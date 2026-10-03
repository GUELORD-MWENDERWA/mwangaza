"""Annonces de démonstration (H4), publiées par le directeur fictif de chaque école, une seule
fois par école : deux à toutes les familles (dont une archivée), une aux dernières classes. Une
famille sur deux les a lues dans le portail, jamais celle du compte de démonstration du portail
(ses annonces y restent « Nouvelle »).

Annonces de la plateforme (5.4.3), publiées une seule fois par le super-admin : une à toutes
les écoles, une à l'ITIG seule, une archivée ; non lues à chaque `make demo` (le bandeau
s'affiche), comme leurs notifications au personnel des écoles visées (5.5)."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.demo import PLATFORM_ADMIN_PHONE
from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.notifications import platform, push, services
from apps.notifications.models import (
    Announcement,
    AnnouncementRead,
    Notification,
    PlatformAnnouncement,
    PlatformAnnouncementRead,
)
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

# Titre, message, jours depuis la publication, écoles visées (vide : toutes), archivée.
PLATFORM_ANNOUNCEMENTS = [
    (
        "Nouvelle version de l'application",
        "La liste des impayés s'imprime maintenant par classe. Rechargez l'application si "
        "l'écran vous propose une mise à jour.",
        20,
        (),
        True,
    ),
    (
        "Votre période d'essai est prolongée",
        "L'essai gratuit de votre école est prolongé jusqu'à la fin du trimestre. Aucune action "
        "n'est demandée de votre part.",
        3,
        ("itig",),
        False,
    ),
    (
        "Maintenance du serveur samedi soir",
        "L'application sera indisponible samedi de 22 h à minuit pour une mise à jour. Les "
        "caisses continuent hors ligne ; tout se synchronise ensuite.",
        1,
        (),
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


def create_demo_platform_announcements(schools: dict[str, School]) -> None:
    PlatformAnnouncementRead.objects.all().delete()
    if not PlatformAnnouncement.objects.exists():
        _publish_platform(schools)
    news = Notification.all_schools.filter(kind=Notification.Kind.PLATFORM_NEWS)
    if not news.exists():
        # Base d'avant la 5.5 : les annonces en cours notifient le personnel.
        for announcement in PlatformAnnouncement.objects.filter(
            archived_at__isnull=True
        ).prefetch_related("schools"):
            push.notify_platform_news(announcement, list(announcement.schools.all()))
    for announcement in PlatformAnnouncement.objects.all():
        news.filter(title=announcement.title).update(created_at=announcement.published_at)
    news.update(read_at=None)


def _publish_platform(schools: dict[str, School]) -> None:
    admin = User.objects.get(phone=PLATFORM_ADMIN_PHONE)
    now = timezone.now()
    # Pas avant la création des écoles (base neuve) : elles ne verraient pas l'annonce.
    start = max(school.created_at for school in schools.values())
    for title, body, days, codes, archived in PLATFORM_ANNOUNCEMENTS:
        announcement = platform.publish(
            actor=admin,
            title=title,
            body=body,
            audience="schools" if codes else "all_schools",
            schools=[schools[code] for code in codes],
        )
        if archived:
            platform.archive(announcement, actor=admin)
        PlatformAnnouncement.objects.filter(pk=announcement.pk).update(
            published_at=max(now - timedelta(days=days), start)
        )
