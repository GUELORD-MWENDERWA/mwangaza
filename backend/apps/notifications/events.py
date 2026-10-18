"""Notifications des événements de l'école (5.6.1), écrites au moment de l'action, dans sa
transaction : paiement reçu, annonce et convocation (5.7) pour le parent (Portail), écart de caisse
et annulation à valider pour le personnel qui en a le droit, annonce de l'école pour tout son
personnel (Gestion), droit sensible donné à un compte pour ceux qui gèrent les rôles (S.3.1), fiche
de cotes envoyée ou renvoyée (NB.1). Le
texte est écrit dans la langue de chaque destinataire ; l'envoi sur l'écran suit la validation
(`push.notify`).

Appelées depuis les services, dans l'école courante. Les envois à heure fixe (échéance proche,
retard, caisse encore ouverte) : `scheduled.py` (5.6.2)."""

from collections import defaultdict
from collections.abc import Callable, Iterable

from django.db.models import QuerySet
from django.utils import timezone, translation
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from apps.academics.models import DisciplineIncident, GradeSheet
from apps.accounts.models import Role, User
from apps.accounts.roles import PERMISSIONS, sorted_permissions
from apps.core.models import PlatformSettings
from apps.core.money import format_amount
from apps.core.tenancy import require_current_school
from apps.finance.models import CancellationRequest, CashClosing, CashSession, Payment
from apps.notifications import push
from apps.notifications.models import Announcement, Notification, Summons
from apps.students.models import Family

App = Notification.App
Kind = Notification.Kind


def send(users: Iterable[User], *, app: str, kind: str, url: str, text: Callable) -> int:
    """`text()` rend (titre, message) ; appelée une fois par langue des destinataires. Rend le
    nombre de notifications créées (aucune dans une école sans le module `notifications`)."""
    school = require_current_school()
    if not school.has_module("notifications"):
        return 0
    by_language = defaultdict(list)
    for user in users:
        by_language[user.language].append(user)
    created = 0
    for language, group in by_language.items():
        with translation.override(language):
            title, body = text()
        created += len(
            push.notify(group, school=school, app=app, kind=kind, title=title, body=body, url=url)
        )
    return created


def _parents(families: QuerySet[Family]) -> QuerySet[User]:
    """Comptes du portail de ces familles ; aucun pour une famille dont l'école a suspendu
    l'accès (elle ne voit plus rien de l'école)."""
    with_access = families.filter(portal_suspended_at__isnull=True)
    return User.objects.filter(is_active=True, pk__in=with_access.values("primary_user"))


def staff(kind: str, *, but: User | None = None) -> QuerySet[User]:
    """Personnel actif de l'école qui a le droit de recevoir cette sorte, sauf `but` : l'auteur
    de l'action (il le sait déjà) ou, pour une alerte de sécurité, l'intéressé."""
    users = User.objects.filter(
        is_active=True,
        memberships__school=require_current_school(),
        memberships__is_active=True,
        memberships__roles__permissions__contains=[push.STAFF_KINDS[kind]],
    )
    return (users.exclude(pk=but.pk) if but else users).distinct()


def payment_received(payment: Payment) -> None:
    """Paiement encaissé : le parent le voit sur son téléphone et ouvre la page de l'enfant, où
    sont son solde et le reçu en PDF."""
    student = payment.enrollment.student
    parents = _parents(Family.objects.filter(pk=student.family_id))
    amount = format_amount(payment.received_amount_minor, payment.received_currency)
    send(
        parents,
        app=App.PORTAIL,
        kind=Kind.PAYMENT_RECEIVED,
        url=f"/children/{student.pk}",
        text=lambda: (
            _("Payment received: %(amount)s") % {"amount": amount},
            _("%(student)s · receipt %(number)s")
            % {"student": student, "number": payment.receipt_number},
        ),
    )


def announcement_published(announcement: Announcement, families: QuerySet[Family]) -> None:
    """Annonce de l'école : aux familles visées qui ont un compte. Le texte est celui de l'école,
    tel qu'elle l'a écrit."""
    send(
        _parents(families),
        app=App.PORTAIL,
        kind=Kind.ANNOUNCEMENT,
        url="/announcements",
        text=lambda: (announcement.title, announcement.body),
    )


def staff_announcement_published(announcement: Announcement, members: QuerySet[User]) -> None:
    """Annonce de l'école à son personnel (5.7) : à tous les comptes actifs, sauf l'auteur."""
    send(
        members,
        app=App.GESTION,
        kind=Kind.STAFF_ANNOUNCEMENT,
        url="/staff-news",
        text=lambda: (announcement.title, announcement.body),
    )


