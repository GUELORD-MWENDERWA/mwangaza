"""Remplir un espace de démonstration (`fill`) : le même code pour `make demo` et pour la console
(4.17, `03` § 4 bis). Et l'identité de la plateforme pour `make demo` (5.1) : valeurs de départ,
contact du support et mentions légales fictifs ; les vraies valeurs se saisissent dans les
paramètres de la plateforme."""

from collections.abc import Callable
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.academics.demo import create_demo_courses, create_demo_grades, create_demo_promotion
from apps.accounts.demo import create_demo_accounts
from apps.accounts.phone import DEMO_PHONE_PREFIX
from apps.ai.demo import create_demo_ai
from apps.core import site_content
from apps.core.models import Article, DemoRequest, PlatformSettings
from apps.core.tenancy import use_all_schools
from apps.finance.demo import (
    create_demo_cancellations,
    create_demo_charges,
    create_demo_credits,
    create_demo_discounts,
    create_demo_fees,
    create_demo_payments,
)
from apps.notifications.demo import (
    create_demo_announcements,
    create_demo_communication,
    create_demo_event_notifications,
)
from apps.portal.demo import (
    create_demo_activations,
    create_demo_contact_changes,
    create_demo_portal,
)
from apps.schools.demo import DemoSpace, create_demo_look, create_demo_organisation
from apps.students.demo import create_demo_students
from apps.sync.demo import create_demo_devices
from apps.timetable.demo import create_demo_timetable

# Chaque tâche qui ajoute un modèle ajoute ici son étape (`docs/07-a-fournir.md` § 4). Une étape
# ne touche qu'aux espaces reçus, jamais au reste de la plateforme, et peut être rejouée.
STEPS: list[Callable[[list[DemoSpace]], None]] = [
    create_demo_look,
    create_demo_accounts,
    create_demo_organisation,
    create_demo_courses,
    create_demo_timetable,
    create_demo_ai,
    create_demo_fees,
    create_demo_students,
    create_demo_grades,
    create_demo_charges,
    create_demo_discounts,
    create_demo_payments,
    create_demo_credits,
    create_demo_cancellations,
    create_demo_devices,
    create_demo_announcements,
    create_demo_portal,
    create_demo_contact_changes,
    create_demo_activations,
    create_demo_event_notifications,
    create_demo_communication,
    create_demo_promotion,
]


def fill(
    spaces: list[DemoSpace],
    on_step: Callable[[int, int], None] | None = None,
    *,
    start: int = 0,
    count: int | None = None,
) -> int:
    """Écrit les données fictives dans `spaces` (écoles déjà créées, de démonstration), ou les
    remet comme au départ. Une transaction par étape : des écritures courtes, et `on_step(faites,
    total)` dit où on en est (avancement affiché par la console). Tâche de la plateforme : la base
    laisse voir toutes les écoles (S.6, codes famille uniques partout), chaque étape travaille
    dans l'école de chaque espace (`use_school`). `start`, `count` : seulement ces étapes (la
    console en fait une par tâche de fond, `demonstrations.fill`) ; rend le nombre d'étapes faites
    en tout."""
    for space in spaces:
        if not space.school.is_demo:
            raise ValueError(f"{space.school.code} n'est pas un espace de démonstration.")
    steps = STEPS[start:] if count is None else STEPS[start : start + count]
    for done, step in enumerate(steps, start=start + 1):
        with use_all_schools(), transaction.atomic():
            step(spaces)
        if on_step is not None:
            on_step(done, len(STEPS))
    return start + len(steps)


DEMO_SUPPORT_PHONE = "+243000000999"
SOCIAL_FIELDS = (
    "whatsapp_url",
    "facebook_url",
    "instagram_url",
    "linkedin_url",
    "youtube_url",
    "tiktok_url",
)
# Demandes de démonstration fictives (WEB.1d) : (heures écoulées, champs). Numéros du bloc fictif.
DEMO_REQUESTS = [
    (
        2,
        {
            "name": "MUHINDO KAKULE Jean-Paul",
            "role": "prefect",
            "school_name": "Institut Les Volcans",
            "town": "Goma",
            "phone": "+243000300001",
            "size": "300-800",
            "message": "Nous voulons voir la caisse et les impayés, avec notre comptable.",
        },
    ),
    (
        20,
        {
            "name": "KAVIRA MASIKA Esther",
            "role": "promoter",
            "school_name": "Complexe scolaire Mont Goma",
            "town": "Goma",
            "phone": "+243000300002",
            "size": "lt300",
            "email": "esther.kavira@example.com",
        },
    ),
    (
        96,
        {
            "name": "BAHATI MUSAFIRI Patrick",
            "role": "head",
            "school_name": "École primaire Kivu Lumière",
            "town": "Gisenyi",
            "phone": "+243000300003",
            "size": "300-800",
            "language": "en",
            "status": "called",
            "notes": "Rappelé le 15/10 : démonstration en ligne jeudi à 10 h.",
        },
    ),
]


