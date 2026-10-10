"""Comptes fictifs de `make demo` (`docs/07-a-fournir.md` § 4) : un par rôle à l'ITIG de
démonstration, quelques-uns à Volcans, un enseignant dans les deux écoles, un super-admin.

Numéros en +243 0… : aucun numéro réel ne commence par 0 après l'indicatif, ces comptes ne
peuvent donc pas être ceux de vraies personnes. Noms inventés. Le mot de passe et la clé de
double authentification de développement ne sont pas des secrets : `make demo` est refusé hors
développement et des essais ; le serveur de démonstration en ligne a son propre mot de passe.
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import LoginFailure, Membership, Role, User
from apps.accounts.roles import SYSTEM_ROLES
from apps.accounts.services import create_system_roles
from apps.core.crypto import DecryptionError, decrypt, encrypt
from apps.core.tenancy import use_school
from apps.schools.models import School

DEMO_PASSWORD = "mwangaza-demo"
# Double authentification des comptes qui l'exigent (directeur, comptable, caissier) : une seule
# clé, à ajouter une fois dans une application d'authentification ; ou `make totp`. Jamais sur le
# serveur de démonstration en ligne (`demo_password`).
DEMO_TOTP_SECRET = "MWANGAZADEMOTOTPMWANGAZADEMOTOTP"


def demo_password() -> str:
    """Mot de passe des comptes fictifs : celui du serveur de démonstration en ligne
    (`DJANGO_DEMO_PASSWORD`, 4.6.2), sinon celui du dépôt, connu de tous."""
    return settings.DEMO_PASSWORD or DEMO_PASSWORD


def set_demo_password(user: User) -> None:
    """Sans toucher au mot de passe qui est déjà le bon : un nouveau hachage fermerait toutes les
    sessions du compte à chaque `make demo` (Gestion et Portail déconnectés)."""
    if not user.check_password(demo_password()):
        user.set_password(demo_password())


PLATFORM_ADMIN_PHONE = "+243000000000"

# Rôle propre à l'ITIG de démonstration (Q7) : un rôle créé par l'école, pas un rôle du code.
WORKSHOP_HEAD = "Chef d'atelier"
CUSTOM_ROLES = {"itig": {WORKSHOP_HEAD: ["students.view"]}}


@dataclass(frozen=True)
class DemoAccount:
    phone: str
    last_name: str
    middle_name: str
    first_name: str
    # École → rôle : code d'un rôle système, ou nom d'un rôle de l'école.
    roles: dict[str, str]
    description: str
    # Rôle qui exige la double authentification, pas encore activée : pour essayer l'activation.
    totp_to_enable: bool = False


DEMO_ACCOUNTS = [
    DemoAccount("+243000001001", "Kambale", "Muhindo", "Patrice", {"itig": "head"}, "directeur"),
    DemoAccount(
        "+243000001002",
        "Kavugho",
        "Mbambu",
        "Esther",
        {"itig": "study_director"},
        "directrice des études",
    ),
    DemoAccount(
        "+243000001003",
        "Vagheni",
        "Kasongo",
        "Jonas",
        {"itig": "discipline_master"},
        "directeur de discipline",
    ),
    DemoAccount("+243000001004", "Mbusa", "Kitsa", "Didier", {"itig": "accountant"}, "comptable"),
    DemoAccount("+243000001005", "Kahindo", "Sivira", "Grâce", {"itig": "cashier"}, "caissière"),
    DemoAccount("+243000001006", "Nzigire", "Bora", "Solange", {"itig": "secretary"}, "secrétaire"),
    DemoAccount(
        "+243000001007",
        "Musubao",
        "Kyakimwa",
        "Albert",
        {"itig": "promoter"},
        "promoteur",
        totp_to_enable=True,
    ),
    DemoAccount(
        "+243000001008",
        "Katembo",
        "Siku",
        "Olivier",
        {"itig": "teacher", "volcans": "teacher"},
        "enseignant dans les deux écoles",
    ),
    DemoAccount("+243000001009", "Bahavu", "Neema", "Claudine", {"itig": "parent"}, "parent"),
    DemoAccount(
        "+243000001010", "Paluku", "Mathe", "Benjamin", {"itig": WORKSHOP_HEAD}, "chef d'atelier"
    ),
    DemoAccount("+243000002001", "Mapendo", "Rukara", "Josué", {"volcans": "head"}, "directeur"),
    DemoAccount(
        "+243000002004", "Byamungu", "Nabintu", "Pascal", {"volcans": "accountant"}, "comptable"
    ),
    DemoAccount(
        "+243000002005", "Cishugi", "Mulume", "Espérance", {"volcans": "cashier"}, "caissière"
    ),
]


def _reset_roles(school: School) -> dict[str, Role]:
    """Rôles système remis à leurs permissions par défaut, rôles de démonstration de l'école."""
    create_system_roles(school)
    roles = {}
    with use_school(school):
        for role in Role.objects.exclude(code=""):
            role.name = ""
            role.permissions = list(SYSTEM_ROLES[role.code].permissions)
            role.save()
            roles[role.code] = role
        for name, permissions in CUSTOM_ROLES.get(school.code, {}).items():
            roles[name], _created = Role.objects.update_or_create(
                name=name, defaults={"permissions": permissions}
            )
    return roles


