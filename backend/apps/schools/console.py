"""Tableau de bord de la console de la plateforme (5.2) : toutes les écoles à la fois, lues hors de
toute école (`all_schools`), pour le super-admin seulement (`IsPlatformAdmin`). Liste des écoles
(5.3) : élèves et dernière activité de chacune.

Chiffres des espaces réels seulement (4.15) : un espace d'essai ou de démonstration n'y compte
jamais. Écoles par statut (essais qui finissent bientôt), élèves (inscriptions actives de l'année
en cours de chaque école), paiements du jour par devise (annulés exclus ; montants jamais
additionnés entre devises ; jour dans le fuseau de la plateforme, `TIME_ZONE`), écoles les plus
actives du jour et santé du serveur."""

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Count, OuterRef, QuerySet, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core import health
from apps.core.money import Currency
from apps.finance.models import Payment
from apps.schools.models import School
from apps.students.models import Enrollment

# Un essai qui finit dans ces jours est signalé.
TRIAL_ENDING_DAYS = 30
ACTIVE_SCHOOLS = 10
LIVE = School.Environment.LIVE


def schools() -> QuerySet[School]:
    """Écoles avec `student_count` (inscriptions actives de l'année en cours, A2) et
    `last_activity_at` (dernière entrée de son journal qui n'est ni du support ni du
    super-admin) ; deux sous-requêtes, pas une requête par école."""
    last = (
        AuditLog.all_schools.filter(school=OuterRef("pk"), impersonated_by__isnull=True)
        .exclude(actor__is_platform_admin=True)
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    students = (
        Enrollment.all_schools.filter(
            school=OuterRef("pk"), status="active", academic_year__is_current=True
        )
        .order_by()
        .values("school")
        .annotate(count=Count("pk"))
        .values("count")
    )
    return School.objects.annotate(
        last_activity_at=Subquery(last), student_count=Coalesce(Subquery(students), 0)
    )


def _schools(day) -> dict:
    live = School.objects.filter(environment=LIVE)
    counts = dict(live.values_list("status").annotate(count=Count("id")).order_by())
    ending = live.filter(
        status=School.Status.TRIAL, trial_ends_on__lte=day + timedelta(days=TRIAL_ENDING_DAYS)
    ).count()
    return {
        "active": counts.get(School.Status.ACTIVE, 0),
        "trial": counts.get(School.Status.TRIAL, 0),
        "suspended": counts.get(School.Status.SUSPENDED, 0),
        "trial_ending": ending,
    }


def _today_payments(day) -> tuple[list[dict], list[dict]]:
    start = timezone.make_aware(datetime.combine(day, time()))
    rows = (
        Payment.all_schools.filter(
            school__environment=LIVE,
            cancellation__isnull=True,
            paid_at__gte=start,
            paid_at__lt=start + timedelta(days=1),
        )
        .values("school", "received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"), count=Count("id"))
        .order_by()
    )
    totals = defaultdict(lambda: {"amount_minor": 0, "count": 0})
    by_school = defaultdict(lambda: {"payments": 0, "amounts": defaultdict(int)})
    for row in rows:
        currency = row["received_currency"]
        totals[currency]["amount_minor"] += row["amount_minor"]
        totals[currency]["count"] += row["count"]
        by_school[row["school"]]["payments"] += row["count"]
        by_school[row["school"]]["amounts"][currency] += row["amount_minor"]

    # Chaque devise de la plateforme, même à zéro, dollars d'abord.
    today = [{"currency": c, **totals[c]} for c in Currency.values]
    busiest = sorted(by_school.items(), key=lambda item: -item[1]["payments"])[:ACTIVE_SCHOOLS]
    schools = School.objects.in_bulk([school_id for school_id, _row in busiest])
    active = [
        {
            "id": school_id,
            "code": schools[school_id].code,
            "name": schools[school_id].name,
            "status": schools[school_id].status,
            "payments": row["payments"],
            "today": [
                {"currency": c, "amount_minor": row["amounts"][c]}
                for c in Currency.values
                if c in row["amounts"]
            ],
        }
        for school_id, row in busiest
    ]
    return today, active


def dashboard() -> dict:
    day = timezone.localdate()
    today, active = _today_payments(day)
    return {
        "day": day,
        "schools": _schools(day),
        "students": Enrollment.all_schools.filter(
            school__environment=LIVE, status="active", academic_year__is_current=True
        ).count(),
        "today": today,
        "payments_today": sum(row["count"] for row in today),
        "active_schools": active,
        "health": health.report(),
    }
