"""Comptes fictifs d'un espace de démonstration (`docs/07-a-fournir.md` § 4) : un par rôle pour
le profil `itig`, quelques-uns pour `volcans`, un enseignant dans les deux écoles de `make demo`,
et, en développement seulement, un super-admin.

Numéros dans la plage réservée (`phone.is_demo_phone`) : ces comptes ne peuvent pas être ceux de
vraies personnes. Noms inventés. Les téléphones écrits ici sont ceux de `make demo` ; un autre
espace a les mêmes comptes dans ses propres numéros (`DemoSpace.numbers`). Le mot de passe et la
clé de double authentification de développement ne sont pas des secrets : ils ne servent qu'en
développement ; ailleurs, chaque espace a son mot de passe, et aucune clé.
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import LoginFailure, Membership, Role, User
from apps.accounts.roles import SYSTEM_ROLES, TOTP_PERMISSIONS
from apps.accounts.services import create_system_roles
from apps.core.crypto import encrypt
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace

DEMO_PASSWORD = "mwangaza-demo"
# Développement : un espace de démonstration ne demande pas la double authentification, mais les
# comptes dont le rôle l'exigerait ailleurs (directeur, comptable, caissier) gardent une clé
# commune, pour essayer la connexion en deux étapes : à ajouter une fois dans une application
# d'authentification, ou `make totp`. Jamais hors développement (`demo_password`).
DEMO_TOTP_SECRET = "MWANGAZADEMOTOTPMWANGAZADEMOTOTP"


def demo_password() -> str:
    """Mot de passe des comptes de `make demo` : celui du serveur (`DJANGO_DEMO_PASSWORD`,
    4.6.2), sinon celui du dépôt, connu de tous."""
    return settings.DEMO_PASSWORD or DEMO_PASSWORD


def set_demo_password(user: User, password: str) -> None:
    """Sans toucher au mot de passe qui est déjà le bon : un nouveau hachage fermerait toutes les
    sessions du compte à chaque `make demo` (Gestion et Portail déconnectés)."""
    if not user.check_password(password):
        user.set_password(password)


PLATFORM_ADMIN_PHONE = "+243000000000"

# Rôle propre au profil `itig` (Q7) : un rôle créé par l'école, pas un rôle du code.
WORKSHOP_HEAD = "Chef d'atelier"
CASH_DESK_PC = "PC Caisse · Windows · Edge"
CUSTOM_ROLES = {"itig": {WORKSHOP_HEAD: ["students.view"]}}


@dataclass(frozen=True)
class DemoAccount:
    phone: str
    last_name: str
    middle_name: str
    first_name: str
    # Profil → rôle : code d'un rôle système, ou nom d'un rôle de l'école.
    roles: dict[str, str]
    description: str
    # Développement : pas de clé commune pour ce compte, il se connecte sans code, comme dans un
    # espace créé depuis la console.
    no_code: bool = False
    # Poste fictif du compte dans « Appareils connectés » (`sync/demo.py`).
    device: str = ""


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
    DemoAccount(
        "+243000001005",
        "Kahindo",
        "Sivira",
        "Grâce",
        {"itig": "cashier"},
        "caissière",
        device=CASH_DESK_PC,
    ),
    DemoAccount(
        "+243000001006",
        "Nzigire",
        "Bora",
        "Solange",
        {"itig": "secretary"},
        "secrétaire",
        device="PC Secrétariat · Windows",
    ),
    DemoAccount(
        "+243000001007",
        "Musubao",
        "Kyakimwa",
        "Albert",
        {"itig": "promoter"},
        "promoteur",
        no_code=True,
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
        "+243000002005",
        "Cishugi",
        "Mulume",
        "Espérance",
        {"volcans": "cashier"},
        "caissière",
        device=CASH_DESK_PC,
    ),
]


def _reset_roles(space: DemoSpace) -> dict[str, Role]:
    """Rôles système remis à leurs permissions par défaut, rôles de démonstration du profil."""
    create_system_roles(space.school)
    roles = {}
    with use_school(space.school):
        for role in Role.objects.exclude(code=""):
            role.name = ""
            role.permissions = list(SYSTEM_ROLES[role.code].permissions)
            role.save()
            roles[role.code] = role
        for name, permissions in CUSTOM_ROLES.get(space.profile, {}).items():
            roles[name], _created = Role.objects.update_or_create(
                name=name, defaults={"permissions": permissions}
            )
    return roles


def _account(phone: str, password: str, **fields) -> User:
    user = User.objects.filter(phone=phone).first() or User(phone=phone)
    for field, value in fields.items():
        setattr(user, field, value)
    user.is_active = True
    user.must_change_password = False
    set_demo_password(user, password)
    user.save()
    return user


def create_demo_admin() -> User | None:
    """Super-admin fictif, en développement seulement (`DEBUG`) : son mot de passe et sa clé sont
    écrits dans le dépôt. Ailleurs il n'existe pas : celui qu'un ancien `make demo` a créé perd
    ses droits et son accès (le vrai super-admin se crée par `createsuperuser`)."""
    if not settings.DEBUG:
        former = User.objects.filter(phone=PLATFORM_ADMIN_PHONE).first()
        if former is not None:
            services.reset_totp(former)
            former.is_platform_admin = former.is_active = False
            former.save(update_fields=["is_platform_admin", "is_active", "updated_at"])
        return None
    LoginFailure.objects.filter(phone=PLATFORM_ADMIN_PHONE).delete()
    admin = _account(
        PLATFORM_ADMIN_PHONE,
        demo_password(),
        last_name="Mwangaza",
        first_name="Admin",
        is_platform_admin=True,
    )
    # Double authentification obligatoire pour le super-admin (console, administration Django).
    _set_demo_totp(admin, shared_key=True)
    return admin


def demo_accounts(space: DemoSpace) -> list[DemoAccount]:
    """Les comptes d'exemple du profil de `space` (leur numéro : `space.numbers.of(phone)`)."""
    return [account for account in DEMO_ACCOUNTS if space.profile in account.roles]


