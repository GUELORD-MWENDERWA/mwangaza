"""Annonces de démonstration (H4), publiées par le directeur fictif de chaque école, une seule
fois par école : deux à toutes les familles (dont une archivée), une aux dernières classes. Une
famille sur deux les a lues dans le portail, jamais celle du compte de démonstration du portail
(ses annonces y restent « Nouvelle »)."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.notifications import services
from apps.notifications.models import Announcement, AnnouncementRead
from apps.schools.models import ClassGroup, School
from apps.students.models import Family

PUBLISHERS = {"itig": "+243000001001", "volcans": "+243000002001"}
# Titre, message, jours depuis la publication, classes visées, archivée.
ANNOUNCEMENTS = [
    (
        "Mesures d'hygiène à l'entrée de l'école",
        "Chers parents, un point de lavage des mains est installé au portail. Chaque élève se "
        "lave les mains en arrivant. Merci de rappeler cette consigne à vos enfants.",
        30,
        False,
        True,
    ),
    (
        "Rappel : paiement de la 1re tranche",
        "Chers parents, la 1re tranche des frais scolaires est attendue avant le 15 du mois. "
        "La caisse est ouverte du lundi au vendredi de 7 h 30 à 15 h. Merci de garder le reçu.",
        8,
        False,
        False,
    ),
    (
        "Réunion des parents des classes terminales",
        "Chers parents, une réunion sur la préparation des examens aura lieu samedi prochain à "
        "9 h dans la grande salle. Présence vivement souhaitée.",
        2,
        True,
        False,
    ),
]


def create_demo_announcements(schools: dict[str, School]) -> None:
    for code, school in schools.items():
        with use_school(school):
            if not Announcement.objects.exists():
                _publish(User.objects.get(phone=PUBLISHERS[code]))
            _create_reads()


def _publish(publisher: User) -> None:
    now = timezone.now()
    last_classes = list(
        ClassGroup.objects.filter(academic_year__is_current=True)
        .select_related("level", "track")
        .order_by("-level__order", "track__name", "section")[:3]
    )
    for title, body, days, for_classes, archived in ANNOUNCEMENTS:
        announcement = services.publish(
            actor=publisher,
            title=title,
            body=body,
            audience="class_groups" if for_classes else "all_families",
            class_groups=last_classes if for_classes else None,
        )
        if archived:
            services.archive(announcement, actor=publisher)
        published_at = now - timedelta(days=days)
        Announcement.objects.filter(pk=announcement.pk).update(
            published_at=published_at,
            archived_at=published_at + timedelta(days=21) if archived else None,
        )


def _create_reads() -> None:
    # La famille du compte du portail (la première créée, `portal.demo`) : ses annonces
    # redeviennent « Nouvelle » à chaque `make demo`.
    shared = Family.objects.order_by("created_at", "id").values_list("pk", flat=True).first()
    AnnouncementRead.objects.filter(family_id=shared).delete()
    if AnnouncementRead.objects.exists():
        return
    published = Announcement.objects.filter(archived_at__isnull=True).prefetch_related(
        "class_groups"
    )
    for announcement in published:
        families = (
            services.recipient_families(announcement.audience, announcement.class_groups.all())
            .exclude(pk=shared)
            .only("id", "school_id")
            .order_by("id")
        )
        rows = [
            AnnouncementRead(announcement=announcement, family=family)
            for family in list(families)[::2]
        ]
        AnnouncementRead.objects.bulk_create(rows)
