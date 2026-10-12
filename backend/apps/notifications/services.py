"""Annonces de l'école aux familles (H4) : publication, archivage, familles touchées."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.notifications import events
from apps.notifications.models import Announcement
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment, Family


def recipient_families(audience: str, class_groups=()) -> QuerySet[Family]:
    """Familles qui ont au moins un enfant inscrit (actif) cette année, dans les classes choisies
    si l'annonce ne va pas à toutes ; une fratrie ne compte qu'une fois."""
    enrolled = Q(
        students__enrollments__status=Enrollment.Status.ACTIVE,
        students__enrollments__academic_year__is_current=True,
    )
    if audience == Announcement.Audience.CLASS_GROUPS:
        enrolled &= Q(students__enrollments__class_group__in=list(class_groups))
    return Family.objects.filter(enrolled).distinct()


@transaction.atomic
def publish(
    *,
    actor: User,
    title: str,
    body: str,
    audience: str,
    class_groups: list[ClassGroup] | None = None,
    attachment=None,
) -> Announcement:
    """Publie tout de suite. `class_groups` : classes de l'année en cours, déjà vérifiées ;
    `attachment` : PDF déjà vérifié (`attachments.validate_attachment`)."""
    class_groups = class_groups or []
    if audience == Announcement.Audience.ALL_FAMILIES:
        class_groups = []
    elif not class_groups:
        message = _("Choose at least one class.")
        raise ValidationError({"class_groups": ValidationError(message, code="required")})
    announcement = Announcement.objects.create(
        title=title.strip(),
        body=body.strip(),
        audience=audience,
        published_at=timezone.now(),
        created_by=actor,
    )
    announcement.class_groups.set(class_groups)
    if attachment is not None:
        announcement.attachment.save(f"annonce-{uuid7().hex[-12:]}.pdf", attachment)
    after = {
        "title": announcement.title,
        "audience": audience,
        "class_groups": sorted(group.name for group in class_groups),
        "attachment": bool(announcement.attachment),
        "families": recipient_families(audience, class_groups).count(),
    }
    audit.record(Action.ANNOUNCEMENTS_PUBLISHED, announcement, actor=actor, after=after)
    events.announcement_published(announcement, recipient_families(audience, class_groups))
    return announcement


@transaction.atomic
def archive(announcement: Announcement, *, actor: User) -> Announcement:
    """Retire l'annonce du portail ; déjà archivée : rien ne change."""
    announcement = Announcement.objects.select_for_update().get(pk=announcement.pk)
    if announcement.archived_at is not None:
        return announcement
    announcement.archived_at = timezone.now()
    announcement.archived_by = actor
    announcement.save(update_fields=["archived_at", "archived_by", "updated_at"])
    audit.record(Action.ANNOUNCEMENTS_ARCHIVED, announcement, actor=actor, after={"archived": True})
    return announcement
