"""Annonces de l'école aux familles (H4) ou à son personnel (5.7) : publication, archivage,
familles ou personnes touchées."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import Membership, User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.ids import uuid7
from apps.core.tenancy import require_current_school
from apps.notifications import events
from apps.notifications.models import Announcement
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment, Family


def recipient_families(audience: str, class_groups=()) -> QuerySet[Family]:
    """Familles qui ont au moins un enfant inscrit (actif) cette année, dans les classes choisies
    si l'annonce ne va pas à toutes ; une fratrie ne compte qu'une fois. Aucune pour une annonce
    au personnel."""
    if audience == Announcement.Audience.STAFF:
        return Family.objects.none()
    enrolled = Enrollment.objects.filter(
        status=Enrollment.Status.ACTIVE, academic_year__is_current=True
    )
    if audience == Announcement.Audience.CLASS_GROUPS:
        enrolled = enrolled.filter(class_group__in=list(class_groups))
    # Les identifiants se lisent d'abord (une jointure simple), puis `pk__in` : des sous-requêtes
    # imbriquées ou un DISTINCT sur trois tables prennent un mauvais plan tant que PostgreSQL ne
    # connaît pas la taille des tables (base neuve de la démo et des tests : 20 s la requête).
    ids = set(enrolled.values_list("student__family", flat=True))
    return Family.objects.filter(pk__in=ids)


def staff_members() -> QuerySet[User]:
    """Personnel actif de l'école courante (tous rôles)."""
    members = Membership.objects.filter(
        school=require_current_school(), is_active=True, user__is_active=True
    )
    return User.objects.filter(pk__in=members.values("user"))


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
    to_staff = audience == Announcement.Audience.STAFF
    if audience != Announcement.Audience.CLASS_GROUPS:
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
    }
    if to_staff:
        after["staff"] = staff_members().count()
    else:
        after["families"] = recipient_families(audience, class_groups).count()
    audit.record(Action.ANNOUNCEMENTS_PUBLISHED, announcement, actor=actor, after=after)
    if to_staff:
        events.staff_announcement_published(announcement, staff_members().exclude(pk=actor.pk))
    else:
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
