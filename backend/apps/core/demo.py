"""Remplir un espace de démonstration (`fill`) : le même code pour `make demo` et pour la console
(4.17, `03` § 4 bis). Et l'identité de la plateforme pour `make demo` (5.1) : valeurs de départ,
contact du support et mentions légales fictifs ; les vraies valeurs se saisissent dans les
paramètres de la plateforme."""

from collections.abc import Callable
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.academics.demo import create_demo_courses, create_demo_grades, create_demo_promotion
from apps.accounts.demo import create_demo_accounts
from apps.accounts.phone import DEMO_PHONE_PREFIX
from apps.core.models import DemoRequest, PlatformSettings
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

# Chaque tâche qui ajoute un modèle ajoute ici son étape (`docs/07-a-fournir.md` § 4). Une étape
# ne touche qu'aux espaces reçus, jamais au reste de la plateforme, et peut être rejouée.
STEPS: list[Callable[[list[DemoSpace]], None]] = [
    create_demo_look,
    create_demo_accounts,
    create_demo_organisation,
    create_demo_courses,
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


def fill(spaces: list[DemoSpace], on_step: Callable[[int, int], None] | None = None) -> None:
    """Écrit les données fictives dans `spaces` (écoles déjà créées, de démonstration), ou les
    remet comme au départ. Une transaction par étape : des écritures courtes, et `on_step(faites,
    total)` dit où on en est (avancement affiché par la console). Tâche de la plateforme : la base
    laisse voir toutes les écoles (S.6, codes famille uniques partout), chaque étape travaille
    dans l'école de chaque espace (`use_school`)."""
    for space in spaces:
        if not space.school.is_demo:
            raise ValueError(f"{space.school.code} n'est pas un espace de démonstration.")
    for done, step in enumerate(STEPS, start=1):
        with use_all_schools(), transaction.atomic():
            step(spaces)
        if on_step is not None:
            on_step(done, len(STEPS))


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
