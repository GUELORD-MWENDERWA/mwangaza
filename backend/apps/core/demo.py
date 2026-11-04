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
from apps.accounts.models import User
from apps.accounts.phone import DEMO_PHONE_PREFIX
from apps.ai.demo import create_demo_ai
from apps.audit.demo import create_demo_security
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
SELLER_PHONE = "+243000000003"  # compte « commercial » de `accounts/demo.py`
DEMO_REQUESTS = [
    (
        1,
        {
            "source": "chat",
            "name": "Papa Gloire",
            "phone": "+243000300004",
            "message": "Bonjour, mon école de 400 élèves peut-elle payer en francs congolais ?",
        },
    ),
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
            "status": "demo_done",
            "notes": "Démonstration en ligne faite le 15/10 : revient vers nous après son conseil.",
            "follow_up_in_days": 5,
        },
    ),
    (
        140,
        {
            "name": "SIFA NEEMA Rose",
            "role": "head",
            "school_name": "Lycée Tuungane",
            "town": "Goma",
            "phone": "+243000300005",
            "size": "800-1500",
            "status": "contacted",
            "notes": "Appelée lundi : veut voir la paie. Rappeler.",
            "follow_up_in_days": -2,
        },
    ),
    (
        300,
        {
            "name": "KATEMBO LUC",
            "role": "promoter",
            "school_name": "Institut Bon Berger",
            "town": "Butembo",
            "phone": "+243000300006",
            "size": "300-800",
            "status": "signed",
            "notes": "Contrat signé ; ouverture de l'espace réel à faire.",
        },
    ),
    (
        400,
        {
            "name": "MBUSA JEAN",
            "role": "accountant",
            "school_name": "École Étoile du Kivu",
            "town": "Goma",
            "phone": "+243000300007",
            "size": "lt300",
            "status": "lost",
            "lost_reason": "Trop petite pour le moment, paie encore sur papier.",
        },
    ),
]


def create_demo_requests() -> None:
    """Demandes de démonstration fictives pour la console, remises comme au départ."""
    DemoRequest.objects.filter(phone__startswith=DEMO_PHONE_PREFIX).delete()
    now = timezone.now()
    today = timezone.localdate()
    seller = User.objects.filter(phone=SELLER_PHONE).first()  # le commercial de démonstration
    for hours, fields in DEMO_REQUESTS:
        fields = dict(fields)
        days = fields.pop("follow_up_in_days", None)
        if days is not None:
            fields["follow_up_on"] = today + timedelta(days=days)
            fields["assignee"] = seller
        request = DemoRequest.objects.create(is_demo=True, **fields)
        # `auto_now_add` remplit la date à la création : on la recule ensuite.
        DemoRequest.objects.filter(pk=request.pk).update(created_at=now - timedelta(hours=hours))


def ensure_demo_console() -> None:
    """Console en mode démonstration (lot 5, ②bis) : crée une école de démonstration depuis la
    console, jamais depuis `make demo`. S'il n'y a encore aucun prospect fictif, en remet : le
    mode démonstration montre alors une console vivante. Ne touche à rien de réel."""
    if not DemoRequest.objects.filter(is_demo=True).exists():
        create_demo_requests()
    create_demo_security()


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
            "company_name": "Mwangaza SARL (démonstration)",
            "company_ids": "RCCM CD/GOM/RCCM/00-X-0000 · Id. nat. 00-000-N00000X (fictifs)",
            "signer_name": "Directrice générale (à compléter)",
            "signer_title": "Directrice générale",
            "payment_details": (
                "Banque (fictive) : compte 00000-00000-00000000000-00\nMobile Money : +243000000999"
            ),
            "legal_notice": (
                "Plateforme de démonstration : toutes les données sont fictives.\n"
                "Éditeur, hébergeur et contact : à compléter dans les paramètres de la plateforme."
            ),
        },
    )
    return platform
