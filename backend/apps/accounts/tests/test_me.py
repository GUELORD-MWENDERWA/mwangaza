"""/api/me/ : le compte, ses écoles, ses droits dans l'école de l'adresse, l'état de sa double
authentification ; la personne change sa langue."""

import pytest

from apps.accounts.models import Role
from apps.accounts.roles import STARTER_ROLES
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/me/"


def test_anonymous_is_refused(api, school):
    response = api().get(URL)

    assert response.status_code == 403
    assert response.json()["code"] == "not_authenticated"


def test_head_sees_their_roles_and_permissions(api, school):
    user = UserFactory(last_name="Kambale", middle_name="Muhindo", first_name="Patrice")
    MembershipFactory(user=user, school=school, roles=["head"])
    with use_school(school):
        head_role = Role.objects.get(name="Directeur")

    data = api(user).get(URL).json()

    assert data["id"] == str(user.id)
    assert data["phone"] == user.phone
    assert (data["last_name"], data["middle_name"], data["first_name"]) == (
        "Kambale",
        "Muhindo",
        "Patrice",
    )
    assert data["language"] == "fr"
    # Directeur : double authentification exigée (B4), pas encore activée par ce compte de test.
    assert data["totp_required"] is True
    assert (data["totp_enabled"], data["totp_enabled_at"]) == (False, None)
    assert data["recovery_codes_left"] == 0
    assert data["is_platform_admin"] is False
    assert data["schools"] == [
        {
            "code": "alpha",
            "name": "École Alpha (fictive)",
            "status": "active",
            "url": "http://alpha.localhost:5173",
            "primary_color": "#0E5C6B",
            "text_color": "#FFFFFF",
            "logo": None,
            "roles": [{"id": str(head_role.id), "name": "Directeur"}],
            "last_login_at": None,
        }
    ]
    school_data = data["school"]
    assert (school_data["code"], school_data["name"]) == ("alpha", "École Alpha (fictive)")
    assert school_data["roles"] == [{"id": str(head_role.id), "name": "Directeur"}]
    assert school_data["permissions"] == list(STARTER_ROLES["head"].permissions)


def test_one_account_in_two_schools(api, school, other_school):
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["head"])
    MembershipFactory(user=user, school=other_school, roles=["teacher"])

    at_alpha = api(user).get(URL).json()
    at_beta = api(user, host="beta.localhost").get(URL).json()
    at_platform = api(user, host="localhost").get(URL).json()

    assert [s["code"] for s in at_alpha["schools"]] == ["alpha", "beta"]
    assert [r["name"] for r in at_alpha["school"]["roles"]] == ["Directeur"]
    # Dans chaque école, seulement les rôles et permissions de cette école.
    assert [r["name"] for r in at_beta["school"]["roles"]] == ["Enseignant"]
    assert at_beta["school"]["permissions"] == []
    # Adresse générale : choix de l'école (M2), aucun droit.
    assert at_platform["school"] is None
    assert len(at_platform["schools"]) == 2


def test_each_school_with_its_own_roles_colour_and_last_visit(api, school, other_school):
    """Choix de l'école (M2) : pour chaque école du compte, ses rôles dans cette école, sa couleur,
    son logo (à son adresse) et la dernière connexion à cette école."""
    from django.core.files.base import ContentFile
    from django.utils import timezone

    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["head"])
    visited = timezone.now()
    MembershipFactory(user=user, school=other_school, roles=["teacher", "secretary"])
    user.memberships.filter(school=other_school).update(last_login_at=visited)
    other_school.primary_color = "#F2C94C"
    other_school.logo.save("logo.png", ContentFile(b"\x89PNG\r\n\x1a\n" + b"\0" * 32), save=True)

    schools = {s["code"]: s for s in api(user).get(URL).json()["schools"]}

    beta = schools["beta"]
    assert sorted(r["name"] for r in beta["roles"]) == ["Enseignant", "Secrétaire"]
    assert [r["name"] for r in schools["alpha"]["roles"]] == ["Directeur"]
    assert beta["url"] == "http://beta.localhost:5173"
    assert (beta["primary_color"], beta["text_color"]) == ("#F2C94C", "#211D1A")
    assert beta["logo"].startswith("http://beta.localhost:5173/api/school/logo/?v=")
    assert beta["last_login_at"] is not None
    assert schools["alpha"]["logo"] is None


def test_platform_admin_is_said(api, school, platform_admin):
    data = api(platform_admin).get(URL).json()

    assert data["is_platform_admin"] is True
    assert data["schools"] == []
    assert data["school"] is None


def test_roles_of_another_person_are_never_listed(api, school, other_school, head):
    MembershipFactory(school=other_school, roles=["head"])

    data = api(head).get(URL).json()

    assert [s["code"] for s in data["schools"]] == ["alpha"]
    assert [r["name"] for r in data["schools"][0]["roles"]] == ["Directeur"]


def test_no_access_to_a_school_where_the_account_has_no_role(api, head, other_school):
    data = api(head, host="beta.localhost").get(URL).json()

    assert data["school"] is None
    assert [s["code"] for s in data["schools"]] == ["alpha"]


def test_deactivated_membership_is_not_listed(api, school, other_school):
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["head"], is_active=False)
    MembershipFactory(user=user, school=other_school, roles=["cashier"])

    data = api(user).get(URL).json()

    assert data["school"] is None
    assert [s["code"] for s in data["schools"]] == ["beta"]


def test_teacher_does_not_need_two_factor_authentication(api, school):
    user = MembershipFactory(school=school, roles=["teacher"]).user

    assert api(user).get(URL).json()["totp_required"] is False


def test_role_that_requires_it_in_another_school_counts(api, school, other_school):
    # Un seul compte : exigée pour lui partout (sans dire à l'école alpha pourquoi).
    user = MembershipFactory(school=school, roles=["teacher"]).user
    MembershipFactory(user=user, school=other_school, roles=["cashier"])

    data = api(user).get(URL).json()

    assert data["totp_required"] is True
    assert [r["name"] for r in data["school"]["roles"]] == ["Enseignant"]


def test_language_can_be_changed(api, school):
    user = MembershipFactory(school=school, roles=["teacher"]).user

    response = api(user).patch(URL, {"language": "en"})

    assert response.status_code == 200
    assert response.json()["language"] == "en"
    user.refresh_from_db()
    assert user.language == "en"


def test_unknown_language_is_refused(api, school):
    user = MembershipFactory(school=school, roles=["teacher"]).user

    response = api(user).patch(URL, {"language": "sw"})

    assert response.status_code == 400
    assert "language" in response.json()["fields"]


def test_names_cannot_be_changed_here(api, school):
    # Noms et téléphone : par l'école (M4, « adressez-vous au directeur ») ou le support.
    user = MembershipFactory(school=school, roles=["teacher"], user__last_name="Kambale").user

    api(user).patch(URL, {"language": "fr", "last_name": "Autre", "phone": "0000000999"})

    user.refresh_from_db()
    assert user.last_name == "Kambale"


def test_a_suspended_school_stays_listed_greyed(api, school, other_school):
    # Choix de l'école (M2) : école suspendue visible mais grisée.
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["teacher"])
    MembershipFactory(user=user, school=other_school, roles=["teacher"])
    other_school.status = "suspended"
    other_school.save()

    schools = api(user).get(URL).json()["schools"]

    assert {item["code"]: item["status"] for item in schools} == {
        "alpha": "active",
        "beta": "suspended",
    }
