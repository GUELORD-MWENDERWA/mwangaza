"""Comptes dans la console de la plateforme (5.4.1) : super-admin seulement, à l'adresse de la
console ; recherche dans toutes les écoles (personnel et parents), noms, téléphone, accès, mot de
passe provisoire et double authentification, notés dans le journal de la plateforme et dans celui
de chaque école où la personne est active."""

from urllib.parse import urlencode

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, User
from apps.audit.actions import Action
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.core.tenancy import use_school
from apps.students.models import Family
from tests.factories import MembershipFactory, UserFactory, enable_totp

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
ACCOUNTS = "/api/console/accounts/"


def parent_of(school, user, code) -> Family:
    with use_school(school):
        return Family.objects.create(code=code, primary_user=user, activated_at=timezone.now())


def platform_journal(user) -> list[str]:
    return list(
        PlatformAuditLog.objects.filter(entity_id=str(user.pk))
        .order_by("created_at", "id")
        .values_list("action", flat=True)
    )


def journal(school, user) -> list[str]:
    """Le journal de l'école, sur l'appartenance de la personne à cette école."""
    membership = Membership.objects.get(school=school, user=user)
    with use_school(school):
        logs = AuditLog.objects.filter(entity_id=membership.pk).order_by("created_at", "id")
        return list(logs.values_list("action", flat=True))


@pytest.fixture
def both(school, other_school):
    """Directeur de l'école alpha, enseignant de l'école beta."""
    user = MembershipFactory(school=school, roles=["head"]).user
    MembershipFactory(school=other_school, user=user, roles=["teacher"])
    return user


def test_only_the_platform_admin_manages_accounts_at_the_console(api, platform_admin, head, both):
    detail = f"{ACCOUNTS}{both.pk}/"
    calls = [
        ("get", ACCOUNTS, None),
        ("get", detail, None),
        ("patch", detail, {"last_name": "Piraté", "is_active": False}),
        ("post", f"{detail}new-password/", None),
        ("post", f"{detail}reset-totp/", None),
    ]
    for method, url, data in calls:

        def call(client, method=method, url=url, data=data):
            return client.get(url) if method == "get" else getattr(client, method)(url, data)

        # Le directeur d'une école ne touche pas au compte de quelqu'un d'une autre école.
        assert call(api(head, host=CONSOLE)).status_code == 403
        assert call(api(platform_admin, host=CONSOLE, mfa=False)).status_code == 403
        # À l'adresse d'une école, ces points d'API n'existent pas.
        assert call(api(platform_admin)).status_code == 404
        assert call(api(head)).status_code == 404
    both.refresh_from_db()
    assert both.is_active and not both.must_change_password and both.last_name != "Piraté"
    assert not PlatformAuditLog.objects.exists()


def test_search_finds_accounts_in_every_school_with_their_roles_and_families(
    api, platform_admin, school, other_school, both, django_assert_max_num_queries
):
    both.phone = "+243970001122"
    both.last_name, both.first_name = "Kasereka", "Dieudonné"
    both.save()
    parent_of(other_school, both, "FAMBETA1")
    parent_only = UserFactory(last_name="Kahindo", first_name="Neema")
    parent_of(school, parent_only, "FAMALPH1")
    for _ in range(5):
        MembershipFactory(school=school, roles=["cashier"])
    client = api(platform_admin, host=CONSOLE)

    # Numéro tapé à la façon locale, ou mots du nom dans le désordre.
    for search in ("0970001122", "dieudonné kase"):
        rows = client.get(f"{ACCOUNTS}?{urlencode({'search': search})}").json()["results"]
        assert [row["id"] for row in rows] == [str(both.pk)]
    row = rows[0]
    assert {(m["school"]["code"], tuple(m["roles"])) for m in row["memberships"]} == {
        (school.code, ("Préfet des études",)),
        (other_school.code, ("Enseignant",)),
    }
    assert [(f["code"], f["school"]["code"]) for f in row["families"]] == [
        ("FAMBETA1", other_school.code)
    ]
    rows = client.get(f"{ACCOUNTS}?search=neema").json()["results"]
    assert [(row["memberships"], len(row["families"])) for row in rows] == [([], 1)]

    # Sans recherche : toute la page en un nombre fixe de requêtes, pas une par compte.
    with django_assert_max_num_queries(12):
        rows = client.get(ACCOUNTS).json()["results"]
    assert len(rows) == User.objects.count()


