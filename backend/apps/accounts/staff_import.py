"""Import du personnel depuis Excel (R.1) et lettres d'accès.

Comme la reprise des résultats (8.4.7) : ni table ni tâche de fond. `check` lit le fichier et
rend l'aperçu ; à la validation, le même fichier est renvoyé et `record` le vérifie de nouveau
sous verrou, puis crée tout d'un bloc. Une ligne déjà dans l'école est ignorée : un fichier envoyé
deux fois ne crée rien deux fois. L'aperçu ne dit jamais si un numéro a déjà un compte ailleurs
(B3) ; après l'enregistrement, « compte existant » comme pour l'ajout d'une seule personne.

Un nouveau compte n'a pas de mot de passe utilisable : `letters` lui en donne un, provisoire, au
moment d'imprimer sa lettre d'accès (comme le code famille des invitations, H7). Rien n'est donc
haché pendant l'import (Argon2, un à la fois par processus), et une lettre perdue se réimprime.
"""

import re
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Membership, Role, User
from apps.accounts.phone import (
    InvalidPhoneError,
    demo_block,
    format_phone,
    is_demo_phone,
    normalize_phone,
)
from apps.accounts.services import _role_summaries, _sensitive, make_temporary_password
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import qr_code, school_header, workbook
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.notifications import events
from apps.schools.models import Demonstration, School
from apps.students import imports

# Une école compte quelques dizaines de personnes ; au-delà, deux fichiers.
MAX_ROWS = 150
# Une lettre hache un mot de passe (≈ 0,2 s sur le serveur) : 50 par PDF.
MAX_LETTERS = 50

TITLES = {
    "last_name": {"nom", "lastname", "surname", "name"},
    "middle_name": {"postnom", "middlename"},
    "first_name": {"prenom", "firstname"},
    "phone": {"telephone", "tel", "phone", "numero", "numerodetelephone", "phonenumber"},
    "roles": {"role", "roles", "fonction", "fonctions"},
}
ROLE_SEPARATORS = re.compile(r"[,;]")

READY, SKIPPED, ERROR = "ready", "skipped", "error"

MISSING_COLUMN = ApiError(
    "missing_column",
    _("The file needs a last name, a phone and a role column: use the template."),
    400,
)
TOO_MANY_STAFF = ApiError(
    "too_many_staff",
    _("The file has more than 150 people: split it into two files."),
    400,
)
NOTHING_TO_RECORD = ApiError("nothing_to_record", _("No row can be recorded."), 409)
PREVIEW_OUTDATED = ApiError(
    "preview_outdated",
    _("The file, the roles or the staff changed since the preview: check it again."),
    409,
)
NO_LETTER = ApiError(
    "no_letter",
    _(
        "None of these people needs an access letter: they have already signed in, or their "
        "account is also used outside this school."
    ),
    409,
)


@dataclass
class Line:
    """Une ligne du fichier : prête, ignorée (déjà dans l'école) ou en erreur (`issues`, codes
    traduits par l'écran)."""

    number: int
    last_name: str
    middle_name: str
    first_name: str
    phone_text: str
    roles_text: str
    phone: str = ""
    roles: list[Role] = field(default_factory=list)
    status: str = READY
    issues: list[dict] = field(default_factory=list)

    @property
    def name(self) -> str:
        return " ".join(
            part for part in (self.last_name, self.middle_name, self.first_name) if part
        )

    def refuse(self, code: str, **params) -> None:
        self.status = ERROR
        self.issues.append({"code": code, **params})


@dataclass
class Preview:
    lines: list[Line]
    # Après l'enregistrement : chaque personne ajoutée.
    added: list[dict] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(line.status == status for line in self.lines)


