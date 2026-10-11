"""Les 9 rôles système de `docs/04-modele-de-donnees.md` § 8, copiés dans chaque école."""

import pytest

from apps.accounts.models import Role
from apps.accounts.roles import PERMISSIONS, SYSTEM_ROLES, TOTP_PERMISSIONS, sorted_permissions
from apps.accounts.services import create_system_roles
from apps.core.tenancy import use_school
from tests.factories import SchoolFactory

pytestmark = pytest.mark.django_db

# Tableau de `docs/04` § 8 recopié ici : un écart entre le code et le document fait échouer le test.
# Colonnes : directeur, dir. des études, dir. de discipline, comptable, caissier, secrétaire,
# promoteur.
COLUMNS = [
    "head",
    "study_director",
    "discipline_master",
    "accountant",
    "cashier",
    "secretary",
    "promoter",
]
TABLE = {
    "school.configure": "✔ . . . . . .",
    "classes.manage": "✔ ✔ . . . . .",
    "roles.manage": "✔ . . . . . .",
    "students.view": "✔ ✔ ✔ ✔ ✔ ✔ ✔",
    "students.edit": "✔ ✔ . . . ✔ .",
    "students.import": "✔ . . . . ✔ .",
    "finance.configure_fees": "✔ . . ✔ . . .",
    "finance.set_exchange_rate": "✔ . . ✔ . . .",
    "finance.grant_discount": "✔ . . ✔ . . .",
    "finance.collect_payment": ". . . ✔ ✔ . .",
    "finance.request_cancellation": ". . . ✔ ✔ . .",
    "finance.approve_cancellation": "✔ . . ✔ . . .",
    "finance.close_register": ". . . ✔ ✔ . .",
    "finance.view_reports": "✔ . . ✔ . . ✔",
    "finance.import_prior_payments": "✔ . . ✔ . . .",
    "announcements.publish": "✔ ✔ ✔ . . ✔ .",
    "audit.view": "✔ . . . . . ✔",
}


def expected_permissions() -> dict[str, set[str]]:
    expected = {code: set() for code in [*COLUMNS, "teacher", "parent"]}
    for permission, marks in TABLE.items():
        for role, mark in zip(COLUMNS, marks.split(), strict=True):
            if mark == "✔":
                expected[role].add(permission)
    return expected


def test_permission_codes_match_the_document():
    assert list(PERMISSIONS) == list(TABLE)


def test_system_roles_match_the_document():
    assert {code: set(role.permissions) for code, role in SYSTEM_ROLES.items()} == (
        expected_permissions()
    )


def test_a_new_school_gets_the_nine_system_roles(school):
    with use_school(school):
        roles = list(Role.objects.all())

    assert [role.code for role in roles] == list(SYSTEM_ROLES)
    assert {role.code: set(role.permissions) for role in roles} == expected_permissions()
    assert all(role.name == "" for role in roles)


def test_teacher_and_parent_have_no_permission_in_v1_0(school):
    with use_school(school):
        assert Role.objects.get(code="teacher").permissions == []
        assert Role.objects.get(code="parent").permissions == []


def test_creating_system_roles_again_changes_nothing(school):
    with use_school(school):
        cashier = Role.objects.get(code="cashier")
        cashier.permissions = ["students.view"]
        cashier.save()

    assert create_system_roles(school) == []

    with use_school(school):
        assert Role.objects.count() == 9
        assert Role.objects.get(code="cashier").permissions == ["students.view"]


def test_missing_system_roles_are_added(school):
    with use_school(school):
        Role.objects.get(code="parent").delete()

    created = create_system_roles(school)

    assert [role.code for role in created] == ["parent"]


def test_each_school_has_its_own_copy(school, other_school):
    with use_school(school):
        cashier = Role.objects.get(code="cashier")
        cashier.permissions = []
        cashier.save()

    with use_school(other_school):
        assert Role.objects.get(code="cashier").permissions == list(
            SYSTEM_ROLES["cashier"].permissions
        )
        assert Role.objects.count() == 9


def test_school_created_inside_another_school_context(school):
    # Ex. super-admin qui crée une école : les rôles vont dans la nouvelle école.
    with use_school(school):
        new_school = SchoolFactory(code="gamma")
    with use_school(new_school):
        assert Role.objects.count() == 9


def test_sorted_permissions():
    assert sorted_permissions(["audit.view", "students.view", "audit.view"]) == [
        "students.view",
        "audit.view",
    ]
    with pytest.raises(ValueError):
        sorted_permissions(["students.delete"])


def test_default_roles_that_require_two_factor_authentication():
    # B4 : directeur, comptable, caissier, promoteur.
    requiring = {
        code for code, role in SYSTEM_ROLES.items() if set(role.permissions) & TOTP_PERMISSIONS
    }

    assert requiring == {"head", "accountant", "cashier", "promoter"}


def test_every_right_on_money_requires_it():
    finance = {code for code in PERMISSIONS if code.startswith("finance.")}

    assert finance <= TOTP_PERMISSIONS
    assert TOTP_PERMISSIONS.issubset(PERMISSIONS)