def create_demo_accounts(spaces: list[DemoSpace]) -> None:
    """Crée ou remet à jour les comptes de démonstration et leurs rôles. Ce que l'utilisateur a
    ajouté en essayant l'application (autres comptes, autres rôles) n'est pas effacé ; les
    connexions de ces comptes bloquées par des essais ratés sont débloquées."""
    for space in spaces:
        roles, accounts = _reset_roles(space), demo_accounts(space)
        phones = [space.numbers.of(demo.phone) for demo in accounts]
        LoginFailure.objects.filter(phone__in=phones).delete()
        for demo, phone in zip(accounts, phones, strict=True):
            user = _account(
                phone,
                space.password,
                last_name=demo.last_name,
                middle_name=demo.middle_name,
                first_name=demo.first_name,
            )
            role = roles[demo.roles[space.profile]]
            membership, _created = Membership.objects.update_or_create(
                user=user, school=space.school, defaults={"is_active": True}
            )
            with use_school(space.school):
                membership.roles.set([role])
            sensitive = bool(TOTP_PERMISSIONS.intersection(role.permissions))
            _set_demo_totp(
                user, shared_key=space.shared_totp_key and sensitive and not demo.no_code
            )


def _set_demo_totp(user: User, *, shared_key: bool) -> None:
    """La clé commune du développement, ou aucune : une clé liée par un visiteur à un compte que
    tous partagent est retirée (un espace de démonstration ne demande pas de code)."""
    services.reset_totp(user)
    if shared_key:
        user.totp_secret = encrypt(DEMO_TOTP_SECRET)
        user.totp_enabled_at = timezone.now()
        user.save(update_fields=["totp_secret", "totp_enabled_at", "updated_at"])
