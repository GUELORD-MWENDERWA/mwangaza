"""Annonces des écoles sur le portail (H4), les plus récentes d'abord, toutes écoles mêlées.

Chaque famille reliée au compte (`primary_user`) lit les annonces de son école qui la visent, comme
les compte la Gestion (`notifications.services.recipient_families`) : à toutes les familles, ou
à une classe où l'un de ses enfants est inscrit (actif) cette année. Jamais une annonce archivée,
ni une annonce publiée avant la fin de l'année scolaire précédente (celles d'une rentrée, publiées
pendant les vacances, restent). Accès suspendu par l'école ou école suspendue : rien. Une annonce
qui ne vise pas la famille n'existe pas (404), comme celle d'une autre école."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import reduce
from operator import or_
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.notifications.models import Announcement, AnnouncementRead
from apps.schools.models import AcademicYear, ClassGroup, School
from apps.students.models import Enrollment, Family

TARGETS = Announcement.class_groups.through


@dataclass
class Reader:
    """Une famille du compte, les classes de ses enfants cette année et la date avant laquelle
    les annonces de son école ne comptent plus."""

    family: Family
    class_groups: set[UUID] = field(default_factory=set)
    since: datetime | None = None


def readers(user: User, family_id: UUID | None = None) -> list[Reader]:
    """Familles du compte qui ont un enfant inscrit cette année (`family_id` : une seule).
    Trois requêtes."""
    families = (
        Family.all_schools.filter(primary_user=user, portal_suspended_at__isnull=True)
        .exclude(school__status=School.Status.SUSPENDED)
        .select_related("school")
    )
    if family_id is not None:
        families = families.filter(pk=family_id)
    found = {reader.family.pk: reader for reader in map(Reader, families)}
    for family, group in Enrollment.all_schools.filter(
        student__family__in=list(found),
        academic_year__is_current=True,
        status=Enrollment.Status.ACTIVE,
    ).values_list("student__family_id", "class_group_id"):
        found[family].class_groups.add(group)
    found = {pk: reader for pk, reader in found.items() if reader.class_groups}
    ends = _previous_year_ends({reader.family.school for reader in found.values()})
    for reader in found.values():
        school = reader.family.school
        if school.pk in ends:
            day = ends[school.pk] + timedelta(days=1)
            reader.since = datetime.combine(day, time.min, tzinfo=ZoneInfo(school.timezone))
    return list(found.values())


def _previous_year_ends(schools: set[School]) -> dict[UUID, date]:
    """Fin de l'année qui précède l'année en cours, par école (aucune : pas de limite)."""
    years = defaultdict(list)
    for year in AcademicYear.all_schools.filter(school__in=schools).only(
        "school_id", "starts_on", "ends_on", "is_current"
    ):
        years[year.school_id].append(year)
    ends = {}
    for school_id, items in years.items():
        current = next((year for year in items if year.is_current), None)
        before = [y.ends_on for y in items if current and y.ends_on <= current.starts_on]
        if before:
            ends[school_id] = max(before)
    return ends


def _aimed_at(reader: Reader) -> Q:
    targeted = TARGETS.objects.filter(
        announcement_id=OuterRef("pk"), classgroup_id__in=reader.class_groups
    )
    condition = Q(school_id=reader.family.school_id, archived_at__isnull=True)
    if reader.since is not None:
        condition &= Q(published_at__gte=reader.since)
    return condition & (Q(audience=Announcement.Audience.ALL_FAMILIES) | Exists(targeted))


def visible(user: User, found: list[Reader]) -> QuerySet[Announcement]:
    """Annonces que ces familles du compte peuvent lire, avec `read` (déjà lue par l'une
    d'elles) ; aucune famille : aucune annonce."""
    if not found:
        return Announcement.all_schools.none()
    read = AnnouncementRead.all_schools.filter(
        announcement=OuterRef("pk"), family__in=[reader.family for reader in found]
    )
    groups = ClassGroup.all_schools.select_related("level", "track")
    return (
        Announcement.all_schools.filter(reduce(or_, map(_aimed_at, found)))
        .select_related("school")
        .prefetch_related(Prefetch("class_groups", queryset=groups))
        .annotate(read=Exists(read))
        .order_by("-published_at", "-id")
    )


def describe(announcements: list[Announcement], found: list[Reader]) -> None:
    """`classes` : classes visées où un enfant de la famille est inscrit (« 3e Électricité A »),
    vide pour une annonce à toutes les familles."""
    mine = defaultdict(set)
    for reader in found:
        mine[reader.family.school_id] |= reader.class_groups
    for announcement in announcements:
        announcement.classes = [
            group.name
            for group in announcement.class_groups.all()
            if group.pk in mine[announcement.school_id]
        ]


def find(user: User, announcement_id) -> Announcement:
    announcement = visible(user, readers(user)).filter(pk=announcement_id).first()
    if announcement is None:
        raise NotFound
    return announcement


def mark_read(user: User, ids: list[UUID]) -> None:
    """Marque lues, pour chaque famille du compte qu'elles visent ; une annonce déjà lue, d'une
    autre école ou qui ne vise pas la famille est ignorée. Deux requêtes par famille."""
    for reader in readers(user):
        rows = [
            AnnouncementRead(
                school=reader.family.school,
                announcement=announcement,
                family=reader.family,
                created_by=user,
            )
            for announcement in Announcement.all_schools.filter(_aimed_at(reader), pk__in=ids).only(
                "id", "school_id"
            )
        ]
        AnnouncementRead.all_schools.bulk_create(rows, ignore_conflicts=True)
