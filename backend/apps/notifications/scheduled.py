"""Notifications à heure fixe (5.6.2). Le planificateur (Celery beat, dans le worker) appelle
`tick` toutes les quinze minutes : pour chaque école ouverte, à son heure et dans son fuseau, une
fois par jour et par sorte de travail. La marque du passage (`ScheduledRun`) est écrite dans la
transaction des notifications : un passage rejoué, ou deux en même temps, n'envoie rien deux fois.

Une école sans le module `notifications` est ignorée ; les relances demandent aussi `finance` et
`portal`, l'alerte des caisses `finance` (M.2.1).

- Relances aux parents, à `REMINDERS_TIME`, si l'école les a activées (`schools/reminders.py`) :
  échéance proche et retard de paiement | une notification par parent, tous ses enfants réunis,
  montants par devise (jamais additionnés), dans sa langue.
- Caisses encore ouvertes, à l'heure de clôture choisie par l'école (`schools/alerts.py`) : à
  ceux qui lisent les rapports.

`purge`, chaque nuit : notifications et marques de plus de `KEEP_DAYS` jours."""

import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.accounts.models import User
from apps.core.money import Currency, format_amount
from apps.core.tenancy import use_all_schools, use_school
from apps.finance import services as finance
from apps.finance.models import CashSession, StudentCharge
from apps.notifications import events, push
from apps.notifications.models import Notification, ScheduledRun
from apps.portal.children import fee_label
from apps.schools import alerts
from apps.schools.models import School
from apps.students.models import Enrollment, Family

logger = logging.getLogger(__name__)

App, Kind, Job = Notification.App, Notification.Kind, ScheduledRun.Job

# Heure de l'école à partir de laquelle partent les relances aux parents.
REMINDERS_TIME = time(8, 0)
# Notifications et marques des passages gardées.
KEEP_DAYS = 90


def tick(now: datetime | None = None, *, force: bool = False) -> dict[str, int]:
    """Un passage : notifications créées par code d'école. Deux requêtes quand rien n'est à
    faire. `force` : sans attendre l'heure (`make relances`, pour un essai)."""
    now = now or timezone.now()
    # Tâche de fond, sans école courante : les marques de toutes les écoles en une requête, puis
    # chaque école est servie dans la sienne (`run`).
    with use_all_schools():
        done = set(
            ScheduledRun.all_schools.filter(day__gte=now.date() - timedelta(days=1)).values_list(
                "school_id", "job", "day"
            )
        )
    created = defaultdict(int)
    # Seulement les écoles qui ont le module `notifications` (une requête, pas un test par école).
    schools = School.objects.exclude(status__in=School.CLOSED_STATUSES).filter(
        modules__contains=["notifications"]
    )
    for school in schools:
        local = now.astimezone(ZoneInfo(school.timezone))
        hours = {}
        if school.has_module("finance"):
            hours[Job.OPEN_REGISTERS] = alerts.closing_time(school.settings)
        if school.reminders["enabled"] and {"finance", "portal"} <= set(school.modules):
            hours[Job.REMINDERS] = REMINDERS_TIME
        for job, hour in hours.items():
            if (school.pk, job, local.date()) in done or not (force or local.time() >= hour):
                continue
            try:
                created[school.code] += run(school, job, now)
            except Exception:
                # Une école en erreur ne retient pas les autres ; reprise au passage suivant.
                logger.exception("Notifications à heure fixe : %s, %s", school.code, job)
    return dict(created)


def run(school: School, job: str, now: datetime) -> int:
    """Le travail du jour d'une école, dans son fuseau, une seule fois : rien (0) s'il est déjà
    marqué. Rend le nombre de notifications créées."""
    local = now.astimezone(ZoneInfo(school.timezone))
    with use_school(school), timezone.override(local.tzinfo), transaction.atomic():
        _mark, new = ScheduledRun.objects.get_or_create(job=job, day=local.date())
        return JOBS[job](school, local.date()) if new else 0


def purge(now: datetime | None = None) -> int:
    """Efface, dans toutes les écoles, les notifications de plus de `KEEP_DAYS` jours (lues ou
    non) et les marques des passages aussi vieilles. Rend le nombre de notifications effacées."""
    before = (now or timezone.now()) - timedelta(days=KEEP_DAYS)
    with use_all_schools():
        ScheduledRun.all_schools.filter(day__lt=before.date()).delete()
        deleted, _by_model = Notification.all_schools.filter(created_at__lt=before).delete()
    return deleted


# Relances aux parents


def _amounts(charges: list[StudentCharge]) -> str:
    """« 120,00 $ + 25 000 FC » : ce qui reste, par devise, dollars d'abord."""
    totals = defaultdict(int)
    for charge in charges:
        totals[charge.currency] += charge.remaining_minor
    return " + ".join(format_amount(totals[c], c) for c in Currency.values if totals.get(c))


def _day(day: date) -> str:
    """« 15 octobre », dans la langue du destinataire."""
    return formats.date_format(day, "j F")