def _read(file) -> list[Line]:
    _sheet, headers, rows = imports.read_file(file, set().union(*TITLES.values()))
    keys = [imports._key(header) for header in headers]
    columns = {
        name: next((i for i, key in enumerate(keys) if key in titles), None)
        for name, titles in TITLES.items()
    }
    if any(columns[name] is None for name in ("last_name", "phone", "roles")):
        raise BusinessError(MISSING_COLUMN)
    if len(rows) > MAX_ROWS:
        raise BusinessError(TOO_MANY_STAFF)

    def cell(cells: list[str], name: str) -> str:
        index = columns[name]
        return cells[index].strip() if index is not None and index < len(cells) else ""

    return [Line(number, *(cell(cells, name) for name in TITLES)) for number, cells in rows]


def _check(lines: list[Line], school: School) -> None:
    """Statut de chaque ligne. Trois requêtes, quel que soit le nombre de lignes."""
    roles = {imports._key(role.name): role for role in Role.objects.all()}
    seen: dict[str, int] = {}
    for line in lines:
        if not line.last_name:
            line.refuse("missing_name")
        if not line.phone_text:
            line.refuse("missing_phone")
        else:
            try:
                line.phone = normalize_phone(line.phone_text)
            except InvalidPhoneError:
                line.refuse("invalid_phone")
        if line.phone:
            if school.is_demo and not is_demo_phone(line.phone):
                line.refuse("demo_space_number")
            elif is_demo_phone(line.phone) and not school.is_demo:
                line.refuse("demo_number")
            elif line.phone in seen:
                line.refuse("duplicate_phone", line=seen[line.phone])
            else:
                seen[line.phone] = line.number
        names = [name.strip() for name in ROLE_SEPARATORS.split(line.roles_text) if name.strip()]
        if not names:
            line.refuse("missing_role")
        for name in names:
            role = roles.get(imports._key(name))
            if role is None:
                line.refuse("unknown_role", role=name)
            elif role not in line.roles:
                line.roles.append(role)
    members = set(
        Membership.objects.filter(school=school, user__phone__in=list(seen)).values_list(
            "user__phone", flat=True
        )
    )
    for line in lines:
        # Rien ne sera écrit pour cette personne : ses autres problèmes n'importent plus.
        if line.phone in members and seen.get(line.phone) == line.number:
            line.status, line.issues = SKIPPED, [{"code": "already_member"}]


def check(file) -> Preview:
    """Aperçu d'un fichier : rien n'est écrit."""
    lines = _read(file)
    _check(lines, require_current_school())
    return Preview(lines)


def _letter_needed(user: User, used_elsewhere: bool) -> bool:
    """Lettre d'accès possible : le compte n'a jamais servi, et l'école peut changer son mot de
    passe (il ne sert dans aucune autre école, `services.account_managed_by`)."""
    return user.last_login is None and not used_elsewhere and not user.is_platform_admin


def record(file, *, actor: User, expected: int) -> Preview:
    """Ajoute les lignes prêtes d'un bloc ; les autres sont laissées. `expected` : nombre de
    lignes prêtes de l'aperçu validé ; 409 `preview_outdated` s'il a changé."""
    school = require_current_school()
    lines = _read(file)
    with transaction.atomic():
        # Deux imports à la fois dans la même école attendent leur tour.
        School.objects.select_for_update().filter(pk=school.pk).first()
        _check(lines, school)
        preview = Preview(lines)
        ready = [line for line in lines if line.status == READY]
        if not ready:
            raise BusinessError(NOTHING_TO_RECORD)
        if len(ready) != expected:
            raise BusinessError(PREVIEW_OUTDATED)

        users = {
            user.phone: user for user in User.objects.filter(phone__in=[x.phone for x in ready])
        }
        elsewhere = set(
            Membership.objects.filter(user__in=users.values()).values_list("user_id", flat=True)
        )
        new = []
        for line in ready:
            if line.phone not in users:
                user = User(
                    phone=line.phone,
                    last_name=line.last_name,
                    middle_name=line.middle_name,
                    first_name=line.first_name,
                    must_change_password=True,
                    created_by=actor,
                )
                user.set_unusable_password()
                users[line.phone] = user
                new.append(user)
        User.objects.bulk_create(new)
        created = {user.phone for user in new}

        memberships = [
            Membership(user=users[line.phone], school=school, created_by=actor) for line in ready
        ]
        Membership.objects.bulk_create(memberships)
        Membership.roles.through.objects.bulk_create(
            [
                Membership.roles.through(membership_id=membership.pk, role_id=role.pk)
                for membership, line in zip(memberships, ready, strict=True)
                for role in line.roles
            ]
        )
        audit.record_many(
            Action.STAFF_ADDED,
            [
                (
                    membership,
                    {
                        "roles": _role_summaries(line.roles),
                        "new_account": line.phone in created,
                        "file": file.name[:120],
                    },
                )
                for membership, line in zip(memberships, ready, strict=True)
            ],
            actor=actor,
            label=lambda membership: str(membership.user),
        )
        for membership, line in zip(memberships, ready, strict=True):
            events.sensitive_rights_given(membership.user, _sensitive(line.roles), actor=actor)
        preview.added = [
            {
                "id": membership.pk,
                "name": str(membership.user),
                "phone": membership.user.phone,
                "roles": [role.name for role in line.roles],
                "existing_account": line.phone not in created,
                "letter": _letter_needed(membership.user, membership.user_id in elsewhere),
            }
            for membership, line in zip(memberships, ready, strict=True)
        ]
    return preview