def _account(phone: str, **fields) -> User:
    user = User.objects.filter(phone=phone).first() or User(phone=phone)
    for field, value in fields.items():
        setattr(user, field, value)
    user.is_active = True
    user.must_change_password = False
    set_demo_password(user)
    user.save()
    return user


def create_demo_accounts(schools: dict[str, School]) -> list[DemoAccount]:
    """Crée ou remet à jour les comptes de démonstration et leurs rôles. Ce que l'utilisateur a
    ajouté en essayant l'application (autres comptes, autres rôles) n'est pas effacé ; les
    connexions bloquées par des essais ratés sont débloquées."""
    LoginFailure.objects.all().delete()
    roles = {code: _reset_roles(school) for code, school in schools.items()}
    admin = _account(
        PLATFORM_ADMIN_PHONE, last_name="Mwangaza", first_name="Admin", is_platform_admin=True
    )
    # Double authentification obligatoire pour le super-admin (administration Django, 1.5).
    _set_demo_totp(admin, enabled=True)
    for demo in DEMO_ACCOUNTS:
        user = _account(
            demo.phone,
            last_name=demo.last_name,
            middle_name=demo.middle_name,
            first_name=demo.first_name,
        )
        for school_code, role_key in demo.roles.items():
            school = schools[school_code]
            membership, _created = Membership.objects.update_or_create(
                user=user, school=school, defaults={"is_active": True}
            )
            with use_school(school):
                membership.roles.set([roles[school_code][role_key]])
        _set_demo_totp(user, enabled=services.totp_required(user) and not demo.totp_to_enable)
    return DEMO_ACCOUNTS


def _set_demo_totp(user: User, *, enabled: bool) -> None:
    if settings.DEMO_PASSWORD:
        # Serveur en ligne : pas de clé commune, écrite dans le dépôt ; chaque compte lie sa
        # propre application à la première connexion et la garde quand `make demo` est relancé.
        if _has_shared_key(user):
            services.reset_totp(user)
        return
    services.reset_totp(user)
    if enabled:
        user.totp_secret = encrypt(DEMO_TOTP_SECRET)
        user.totp_enabled_at = timezone.now()
        user.save(update_fields=["totp_secret", "totp_enabled_at", "updated_at"])


def _has_shared_key(user: User) -> bool:
    try:
        return user.totp_enabled and decrypt(user.totp_secret) == DEMO_TOTP_SECRET
    except DecryptionError:
        return False