def _due_text(charges: list[StudentCharge], students: str) -> tuple[str, str]:
    fees = ", ".join(dict.fromkeys(fee_label(charge) for charge in charges))
    return (
        _("Payment due on %(date)s: %(amounts)s")
        % {"date": _day(charges[0].due_on), "amounts": _amounts(charges)},
        _("%(students)s · %(fees)s") % {"students": students, "fees": fees},
    )


def _late_text(charges: list[StudentCharge], students: str) -> tuple[str, str]:
    since = min(charge.due_on for charge in charges)
    return (
        _("Late payment: %(amounts)s") % {"amounts": _amounts(charges)},
        _("%(students)s · since %(date)s") % {"students": students, "date": _day(since)},
    )


def _reminders(school: School, day: date) -> int:
    """Relances du jour aux parents qui ont un compte du portail (actif, accès non suspendu par
    l'école) : échéances qui tombent dans `days_before` jours et reste > 0 ; retards, sauf pour
    un parent déjà rappelé depuis moins de `overdue_every_days` jours (sa dernière notification
    de retard fait foi). Six requêtes quelle que soit la taille de l'école, limitées aux enfants
    de ces familles ; même calcul que le solde (`finance.charges_by_enrollment`).

    Familles d'abord, puis leurs inscriptions : une seule requête sur les cinq tables (inscription,
    élève, famille, compte, année) ne finit jamais quand PostgreSQL croit les tables vides (base
    juste remplie : `make demo`, import)."""
    settings = school.reminders
    parents = {
        family.pk: family.primary_user
        for family in Family.objects.filter(
            primary_user__is_active=True, portal_suspended_at__isnull=True
        ).select_related("primary_user")
    }
    students = {
        enrollment.pk: enrollment.student
        for enrollment in Enrollment.objects.filter(
            academic_year__is_current=True,
            status=Enrollment.Status.ACTIVE,
            student__family__in=list(parents),
        ).select_related("student")
    }
    if not students:
        return 0
    since = timezone.make_aware(
        datetime.combine(day - timedelta(days=settings["overdue_every_days"] - 1), time.min)
    )
    reminded = set(
        Notification.objects.filter(kind=Kind.PAYMENT_OVERDUE, created_at__gte=since).values_list(
            "user_id", flat=True
        )
    )
    due_on = day + timedelta(days=settings["days_before"])
    soon, late = defaultdict(list), defaultdict(list)
    charges = finance.charges_by_enrollment(list(students), light=True)
    for enrollment_id, items in charges.items():
        parent = parents[students[enrollment_id].family_id]
        for charge in items:
            if charge.state == finance.OVERDUE and parent.pk not in reminded:
                late[parent].append(charge)
            elif charge.state == finance.UPCOMING and charge.due_on == due_on:
                soon[parent].append(charge)

    drafts = [
        reminder(kind, parent, items, students)
        for kind, by_parent in ((Kind.PAYMENT_DUE, soon), (Kind.PAYMENT_OVERDUE, late))
        for parent, items in by_parent.items()
    ]
    return len(push.create(school, drafts))


def reminder(kind: str, parent: User, charges: list[StudentCharge], students: dict) -> Notification:
    """Relance d'un parent, pas encore enregistrée : tous ses enfants concernés réunis
    (`students` : l'élève de chaque inscription), dans sa langue. Un seul enfant : elle ouvre sa
    page (solde et reçus) ; plusieurs : l'accueil du portail."""
    children = {charge.enrollment_id: students[charge.enrollment_id] for charge in charges}
    [child, *others] = children.values()
    with translation.override(parent.language):
        title, body = TEXTS[kind](charges, ", ".join(str(student) for student in children.values()))
    url = "/" if others else f"/children/{child.pk}"
    return push.draft(parent, app=App.PORTAIL, kind=kind, title=title, body=body, url=url)


TEXTS = {Kind.PAYMENT_DUE: _due_text, Kind.PAYMENT_OVERDUE: _late_text}


# Alerte au personnel


def _open_registers(school: School, day: date) -> int:
    """Caisses pas encore clôturées à l'heure choisie par l'école, ouvertes ce jour-là ou avant
    (ce que montre le tableau de bord) : signalées chaque soir tant qu'elles le restent."""
    sessions = list(
        CashSession.objects.filter(closed_at__isnull=True)
        .select_related("cash_register", "cashier")
        .order_by("opened_at")
    )
    if not sessions:
        return 0
    registers = ", ".join(f"{session.cash_register} ({session.cashier})" for session in sessions)
    count = len(sessions)
    return events.send(
        events.staff(Kind.REGISTER_OPEN),
        app=App.GESTION,
        kind=Kind.REGISTER_OPEN,
        url="/cash-closings",
        text=lambda: (
            ngettext("%(count)d register still open", "%(count)d registers still open", count)
            % {"count": count},
            registers,
        ),
    )


JOBS = {Job.REMINDERS: _reminders, Job.OPEN_REGISTERS: _open_registers}
