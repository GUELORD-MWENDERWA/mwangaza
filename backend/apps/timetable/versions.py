"""Versions de l'horaire (EDT.4a, spec § 10) : publier un brouillon, lister la version publiée et
les anciennes. Une version publiée ou archivée ne se modifie plus (`drafts._open` refuse tout
geste) : pour la changer, on en copie un nouveau brouillon, puis on le publie.

Publier est sérialisé par un verrou sur l'année scolaire : deux publications en même temps se
suivent, sans heurter la règle « une seule version publiée par année »."""

from datetime import date

from django.db import transaction
from django.db.models import QuerySet, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import AcademicYear
from apps.timetable import checks
from apps.timetable.drafts import NOT_A_DRAFT
from apps.timetable.models import Timetable

PUBLISHED = Timetable.Status.PUBLISHED
ARCHIVED = Timetable.Status.ARCHIVED

HAS_CONFLICTS = ApiError(
    "publish_conflicts",
    _("This draft still has conflicts: correct them before publishing."),
    409,
)
OUTSIDE_YEAR = ApiError(
    "valid_from_outside_year", _("This date is not in the school year of the timetable."), 400
)
BEFORE_CURRENT = ApiError(
    "valid_from_before_current",
    _("This date is before the start of the timetable in force."),
    400,
)


def versions(year: AcademicYear | None) -> QuerySet[Timetable]:
    """Version publiée puis anciennes versions de l'année, la plus récente d'abord (la version
    publiée est toujours la dernière publiée : publier archive la précédente)."""
    return (
        Timetable.objects.filter(academic_year=year, status__in=[PUBLISHED, ARCHIVED])
        .select_related("published_by")
        .annotate(hours=Coalesce(Sum("entries__length"), 0))
        .order_by("-published_at")
    )


def publish(timetable: Timetable, *, valid_from: date, actor) -> Timetable:
    """Le brouillon devient l'horaire de l'école à partir de `valid_from` ; la version en vigueur
    est archivée. Refusé tant que les contrôles du brouillon ont du rouge (un conflit, une règle
    obligatoire non tenue) ; le reste à placer et l'orange ne bloquent pas (horaire provisoire)."""
    with transaction.atomic():
        year = AcademicYear.objects.select_for_update().get(pk=timetable.academic_year_id)
        draft = Timetable.objects.select_for_update().get(pk=timetable.pk)
        if draft.status != Timetable.Status.DRAFT:
            raise BusinessError(NOT_A_DRAFT)
        if not year.starts_on <= valid_from <= year.ends_on:
            raise BusinessError(OUTSIDE_YEAR)
        current = Timetable.objects.filter(academic_year=year, status=PUBLISHED).first()
        if current and current.valid_from and valid_from < current.valid_from:
            raise BusinessError(BEFORE_CURRENT)
        report = checks.draft(draft)
        if report["errors"]:
            raise BusinessError(HAS_CONFLICTS)
        if current:
            current.status = ARCHIVED
            current.save(update_fields=["status", "updated_at"])
        draft.status = PUBLISHED
        draft.valid_from = valid_from
        draft.published_at = timezone.now()
        draft.published_by = actor
        draft.history = []
        draft.save(
            update_fields=[
                "status",
                "valid_from",
                "published_at",
                "published_by",
                "history",
                "updated_at",
            ]
        )
        audit.record(
            Action.TIMETABLE_PUBLISHED,
            draft,
            actor=actor,
            after={
                "name": draft.name,
                "valid_from": valid_from.isoformat(),
                "lessons": len(report["entries"]),
                "hours": sum(entry.length for entry in report["entries"]),
                "left_hours": sum(sum(row["lengths"]) for row in report["left"]),
                "warnings": report["warnings"],
                "replaced": current.name if current else None,
            },
            label=draft.name,
        )
    return draft