def summons_issued(summons: Summons) -> None:
    """Convocation (5.7) : le parent la voit sur son téléphone et ouvre le calendrier du portail,
    où sont le jour, l'heure, la personne à voir et le motif."""
    student = summons.student
    when = timezone.localtime(summons.meeting_at)
    send(
        _parents(Family.objects.filter(pk=student.family_id)),
        app=App.PORTAIL,
        kind=Kind.SUMMONS,
        url="/calendar",
        text=lambda: (
            _("Summons: %(student)s") % {"student": student},
            _("You are expected at the school on %(date)s at %(time)s.")
            % {"date": date_format(when, "j F Y"), "time": date_format(when, "H:i")},
        ),
    )


def cash_difference(session: CashSession, closings: list[CashClosing], *, actor: User) -> None:
    """Clôture dont l'écart dépasse, dans une devise, le seuil choisi par l'école
    (`schools/alerts.py`) : à ceux qui lisent les rapports."""
    thresholds = require_current_school().alerts["difference_minor"]
    beyond = [
        line for line in closings if abs(line.difference_minor) > thresholds.get(line.currency, 0)
    ]
    if not beyond:
        return
    amounts = " ; ".join(
        ("+" if line.difference_minor > 0 else "")
        + format_amount(line.difference_minor, line.currency)
        for line in beyond
    )
    register = str(session.cash_register)
    send(
        staff(Kind.CASH_DIFFERENCE, but=actor),
        app=App.GESTION,
        kind=Kind.CASH_DIFFERENCE,
        url="/cash-closings",
        text=lambda: (
            _("Cash difference: %(register)s") % {"register": register},
            _("%(cashier)s closed the register with a difference of %(amounts)s.")
            % {"cashier": actor, "amounts": amounts},
        ),
    )


def cancellation_requested(request: CancellationRequest) -> None:
    """Demande d'annulation : à ceux qui la valident. Le message dit quand le caissier dépasse,
    ce jour-là, le nombre de demandes que l'école a choisi de signaler."""
    payment, cashier = request.payment, request.requested_by
    # Le jour de la demande : celui de l'appareil quand elle a été faite hors ligne.
    day = timezone.localtime(request.requested_at).date()
    count = CancellationRequest.objects.filter(requested_by=cashier, requested_at__date=day).count()
    values = {
        "cashier": cashier,
        "count": count,
        "amount": format_amount(payment.received_amount_minor, payment.received_currency),
        "reason": request.reason,
    }
    over = count > require_current_school().alerts["cancellations_per_day"]

    def text() -> tuple[str, str]:
        body = (
            _("%(cashier)s: request no. %(count)s of the day · %(amount)s · %(reason)s")
            if over
            else _("%(cashier)s · %(amount)s · %(reason)s")
        )
        title = _("Cancellation to approve: %(number)s") % {"number": payment.receipt_number}
        return title, body % values

    send(
        staff(Kind.CANCELLATION_REQUEST, but=cashier),
        app=App.GESTION,
        kind=Kind.CANCELLATION_REQUEST,
        url="/cancellations",
        text=text,
    )


# Sécurité : droits sensibles (S.3.1)


def _by(actor: User) -> str:
    """Qui a fait l'action. Comme dans le journal de l'école, le support n'est jamais nommé."""
    if actor.is_platform_admin:
        return _("%(platform)s support") % {"platform": PlatformSettings.load().name}
    return str(actor)


def _rights(permissions: Iterable[str]) -> str:
    return ", ".join(str(PERMISSIONS[code]) for code in sorted_permissions(permissions))


def sensitive_rights_given(member: User, permissions: set[str], *, actor: User) -> None:
    """Un compte reçoit le droit de gérer les rôles ou un droit sur l'argent (rôle donné, compte
    réactivé) : à tous ceux qui gèrent les rôles de l'école, **auteur compris**, sauf
    l'intéressé. Le directeur dont le compte a été pris par quelqu'un d'autre le voit ainsi sur
    son téléphone, même s'il est seul à gérer les rôles."""
    if not permissions:
        return
    send(
        staff(Kind.SENSITIVE_RIGHTS, but=member),
        app=App.GESTION,
        kind=Kind.SENSITIVE_RIGHTS,
        url="/staff",
        text=lambda: (
            _("Sensitive rights: %(person)s") % {"person": member},
            _("Given by %(actor)s: %(rights)s")
            % {"actor": _by(actor), "rights": _rights(permissions)},
        ),
    )


