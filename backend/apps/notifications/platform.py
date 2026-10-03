"""Annonces de la plateforme aux écoles (5.4.3) : publication et archivage par le super-admin
(journal de la plateforme), lecture par le personnel de chaque école visée."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.notifications.models import PlatformAnnouncement, PlatformAnnouncementRead
from apps.schools.models import School


@transaction.atomic
def publish(
    *, actor: User, title: str, body: str, audience: str, schools: list[School] | None = None
) -> PlatformAnnouncement:
    """Publie tout de suite, à toutes les écoles ou à celles choisies."""
    schools = [] if audience == PlatformAnnouncement.Audience.ALL_SCHOOLS else schools or []
    if audience == PlatformAnnouncement.Audience.SCHOOLS and not schools:
        message = _("Choose at least one school.")
        raise ValidationError({"schools": ValidationError(message, code="required")})
    announcement = PlatformAnnouncement.objects.create(
        title=title.strip(),
        body=body.strip(),
        audience=audience,
        published_at=timezone.now(),
        created_by=actor,
    )
    announcement.schools.set(schools)
    after = {
        "title": announcement.title,
        "audience": audience,
        "schools": sorted(school.name for school in schools),
    }
    audit.record_platform(
        PlatformAction.ANNOUNCEMENT_PUBLISHED, announcement, actor=actor, after=after
    )
    return announcement


@transaction.atomic
def archive(announcement: PlatformAnnouncement, *, actor: User) -> PlatformAnnouncement:
    """Retire l'annonce de la Gestion de chaque école ; déjà archivée : rien ne change."""
    announcement = PlatformAnnouncement.objects.select_for_update().get(pk=announcement.pk)
    if announcement.archived_at is not None:
        return announcement
    announcement.archived_at = timezone.now()
    announcement.archived_by = actor
    announcement.save(update_fields=["archived_at", "archived_by", "updated_at"])
    audit.record_platform(
        PlatformAction.ANNOUNCEMENT_ARCHIVED, announcement, actor=actor, after={"archived": True}
    )
    return announcement


def for_school(school: School, user: User) -> QuerySet[PlatformAnnouncement]:
    """Annonces que voit le personnel de l'école : non archivées, à toutes les écoles ou à elle,
    publiées depuis sa création ; `is_read` pour ce compte."""
    in_schools = PlatformAnnouncement.schools.through.objects.filter(
        platformannouncement=OuterRef("pk"), school=school
    )
    targeted = Exists(in_schools) | Q(audience=PlatformAnnouncement.Audience.ALL_SCHOOLS)
    read = PlatformAnnouncementRead.objects.filter(announcement=OuterRef("pk"), user=user)
    return (
        PlatformAnnouncement.objects.filter(
            targeted, archived_at__isnull=True, published_at__gte=school.created_at
        )
        .annotate(is_read=Exists(read))
        .order_by("-published_at", "-id")
    )


def mark_read(school: School, user: User, ids: list) -> None:
    """Note comme lues, pour ce compte, celles des annonces qui visent l'école ; les autres
    identifiants sont ignorés (une école ne touche pas aux annonces d'une autre)."""
    visible = for_school(school, user).filter(pk__in=ids, is_read=False)
    PlatformAnnouncementRead.objects.bulk_create(
        [PlatformAnnouncementRead(announcement=a, user=user) for a in visible],
        ignore_conflicts=True,
    )