# Lettres d'accès


def letters(ids: list, *, actor: User) -> dict:
    """Lettres d'accès des personnes choisies qui en ont besoin (`_letter_needed`) : chacune
    reçoit un nouveau mot de passe provisoire, imprimé sur sa lettre et gardé nulle part en clair
    (la lettre précédente ne marche plus) ; chaque lettre est au journal. Les autres sont
    ignorées ; `NO_LETTER` s'il n'en reste aucune."""
    school = require_current_school()
    memberships = list(
        Membership.objects.filter(school=school, pk__in=ids, is_active=True)
        .select_related("user")
        .prefetch_related("roles")
        .order_by("user__last_name", "user__middle_name", "user__first_name")
    )
    elsewhere = set(
        Membership.objects.filter(user__in=[m.user for m in memberships])
        .exclude(school=school)
        .values_list("user_id", flat=True)
    )
    # Comptes partagés d'un espace de démonstration : leur mot de passe ne change pas.
    shared = set(
        Demonstration.objects.filter(
            block__in={demo_block(m.user.phone) for m in memberships} - {None}
        ).values_list("block", flat=True)
    )
    chosen = [
        m
        for m in memberships
        if _letter_needed(m.user, m.user_id in elsewhere) and demo_block(m.user.phone) not in shared
    ]
    if not chosen:
        raise BusinessError(NO_LETTER)
    passwords, now = {}, timezone.now()
    with transaction.atomic():
        for membership in chosen:
            user = membership.user
            passwords[user.pk] = make_temporary_password()
            user.set_password(passwords[user.pk])
            user.must_change_password, user.updated_at = True, now
        User.objects.bulk_update(
            [m.user for m in chosen], ["password", "must_change_password", "updated_at"]
        )
        audit.record_many(
            Action.STAFF_PASSWORD_RESET,
            [(membership, {"letter": True}) for membership in chosen],
            actor=actor,
            label=lambda membership: str(membership.user),
        )
    address = f"{school.url}/app/"
    return {
        **school_header(school),
        "contact": school.receipt["header"],
        "paper": "a4",
        "app_url": address.split("://", 1)[-1],
        "qr": qr_code(address),
        "letters": [
            {
                "name": str(membership.user),
                "roles": ", ".join(role.name for role in membership.roles.all()),
                "phone": format_phone(membership.user.phone),
                "password": passwords[membership.user.pk],
            }
            for membership in chosen
        ],
        "printed_by": actor.get_full_name(),
    }


def template_workbook() -> bytes:
    """Modèle à remplir : une colonne par champ, titres reconnus à l'import."""
    titles = [
        gettext("LAST NAME"),
        gettext("MIDDLE NAME (optional)"),
        gettext("FIRST NAME (optional)"),
        gettext("PHONE"),
        gettext("ROLES"),
    ]
    return workbook(titles, [])