def role_rights_added(role: Role, permissions: set[str], *, actor: User) -> None:
    """Un rôle reçoit un droit sensible : tous les comptes qui l'ont le reçoivent d'un coup. Une
    seule notification à ceux qui gèrent les rôles (auteur compris), avec leur nombre ; rien pour
    un rôle que personne n'a encore."""
    if not permissions:
        return
    holders = role.memberships.filter(is_active=True, user__is_active=True).count()
    if not holders:
        return
    send(
        staff(Kind.SENSITIVE_RIGHTS),
        app=App.GESTION,
        kind=Kind.SENSITIVE_RIGHTS,
        url="/roles",
        text=lambda: (
            _("Sensitive rights: role %(role)s") % {"role": role.name},
            _("Added by %(actor)s · accounts with this role: %(count)s · %(rights)s")
            % {"actor": _by(actor), "count": holders, "rights": _rights(permissions)},
        ),
    )


def incident_recorded(incident: DisciplineIncident) -> None:
    """Faute de l'enfant écrite (8.5.1b) : le parent la voit sur son téléphone et ouvre la page de
    l'enfant, où sont ses fautes et sa cote de conduite. Ni la note de l'enseignant ni son nom."""
    student = incident.enrollment.student
    send(
        _parents(Family.objects.filter(pk=student.family_id)),
        app=App.PORTAIL,
        kind=Kind.DISCIPLINE_INCIDENT,
        url=f"/children/{student.pk}",
        text=lambda: (
            _("Conduct: %(student)s") % {"student": student},
            _("%(offence)s on %(date)s (%(points)s points).")
            % {
                "offence": incident.rule.label,
                "date": date_format(incident.occurred_on, "j F Y"),
                "points": incident.points,
            },
        ),
    )


def places_offered(family_ids: Iterable, year_name: str) -> None:
    """Places de l'année suivante proposées (8.4.5) : un envoi pour toutes les familles de la
    classe ; le parent ouvre l'accueil du portail, où il répond pour chaque enfant."""
    send(
        _parents(Family.objects.filter(pk__in=family_ids)),
        app=App.PORTAIL,
        kind=Kind.PLACE_OFFERED,
        url="/",
        text=lambda: (
            _("Place for %(year)s") % {"year": year_name},
            _(
                "The school is keeping a place for your child in %(year)s. "
                "Tell it whether they are coming back."
            )
            % {"year": year_name},
        ),
    )


# Notes : fiche de cotes (NB.1)


def _members(*ids) -> QuerySet[User]:
    """Comptes actifs du personnel de l'école parmi `ids`."""
    return User.objects.filter(
        pk__in=[pk for pk in ids if pk],
        is_active=True,
        memberships__school=require_current_school(),
        memberships__is_active=True,
    ).distinct()


def _sheet_label(state: GradeSheet) -> tuple[str, str]:
    from apps.academics.grades import term_label

    course = state.course
    return f"{course.name} · {course.class_group.name}", str(term_label(state.term))


def grades_sent(state: GradeSheet, *, actor: User) -> None:
    """Fiche envoyée et signée : à ceux qui valident les notes (le directeur des études) et au
    titulaire de la classe, qui la lisent dans « Fiche de cotes »."""
    users = {user.pk: user for user in staff(Kind.GRADES_SENT, but=actor)}
    homeroom = state.course.class_group.homeroom_teacher_id
    users.update({user.pk: user for user in _members(homeroom).exclude(pk=actor.pk)})
    course, term = _sheet_label(state)

    def text() -> tuple[str, str]:
        title = _("Grade sheet received: %(course)s") % {"course": course}
        body = _("%(term)s · sent and signed by %(teacher)s") % {"term": term, "teacher": actor}
        return title, body

    send(
        users.values(),
        app=App.GESTION,
        kind=Kind.GRADES_SENT,
        url=f"/grade-sheets/totals?course={state.course_id}&term={state.term_id}",
        text=text,
    )


def grades_returned(state: GradeSheet, reason: str, *, sender: User | None, actor: User) -> None:
    """Fiche renvoyée avec les remarques du directeur des études : à l'enseignant du cours (sinon
    à qui l'avait envoyée), qui la retrouve dans son carnet."""
    teacher = state.course.teacher_id or (sender.pk if sender else None)
    course, term = _sheet_label(state)

    def text() -> tuple[str, str]:
        title = _("Grade sheet returned: %(course)s") % {"course": course}
        body = _("%(term)s · %(by)s: %(remarks)s") % {
            "term": term,
            "by": _by(actor),
            "remarks": reason,
        }
        return title, body

    send(
        _members(teacher).exclude(pk=actor.pk),
        app=App.GESTION,
        kind=Kind.GRADES_RETURNED,
        url=f"/grades?course={state.course_id}&term={state.term_id}",
        text=text,
    )
