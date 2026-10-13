"""Calendrier du portail (5.7) : événements des écoles où un enfant du compte est inscrit cette
année, et convocations de ses enfants, toutes écoles mêlées.

Comme les annonces (`announcements.py`) : accès suspendu par l'école ou école suspendue, rien ;
un événement réservé au personnel n'existe pas pour une famille ; la convocation de l'enfant d'un
autre compte non plus."""

from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import SchoolEvent, Summons
from apps.portal import announcements
from apps.portal.children import linked_to
from apps.schools.models import School

# Une convocation reste affichée une semaine après son jour (le parent retrouve l'heure, le motif).
SUMMONS_KEPT = timedelta(days=7)


def events(user: User) -> QuerySet[SchoolEvent]:
    """Événements pour tous, à venir ou en cours, les plus proches d'abord. Quatre requêtes."""
    schools = {reader.family.school_id for reader in announcements.readers(user)}
    return (
        SchoolEvent.all_schools.filter(
            school__in=schools,
            audience=SchoolEvent.Audience.EVERYONE,
            ends_on__gte=timezone.localdate(),
        )
        .select_related("school")
        .order_by("starts_on", "start_time", "id")
    )


def summons(user: User) -> QuerySet[Summons]:
    """Convocations non annulées des enfants du compte, la plus proche d'abord."""
    return (
        Summons.all_schools.filter(
            cancelled_at__isnull=True,
            meeting_at__gte=timezone.now() - SUMMONS_KEPT,
            **linked_to(user, "student__family"),
        )
        .exclude(School.portal_closed("school__"))
        .select_related("student", "school")
        .order_by("meeting_at", "id")
    )


def mark_seen(user: User, ids: list) -> None:
    """« Vue le » dans la Gestion ; celles d'un autre compte sont ignorées."""
    summons(user).filter(pk__in=ids, seen_at__isnull=True).update(seen_at=timezone.now())