def test_support_gives_a_temporary_password_and_resets_two_factor_noted_everywhere(
    api, platform_admin, school, other_school, both
):
    enable_totp(both)
    client = api(platform_admin, host=CONSOLE)

    password = client.post(f"{ACCOUNTS}{both.pk}/new-password/").json()["temporary_password"]
    response = client.post(f"{ACCOUNTS}{both.pk}/reset-totp/")
    assert response.status_code == 200 and response.json()["totp_enabled"] is False
    # Plus rien à réinitialiser : rien de plus au journal.
    client.post(f"{ACCOUNTS}{both.pk}/reset-totp/")

    both.refresh_from_db()
    assert both.check_password(password) and both.must_change_password
    assert not both.totp_enabled and not both.totp_secret
    expected = [Action.ACCOUNT_PASSWORD_RESET, Action.ACCOUNT_TOTP_RESET]
    assert platform_journal(both) == expected
    assert journal(school, both) == journal(other_school, both) == expected
    history = client.get(f"{ACCOUNTS}{both.pk}/").json()["history"]
    assert [(h["action"], h["actor"]["id"]) for h in history] == [
        (Action.ACCOUNT_TOTP_RESET, str(platform_admin.pk)),
        (Action.ACCOUNT_PASSWORD_RESET, str(platform_admin.pk)),
    ]


def test_platform_accounts_and_portal_only_accounts_are_refused(api, platform_admin, school):
    other_admin = User.objects.create_superuser("0000000009", "secret-123", last_name="Admin2")
    parent_only = UserFactory()
    parent_of(school, parent_only, "FAMALPH2")
    client = api(platform_admin, host=CONSOLE)

    for url, data in [
        (f"{ACCOUNTS}{other_admin.pk}/", {"is_active": False}),
        (f"{ACCOUNTS}{other_admin.pk}/new-password/", None),
        (f"{ACCOUNTS}{other_admin.pk}/reset-totp/", None),
        (f"{ACCOUNTS}{platform_admin.pk}/", {"is_active": False}),
    ]:
        response = client.patch(url, data) if data else client.post(url)
        assert (response.status_code, response.json()["code"]) == (409, "platform_account")
    # Le portail refuse un mot de passe provisoire : l'école donne un nouveau code famille.
    response = client.post(f"{ACCOUNTS}{parent_only.pk}/new-password/")
    assert (response.status_code, response.json()["code"]) == (409, "portal_only_account")

    other_admin.refresh_from_db()
    parent_only.refresh_from_db()
    assert other_admin.is_active and not parent_only.must_change_password
    assert not PlatformAuditLog.objects.exists()


def test_support_changes_names_phone_and_access(api, platform_admin, school, other_school, both):
    taken = UserFactory(phone="+243970009999")
    client = api(platform_admin, host=CONSOLE)
    session = api(both)
    assert session.get("/api/me/").status_code == 200

    response = client.patch(f"{ACCOUNTS}{both.pk}/", {"phone": "0970009999"})
    assert (response.status_code, response.json()["code"]) == (409, "phone_taken")
    response = client.patch(
        f"{ACCOUNTS}{both.pk}/", {"phone": "0970001234", "first_name": "Espoir"}
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+243970001234"
    # Désactivé : sa session ouverte ne vaut plus, à aucune adresse.
    client.patch(f"{ACCOUNTS}{both.pk}/", {"is_active": False})
    assert session.get("/api/me/").status_code in (401, 403)
    client.patch(f"{ACCOUNTS}{both.pk}/", {"is_active": True})

    taken.refresh_from_db()
    assert taken.phone == "+243970009999"
    changed = PlatformAuditLog.objects.get(entity_id=str(both.pk), action="account.changed")
    assert changed.after == {"phone": "+243970001234", "first_name": "Espoir"}
    expected = [Action.ACCOUNT_CHANGED, Action.ACCOUNT_DEACTIVATED, Action.ACCOUNT_REACTIVATED]
    assert platform_journal(both) == expected
    assert journal(other_school, both) == expected