def create_demo_requests() -> None:
    """Demandes de démonstration fictives pour la console, remises comme au départ."""
    DemoRequest.objects.filter(phone__startswith=DEMO_PHONE_PREFIX).delete()
    now = timezone.now()
    for hours, fields in DEMO_REQUESTS:
        request = DemoRequest.objects.create(**fields)
        # `auto_now_add` remplit la date à la création : on la recule ensuite.
        DemoRequest.objects.filter(pk=request.pk).update(created_at=now - timedelta(hours=hours))


# Actualités fictives du site (SITE.2) : des fonctions qui existent vraiment, aucune école ni
# personne nommée. (jours depuis la publication — négatif : programmé —, champs) ; `None` :
# brouillon.
DEMO_ARTICLES = (
    (
        6,
        {
            "language": "fr",
            "title": "La caisse continue de fonctionner sans internet",
            "summary": "Coupure de réseau à l'heure des paiements : la caissière encaisse, "
            "imprime le reçu, et tout part au serveur au retour du réseau.",
            "body": "À Goma, le réseau tombe souvent au pire moment : le jour où les parents "
            "viennent payer.\n\n## Ce qui ne change pas pour la caissière\n"
            "- elle cherche l'élève et encaisse comme d'habitude ;\n"
            "- le reçu sort avec son **numéro définitif** ;\n"
            "- le solde de l'élève est à jour sur l'appareil.\n\n"
            "## Au retour du réseau\nLes paiements partent seuls, une seule fois chacun. "
            "Le comptable les voit dans la clôture de caisse.",
        },
    ),
    (
        2,
        {
            "language": "fr",
            "title": "Les reçus arrivent sur le téléphone des parents",
            "summary": "Chaque paiement enregistré à la caisse apparaît dans l'espace des "
            "parents, avec son reçu et ce qui reste à payer.",
            "body": "Un parent qui a activé son compte avec le **code famille** voit, pour "
            "chacun de ses enfants :\n- les paiements et leurs reçus ;\n"
            "- les échéances à venir ;\n- les annonces de l'école.\n\n"
            "Le détail est dans [la page des parents](/parents/).",
        },
    ),
    (
        -3,
        {
            "language": "fr",
            "title": "Rappels d'échéance : l'école choisit quand prévenir",
            "summary": "Trois jours avant une tranche, puis en cas de retard : le parent reçoit "
            "un rappel sur son téléphone, si l'école l'active.",
            "body": "Les rappels aux parents sont réglés par chaque école dans ses paramètres."
            "\n\nRien ne part sans son accord.",
        },
    ),
    (
        None,
        {
            "language": "en",
            "title": "The cash desk keeps working without internet",
            "summary": "Network down at payment time: the cashier takes the payment, prints "
            "the receipt, and everything is sent when the network is back.",
            "body": "Payments are sent once each when the network comes back.",
        },
    ),
)


def create_demo_articles() -> None:
    """Actualités fictives, remises comme au départ (celles de la console restent)."""
    Article.objects.filter(title__in=[fields["title"] for _days, fields in DEMO_ARTICLES]).delete()
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    for days, fields in DEMO_ARTICLES:
        article = Article(author_name="", **fields)
        if days is not None:
            article.status = Article.Status.PUBLISHED
            article.published_at = now - timedelta(days=days)
            article.slug = slugify(article.title)
        article.save()
    transaction.on_commit(site_content.clear)


def create_demo_platform() -> PlatformSettings:
    """Remet l'identité de départ (nom, couleurs, sans logo ni icône) avec un support fictif."""
    initial = {
        field.name: field.default
        for field in PlatformSettings._meta.concrete_fields
        if field.has_default() and field.name != "id"
    }
    platform, _ = PlatformSettings.objects.update_or_create(
        pk=1,
        defaults={
            **initial,
            "logo": "",
            "icon": "",
            "support_phone": DEMO_SUPPORT_PHONE,
            "support_email": "support@example.com",
            "address": "Avenue de la Paix n° 1, quartier Les Volcans",
            **{field: "" for field in SOCIAL_FIELDS},
            "legal_notice": (
                "Plateforme de démonstration : toutes les données sont fictives.\n"
                "Éditeur, hébergeur et contact : à compléter dans les paramètres de la plateforme."
            ),
        },
    )
    return platform
