"""Communication de l'école (5.7) : calendrier des événements, convocations des parents, et les
lettres à imprimer (circulaire d'une annonce, convocation) pour les familles sans téléphone."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import school_header
from apps.core.tenancy import require_current_school
from apps.notifications import events
from apps.notifications.models import Announcement, SchoolEvent, Summons
from apps.schools.signatures import signature_context
from apps.students.models import Enrollment, Student


def calendar(*, past: bool = False, day: date | None = None) -> QuerySet[SchoolEvent]:
    """Événements à venir ou en cours, les plus proches d'abord ; `past` : ceux qui sont finis,
    les plus récents d'abord."""
    day = day or timezone.localdate()
    if past:
        return SchoolEvent.objects.filter(ends_on__lt=day).order_by("-starts_on", "-id")
    return SchoolEvent.objects.filter(ends_on__gte=day)


def save_event(event: SchoolEvent | None = None, *, actor: User, **fields) -> SchoolEvent:
    """Crée l'événement ou corrige les champs donnés. Une journée : fin = début."""
    event = event or SchoolEvent(created_by=actor)
    for name, value in fields.items():
        setattr(event, name, value)
    if event.ends_on is None:
        event.ends_on = event.starts_on
    if event.ends_on < event.starts_on:
        message = _("The end cannot be before the start.")
        raise ValidationError({"ends_on": ValidationError(message, code="ends_before_start")})
    event.title = event.title.strip()
    event.save()
    return event


@transaction.atomic
def issue_summons(
    *, actor: User, student: Student, reason: str, meeting_at, meet_with: str
) -> Summons:
    """Convoque les parents d'un élève inscrit cette année : journal, notification au parent."""
    enrollment = (
        Enrollment.objects.filter(
            student=student, academic_year__is_current=True, status=Enrollment.Status.ACTIVE
        )
        .select_related("class_group__level", "class_group__track")
        .first()
    )
    if enrollment is None:
        message = _("This student is not enrolled this year.")
        raise ValidationError({"student": ValidationError(message, code="not_enrolled")})
    if meeting_at < timezone.now():
        message = _("Choose a date and time to come.")
        raise ValidationError({"meeting_at": ValidationError(message, code="in_the_past")})
    summons = Summons.objects.create(
        student=student,
        class_name=enrollment.class_group.name,
        reason=reason.strip(),
        meeting_at=meeting_at,
        meet_with=meet_with.strip(),
        created_by=actor,
    )
    after = {
        "student": str(student),
        "class_name": summons.class_name,
        "meeting_at": timezone.localtime(meeting_at).strftime("%Y-%m-%d %H:%M"),
        "meet_with": summons.meet_with,
        "reason": summons.reason,
    }
    audit.record(Action.SUMMONS_ISSUED, summons, actor=actor, after=after)
    events.summons_issued(summons)
    return summons


@transaction.atomic
def cancel_summons(summons: Summons, *, actor: User) -> Summons:
    """Annule la convocation (elle quitte le portail) ; déjà annulée : rien ne change."""
    summons = Summons.objects.select_for_update().select_related("student").get(pk=summons.pk)
    if summons.cancelled_at is not None:
        return summons
    summons.cancelled_at = timezone.now()
    summons.cancelled_by = actor
    summons.save(update_fields=["cancelled_at", "cancelled_by", "updated_at"])
    audit.record(Action.SUMMONS_CANCELLED, summons, actor=actor, after={"cancelled": True})
    return summons


def search_summons(queryset: QuerySet[Summons], text: str) -> QuerySet[Summons]:
    """Par nom, post-nom, prénom ou matricule de l'élève (chaque mot doit s'y trouver)."""
    for word in text.split():
        queryset = queryset.filter(
            Q(student__last_name__icontains=word)
            | Q(student__middle_name__icontains=word)
            | Q(student__first_name__icontains=word)
            | Q(student__matricule__icontains=word)
        )
    return queryset


def _signature(user: User | None) -> str:
    return str(user) if user else ""


def circular_context(announcement: Announcement) -> dict:
    """Lettre circulaire : l'annonce telle qu'elle a été publiée, à l'en-tête de l'école."""
    school = require_current_school()
    return {
        **school_header(school),
        "contact": school.receipt["header"],
        "announcement": announcement,
        "classes": ", ".join(group.name for group in announcement.class_groups.all()),
        "to_staff": announcement.audience == Announcement.Audience.STAFF,
        "signed_by": _signature(announcement.created_by),
        **signature_context(school, author=announcement.created_by, head_first=True),
    }


def summons_context(summons: Summons) -> dict:
    """Lettre de convocation, avec le coupon que le parent signe et renvoie."""
    school = require_current_school()
    return {
        **school_header(school),
        "contact": school.receipt["header"],
        "summons": summons,
        "student": summons.student,
        "meeting_at": timezone.localtime(summons.meeting_at),
        "signed_by": _signature(summons.created_by),
        **signature_context(school, author=summons.created_by),
    }
