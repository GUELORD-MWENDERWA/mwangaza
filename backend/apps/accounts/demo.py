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
from apps.accounts.platform_roles import OWNER
from apps.accounts.roles import STARTER_ROLES, TOTP_PERMISSIONS, starter_role_name
from apps.core.crypto import encrypt
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace, demo_signature

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
# Équipe fictive de la plateforme (EQ.1), un compte par rôle autre que propriétaire : numéro →
# (rôle, prénom).
DEMO_TEAM = {
    "+243000000001": ("technical", "Technique"),
    "+243000000002": ("support", "Support"),
    "+243000000003": ("commercial", "Commercial"),
    "+243000000004": ("communication", "Communication"),
    "+243000000005": ("finance", "Finance"),
}
PLATFORM_PHONES = [PLATFORM_ADMIN_PHONE, *DEMO_TEAM]

# Chaque école fictive nomme ses rôles à sa façon : ceux du modèle de départ qu'elle a renommés
# (clé du modèle → son nom), et ceux qu'elle a créés (Q7 : nom → permissions).
ROLE_NAMES = {"itig": {"head": "Préfet des études"}, "volcans": {"cashier": "Caissière"}}
WORKSHOP_HEAD = "Chef d'atelier"
CUSTOM_ROLES = {"itig": {WORKSHOP_HEAD: ["students.view"]}}
CASH_DESK_PC = "PC Caisse · Windows · Edge"


@dataclass(frozen=True)
class DemoAccount:
    phone: str
    last_name: str
    middle_name: str
    first_name: str
    # Profil → rôle : clé du modèle de départ, ou nom d'un rôle créé par l'école.
    roles: dict[str, str]
    description: str
    # Développement : pas de clé commune pour ce compte, il se connecte sans code, comme dans un
    # espace créé depuis la console.
    no_code: bool = False
    # Poste fictif du compte dans « Appareils connectés » (`sync/demo.py`).
    device: str = ""
    # Écrit un par un dans la liste de `make demo` ; les enseignants de `TEACHER_POOL` sont
    # résumés en une ligne.
    listed: bool = True


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


# Enseignants de l'ITIG de démonstration (demandé le 2026-10-27 : chaque cours a son
# enseignant, comme dans une vraie école) : `+243 000 001 101` à `…140`, noms inventés.
# `academics/demo.py` leur répartit les cours sans enseignant, 24 h par semaine au plus.
POOL_SIZE = 40
POOL_LAST = (
    "Kahindo",
    "Mumbere",
    "Kavira",
    "Masika",
    "Muhindo",
    "Kasereka",
    "Kambale",
    "Mbusa",
    "Kakule",
    "Paluku",
    "Sikuli",
    "Vahwere",
    "Kyakimwa",
    "Bahati",
    "Musubao",
    "Ngoy",
    "Ilunga",
    "Mutombo",
    "Lukusa",
    "Tshibangu",
    "Kalala",
    "Mwamba",
    "Bisimwa",
    "Cirhuza",
)
POOL_MIDDLE = ("Mathe", "Kasoki", "Kitsa", "Siku", "Kavugho", "Ndungo", "Mughole", "Zawadi")
POOL_FIRST = (
    "Jean-Marie",
    "Esther",
    "Pascal",
    "Rachel",
    "Emmanuel",
    "Furaha",
    "Daniel",
    "Grâce",
    "Jérémie",
    "Solange",
    "Moïse",
    "Béatrice",
    "Patient",
    "Annie",
    "Josué",
    "Nadine",
    "Héritier",
    "Clarisse",
)
TEACHER_POOL = [
    DemoAccount(
        f"+243000001{101 + index}",
        POOL_LAST[index % len(POOL_LAST)],
        POOL_MIDDLE[index % len(POOL_MIDDLE)],
        POOL_FIRST[index % len(POOL_FIRST)],
        {"itig": "teacher"},
        "enseignant",
        listed=False,
    )
    for index in range(POOL_SIZE)
]
DEMO_ACCOUNTS += TEACHER_POOL


def _reset_roles(space: DemoSpace) -> dict[str, Role]:
    """Rôles du profil : ceux du modèle de départ, sous le nom que l'école fictive leur donne et
    avec leurs permissions de départ, puis ceux qu'elle a créés. Un rôle que le visiteur a renommé
    n'est pas retrouvé : il reste tel quel, et celui de la démonstration est recréé."""
    renamed = ROLE_NAMES.get(space.profile, {})
    roles = {}
    with use_school(space.school):
        # Sans casse, comme l'unicité du nom dans l'école.
        existing = {role.name.lower(): role for role in Role.objects.all()}
        for key, starter in STARTER_ROLES.items():
            default = starter_role_name(key)
            name = renamed.get(key, default)
            role = existing.get(name.lower()) or existing.get(default.lower()) or Role()
            role.name, role.permissions = name, list(starter.permissions)
            role.save()
            roles[key] = role
        for name, permissions in CUSTOM_ROLES.get(space.profile, {}).items():
            role = existing.get(name.lower()) or Role()
            role.name, role.permissions = name, permissions
            role.save()
            roles[name] = role
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
    """Propriétaire fictif de la plateforme et un membre fictif par autre rôle de l'équipe
    (`DEMO_TEAM`), en développement seulement (`DEBUG`) : leur mot de passe et leur clé sont écrits
    dans le dépôt. Ailleurs ils n'existent pas : ceux qu'un ancien `make demo` a créés perdent
    leurs droits et leur accès (le vrai propriétaire se crée par `createsuperuser`)."""
    if not settings.DEBUG:
        for former in User.objects.filter(phone__in=PLATFORM_PHONES):
            services.reset_totp(former)
            former.is_platform_admin = former.is_active = False
            former.platform_roles = []
            former.save(
                update_fields=["is_platform_admin", "is_active", "platform_roles", "updated_at"]
            )
        return None
    LoginFailure.objects.filter(phone__in=PLATFORM_PHONES).delete()
    admin = _account(
        PLATFORM_ADMIN_PHONE,
        demo_password(),
        last_name="Mwangaza",
        first_name="Admin",
        is_platform_admin=True,
        platform_roles=[OWNER],
    )
    # Double authentification obligatoire pour toute l'équipe (console, administration Django).
    _set_demo_totp(admin, shared_key=True)
    for phone, (role, first_name) in DEMO_TEAM.items():
        member = _account(
            phone,
            demo_password(),
            last_name="Équipe",
            first_name=first_name,
            is_platform_admin=True,
            platform_roles=[role],
        )
        _set_demo_totp(member, shared_key=True)
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
            if membership.signature:
                membership.signature.delete(save=False)
            membership.signature.save(
                "signature.png", demo_signature(sum(map(int, filter(str.isdigit, phone))))
            )
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
