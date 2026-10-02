"""Portail de démonstration (H2) : la famille qui a des enfants dans les deux écoles a un compte
relié à sa fiche de l'ITIG ; sa fiche des Volcans reste à ajouter avec son code (« Ajouter un
enfant d'une autre école »). `make demo` les remet ainsi, accès rétablis. Trois coordonnées
envoyées par des parents attendent le secrétariat de l'ITIG (H5), une seule fois."""

from dataclasses import dataclass

from django.utils import timezone

from apps.accounts.demo import DEMO_PASSWORD
from apps.accounts.models import User
from apps.accounts.phone import normalize_phone
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
        user = User.objects.create_user(phone, DEMO_PASSWORD, last_name=primary.full_name[:100])
    else:
        user.set_password(DEMO_PASSWORD)
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
