"""Portail de démonstration (H2) : la première famille d'un espace a un compte du portail. Avec
`make demo`, elle a des enfants dans les deux écoles : son compte est relié à sa fiche de l'ITIG,
sa fiche des Volcans reste à ajouter avec son code (« Ajouter un enfant d'une autre école »).
Trois coordonnées envoyées par des parents attendent le secrétariat du profil `itig` (H5)."""

import random
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.demo import set_demo_password
from apps.accounts.models import User
from apps.accounts.phone import InvalidPhoneError, is_demo_phone, normalize_phone
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.schools.models import School
from apps.students import contact_changes
from apps.students.models import ContactChange, Family


@dataclass
class DemoPortal:
    phone: str
    # Code de la même famille dans l'espace suivant (`make demo` : Volcans), à ajouter.
    code_to_add: str | None


def _first_family(school: School) -> Family | None:
    # La famille du compte du portail : la première créée dans chaque école (`students.demo`).
    with use_school(school):
        return Family.objects.prefetch_related("guardians").order_by("created_at", "id").first()


def demo_portal(spaces: list[DemoSpace]) -> DemoPortal | None:
    """Le parent de démonstration, pour l'afficher (`make demo`)."""
    first, *others = [_first_family(space.school) for space in spaces]
    if first is None:
        return None
    primary = next(g for g in first.guardians.all() if g.is_primary)
    other = next((family for family in others if family is not None), None)
    return DemoPortal(
        normalize_phone(primary.phone), f"{other.code[:4]}-{other.code[4:]}" if other else None
    )


def create_demo_portal(spaces: list[DemoSpace]) -> None:
    """Le tuteur principal de la première famille du premier espace a un compte du portail (mot
    de passe de l'espace), relié à sa fiche, accès rétabli. Dans les espaces remplis avec lui
    (`make demo`), la fiche de la même famille reste à ajouter avec son code."""
    first, *others = [_first_family(space.school) for space in spaces]
    if first is None:
        return
    primary = next(g for g in first.guardians.all() if g.is_primary)
    phone, password = normalize_phone(primary.phone), spaces[0].password
    user = User.objects.filter(phone=phone).first()
    if user is None:
        user = User.objects.create_user(phone, password, last_name=primary.full_name[:100])
    else:
        user.is_active = True
        set_demo_password(user, password)
        user.save(update_fields=["is_active", "password", "updated_at"])
    Family.all_schools.filter(primary_user=user).exclude(pk=first.pk).update(
        primary_user=None, activated_at=None
    )
    Family.all_schools.filter(
        pk__in=[first.pk, *(family.pk for family in others if family is not None)]
    ).update(code_expires_at=None, portal_suspended_at=None)
    Family.all_schools.filter(pk=first.pk).update(
        primary_user=user, activated_at=first.activated_at or timezone.now()
    )


# Part des familles qui ont déjà activé leur compte du portail (H7), différente selon la classe.
DEMO_ACTIVATED_SHARE = 0.35


def create_demo_activations(spaces: list[DemoSpace]) -> None:
    """Environ une famille sur trois a activé son compte depuis la rentrée (suivi des
    invitations, 4.9) ; une seule fois par espace. Comptes sans mot de passe utilisable."""
    for space in spaces:
        with use_school(space.school):
            _activate(space.school)


def _activate(school: School) -> None:
    first = _first_family(school)
    families = Family.objects.exclude(pk=first.pk if first else None)
    # Déjà fait (quelques activations faites à la main pendant les essais ne comptent pas).
    if families.filter(activated_at__isnull=False).count() > families.count() / 6:
        return
    draw, now = random.Random(f"activations-{school.code}"), timezone.now()
    drawn = {}
    waiting = families.filter(activated_at=None, portal_suspended_at=None)
    for family in waiting.prefetch_related("guardians"):
        primary = next((g for g in family.guardians.all() if g.is_primary), None)
        if primary is None or not primary.phone or draw.random() > DEMO_ACTIVATED_SHARE:
            continue
        try:
            phone = normalize_phone(primary.phone)
        except InvalidPhoneError:
            continue
        # Jamais le numéro d'une vraie personne, saisi en essayant l'application.
        if phone in drawn or not is_demo_phone(phone):
            continue
        when = now - timedelta(days=draw.randint(0, 30), hours=draw.randint(0, 9))
        drawn[phone] = (family, primary, when)
    # Seulement les numéros tirés : pas tous les comptes de la plateforme.
    taken = set(User.objects.filter(phone__in=drawn).values_list("phone", flat=True))
    password = make_password(None)
    chosen = []
    for phone, (family, primary, when) in drawn.items():
        if phone not in taken:
            family.primary_user = User(
                phone=phone, password=password, last_name=primary.full_name[:100]
            )
            family.activated_at = when
            chosen.append(family)
    User.objects.bulk_create([family.primary_user for family in chosen])
    Family.objects.bulk_update(chosen, ["primary_user", "activated_at"], batch_size=500)


# Ce que trois parents de l'ITIG ont envoyé (adresses et numéros fictifs).
DEMO_CONTACT_CHANGES = [
    {"address": {"commune": "Goma", "quartier": "Himbi", "avenue": "Lukanga", "number": "7"}},
    {"email": "j.sivihwa@exemple.cd"},
    {"emergency_contact": {"full_name": "Amani Pierre", "phone": "+243815539071"}},
]


def create_demo_contact_changes(spaces: list[DemoSpace]) -> None:
    """Profil `itig` seulement, une seule fois."""
    for space in spaces:
        with use_school(space.school):
            if space.profile != "itig" or ContactChange.objects.exists():
                continue
            families = Family.objects.order_by("created_at", "id")
            for family, sent in zip(
                families[1 : 1 + len(DEMO_CONTACT_CHANGES)], DEMO_CONTACT_CHANGES, strict=False
            ):
                before = contact_changes.current(family)
                changes = {name: {"before": before[name], "after": sent[name]} for name in sent}
                ContactChange.objects.create(family=family, changes=changes)
