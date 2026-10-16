"""Le modèle de départ des rôles (`docs/04-modele-de-donnees.md` § 8), copié dans chaque école
neuve, et la migration des anciens rôles système (M.3.2)."""

from importlib import import_module

import pytest

from apps.accounts.models import Role
from apps.accounts.roles import (
    PERMISSIONS,
    ROLES_MANAGE,
    STARTER_ROLES,
    TOTP_PERMISSIONS,
    sorted_permissions,
)
from apps.core.tenancy import use_school
from tests.factories import SchoolFactory, starter_role

pytestmark = pytest.mark.django_db

# Tableau de `docs/04` § 8 recopié ici : un écart entre le code et le document fait échouer le test.
# Colonnes : directeur, dir. des études, dir. de discipline, comptable, caissier, secrétaire,
# promoteur, enseignant.
COLUMNS = [
    "head",
    "study_director",
    "discipline_master",
    "accountant",
    "cashier",
    "secretary",
    "promoter",
    "teacher",
]
TABLE = {
    "school.configure": "✔ . . . . . . .",
    "classes.manage": "✔ ✔ . . . . . .",
    "courses.configure": "✔ ✔ . . . . . .",
    "grades.enter": ". . . . . . . ✔",
    "grades.enter_any": ". ✔ . . . ✔ . .",
    "grades.validate": ". ✔ . . . . . .",
    "discipline.configure": "✔ . ✔ . . . . .",
    "discipline.record": "✔ ✔ ✔ . . . . ✔",
    "discipline.override": "✔ . ✔ . . . . .",
    "roles.manage": "✔ . . . . . . .",
    "students.view": "✔ ✔ ✔ ✔ ✔ ✔ ✔ .",
    "students.edit": "✔ ✔ . . . ✔ . .",
    "students.import": "✔ . . . . ✔ . .",
    "finance.configure_fees": "✔ . . ✔ . . . .",
    "finance.set_exchange_rate": "✔ . . ✔ . . . .",
    "finance.grant_discount": "✔ . . ✔ . . . .",
    "finance.collect_payment": ". . . ✔ ✔ . . .",
    "finance.request_cancellation": ". . . ✔ ✔ . . .",
    "finance.approve_cancellation": "✔ . . ✔ . . . .",
    "finance.close_register": ". . . ✔ ✔ . . .",
    "finance.view_reports": "✔ . . ✔ . . ✔ .",
    "finance.import_prior_payments": "✔ . . ✔ . . . .",
    "announcements.publish": "✔ ✔ ✔ . . ✔ . .",
    "audit.view": "✔ . . . . . ✔ .",
}


def expected_permissions() -> dict[str, set[str]]:
    expected = {code: set() for code in [*COLUMNS, "parent"]}
    for permission, marks in TABLE.items():
        for role, mark in zip(COLUMNS, marks.split(), strict=True):
            if mark == "✔":
                expected[role].add(permission)
    return expected


def test_permission_codes_match_the_document():
    assert list(PERMISSIONS) == list(TABLE)


def test_starter_roles_match_the_document():
    assert {key: set(role.permissions) for key, role in STARTER_ROLES.items()} == (
        expected_permissions()
    )


def test_a_new_school_gets_the_starter_roles_as_ordinary_named_roles(school, other_school):
    with use_school(school):
        roles = list(Role.objects.all())

    # Dans l'ordre du modèle, en français quelle que soit la langue de qui crée l'école.
    assert [role.name for role in roles] == [
        "Directeur",
        "Directeur des études",
        "Directeur de discipline",
        "Comptable",
        "Caissier",
        "Secrétaire",
        "Promoteur",
        "Enseignant",
        "Parent",
    ]
    assert [set(role.permissions) for role in roles] == list(expected_permissions().values())
    # Chaque école a sa copie : changer l'une ne change pas l'autre.
    with use_school(school):
        Role.objects.filter(name="Caissier").update(permissions=[])
    assert starter_role(other_school, "cashier").permissions == list(
        STARTER_ROLES["cashier"].permissions
    )


def test_the_starter_roles_let_the_school_manage_its_roles():
    # Sans cela, le premier compte d'une école neuve ne pourrait donner de droit à personne.
    assert any(ROLES_MANAGE in role.permissions for role in STARTER_ROLES.values())


def test_school_created_inside_another_school_context(school):
    # Ex. super-admin qui crée une école : les rôles vont dans la nouvelle école.
    with use_school(school):
        new_school = SchoolFactory(code="gamma")
    with use_school(new_school):
        assert Role.objects.count() == 9
    with use_school(school):
        assert Role.objects.count() == 9


def test_former_system_roles_are_named_as_the_school_saw_them():
    # Migration 0007 : rôles d'avant M.3.2, avec un code et un nom vide sauf renommage.
    migration = import_module("apps.accounts.migrations.0007_role_names")
    roles = [
        (1, "alpha", "head", "Préfet des études"),  # déjà renommé par l'école : gardé
        (2, "alpha", "cashier", ""),
        (3, "alpha", "accountant", ""),
        (4, "alpha", "", "COMPTABLE"),  # créé par l'école, même nom sans la casse
        (5, "beta", "accountant", ""),
    ]

    assert migration.names_to_give(roles) == {2: "Caissier", 3: "Comptable (2)", 5: "Comptable"}


def test_sorted_permissions():
    assert sorted_permissions(["audit.view", "students.view", "audit.view"]) == [
        "students.view",
        "audit.view",
    ]
    with pytest.raises(ValueError):
        sorted_permissions(["students.delete"])


def test_default_roles_that_require_two_factor_authentication():
    # B4 : directeur, directeur des études (validation des notes), comptable, caissier, promoteur.
    requiring = {
        key for key, role in STARTER_ROLES.items() if set(role.permissions) & TOTP_PERMISSIONS
    }

    assert requiring == {"head", "study_director", "accountant", "cashier", "promoter"}


def test_every_right_on_money_requires_it():
    finance = {code for code in PERMISSIONS if code.startswith("finance.")}

    assert finance <= TOTP_PERMISSIONS
    assert TOTP_PERMISSIONS.issubset(PERMISSIONS)
