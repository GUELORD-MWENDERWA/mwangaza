"""Portail de démonstration (H2) : la famille qui a des enfants dans les deux écoles a un compte
relié à sa fiche de l'ITIG ; sa fiche des Volcans reste à ajouter avec son code (« Ajouter un
enfant d'une autre école »). `make demo` les remet ainsi, accès rétablis. Trois coordonnées
envoyées par des parents attendent le secrétariat de l'ITIG (H5), une seule fois."""

import random
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.demo import demo_password
from apps.accounts.models import User
from apps.accounts.phone import InvalidPhoneError, normalize_phone
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students import contact_changes
from apps.students.models import ContactChange, Family


@dataclass
class DemoPortal:
    phone: str
    code_to_add: str


def _first_family(school: School) -> Family:
    # La famille partagée est la première créée dans chaque école (`students.demo`).
    with use_school(school):
        return Family.objects.prefetch_related("guardians").order_by("created_at", "id").first()


def create_demo_portal(schools: dict[str, School]) -> DemoPortal | None:
    itig, volcans = _first_family(schools["itig"]), _first_family(schools["volcans"])
    if itig is None or volcans is None:
        return None
    primary = next(g for g in itig.guardians.all() if g.is_primary)
    phone = normalize_phone(primary.phone)
    user = User.objects.filter(phone=phone).first()
    if user is None:
        user = User.objects.create_user(phone, demo_password(), last_name=primary.full_name[:100])
    else:
        user.set_password(demo_password())
        user.save(update_fields=["password", "updated_at"])
    Family.all_schools.filter(primary_user=user).exclude(pk=itig.pk).update(
        primary_user=None, activated_at=None
    )
    Family.all_schools.filter(pk__in=[itig.pk, volcans.pk]).update(
        code_expires_at=None, portal_suspended_at=None
    )
    Family.all_schools.filter(pk=itig.pk).update(
        primary_user=user, activated_at=itig.activated_at or timezone.now()
    )
    return DemoPortal(phone, f"{volcans.code[:4]}-{volcans.code[4:]}")


# Part des familles qui ont déjà activé leur compte du portail (H7), différente selon la classe.
DEMO_ACTIVATED_SHARE = 0.35


def create_demo_activations(school: School) -> None:
    """Environ une famille sur trois a activé son compte depuis la rentrée (suivi des
    invitations, 4.9) ; une seule fois par école. Comptes sans mot de passe utilisable."""
    with use_school(school):
        first = _first_family(school)
        families = Family.objects.exclude(pk=first.pk if first else None)
        # Déjà fait (quelques activations faites à la main pendant les essais ne comptent pas).
        if families.filter(activated_at__isnull=False).count() > families.count() / 6:
            return
        draw, now = random.Random(f"activations-{school.code}"), timezone.now()
        taken = set(User.objects.values_list("phone", flat=True))
        password = make_password(None)
        chosen = []
        waiting = families.filter(activated_at=None, portal_suspended_at=None)
        for family in waiting.prefetch_related("guardians"):
            primary = next((g for g in family.guardians.all() if g.is_primary), None)
            if primary is None or not primary.phone or draw.random() > DEMO_ACTIVATED_SHARE:
                continue
            try:
                phone = normalize_phone(primary.phone)
            except InvalidPhoneError:
                continue
            if phone in taken:
                continue
            taken.add(phone)
            family.primary_user = User(
                phone=phone, password=password, last_name=primary.full_name[:100]
            )
            family.activated_at = now - timedelta(
                days=draw.randint(0, 30), hours=draw.randint(0, 9)
            )
            chosen.append(family)
        User.objects.bulk_create([family.primary_user for family in chosen])
        Family.objects.bulk_update(chosen, ["primary_user", "activated_at"], batch_size=500)


# Ce que trois parents de l'ITIG ont envoyé (adresses et numéros fictifs).
DEMO_CONTACT_CHANGES = [
    {"address": {"commune": "Goma", "quartier": "Himbi", "avenue": "Lukanga", "number": "7"}},
    {"email": "j.sivihwa@exemple.cd"},
    {"emergency_contact": {"full_name": "Amani Pierre", "phone": "+243815539071"}},
]


def create_demo_contact_changes(school: School) -> None:
    with use_school(school):
        if ContactChange.objects.exists():
            return
        families = Family.objects.order_by("created_at", "id")[1 : 1 + len(DEMO_CONTACT_CHANGES)]
        for family, sent in zip(families, DEMO_CONTACT_CHANGES, strict=False):
            before = contact_changes.current(family)
            changes = {name: {"before": before[name], "after": sent[name]} for name in sent}
            ContactChange.objects.create(family=family, changes=changes)
