"""Espaces de démonstration (4.17.1, `03` § 4 bis) : comptes dans la plage de numéros réservée
`+243 0…`, jamais mêlés aux comptes d'un espace réel ou d'essai ; pas de double authentification."""

import pytest

from apps.accounts import services
from apps.accounts.models import Role
from apps.accounts.phone import is_demo_phone, normalize_phone
from apps.core.tenancy import use_school
from apps.schools.models import School
from tests.factories import MembershipFactory, SchoolFactory, UserFactory

STAFF = "/api/staff/"
ROLES = "/api/roles/"


@pytest.fixture
def demo_school(db):
    return SchoolFactory(code="vitrine", environment=School.Environment.DEMO)


@pytest.fixture
def demo_head(demo_school):
    user = UserFactory(phone="+243004001001")
    return MembershipFactory(user=user, school=demo_school, roles=["head"]).user


def add(client, school, phone):
    with use_school(school):
        role = str(Role.objects.get(code="cashier").pk)
    return client.post(STAFF, {"phone": phone, "last_name": "Kavira", "roles": [role]})


def test_the_reserved_range_is_every_number_starting_with_zero_after_the_country_code():
    assert is_demo_phone("+243004001001")
    assert is_demo_phone(normalize_phone("0004001001"))
    assert not is_demo_phone("+243971183062")
    # Un autre pays : son 0 n'est pas le nôtre.
    assert not is_demo_phone("+250004001001")


@pytest.mark.parametrize("environment", [School.Environment.LIVE, School.Environment.TEST])
def test_a_reserved_number_never_enters_a_live_or_test_space(api, head, school, environment):
    School.objects.filter(pk=school.pk).update(environment=environment)

    response = add(api(head), school, "0004001005")

    assert response.status_code == 400
    assert response.json()["code"] == "demo_number"
    # Pas non plus en changeant le numéro d'un compte de l'école.
    member = MembershipFactory(school=school, roles=["cashier"])
    changed = api(head).patch(f"{STAFF}{member.pk}/", {"phone": "0004001005"})
    assert changed.json()["code"] == "demo_number"


def test_a_demo_space_only_takes_reserved_numbers(api, demo_head, demo_school):
    client = api(demo_head, host="vitrine.localhost")

    assert add(client, demo_school, "0971183062").json()["code"] == "demo_space_numbers"
    added = add(client, demo_school, "0004001005")
    assert added.status_code == 201, added.content
    # Un compte de démonstration ne devient pas celui d'une vraie personne.
    changed = client.patch(f"{STAFF}{added.json()['id']}/", {"phone": "0971183062"})
    assert changed.json()["code"] == "demo_space_numbers"


def test_two_factor_authentication_is_not_asked_in_a_demo_space(api, demo_head, school):
    # Directeur : un rôle qui l'exige partout ailleurs.
    assert not services.totp_required(demo_head)
    assert api(demo_head, host="vitrine.localhost", mfa=False).get(ROLES).status_code == 200

    # Le même rôle dans un espace réel : exigée, et vérifiée à chaque requête de cet espace.
    MembershipFactory(user=demo_head, school=school, roles=["head"])
    assert services.totp_required(demo_head)
    assert api(demo_head, mfa=False).get(ROLES).json()["code"] == "totp_required"
