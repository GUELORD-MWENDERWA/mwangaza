"""Journal d'audit des rôles, des comptes du personnel, de Mon compte et de la connexion (I1).

Ce qui se passe dans une école va dans son journal ; ce qui change un compte va dans le journal
de chaque école où la personne est active, sans dire où l'action a été faite."""

import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from apps.accounts import services
from apps.accounts.models import Membership, Role
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from tests.factories import (
    TEST_PASSWORD,
    MembershipFactory,
    SchoolFactory,
    enable_totp,
    totp_code,
)

pytestmark = pytest.mark.django_db

ROLES = "/api/roles/"
STAFF = "/api/staff/"
LOGIN = "/api/auth/login/"
CODE = "/api/auth/login/totp/"
PASSWORD = "/api/auth/password/"
SETUP = "/api/auth/totp/setup/"
ACTIVATE = "/api/auth/totp/activate/"
RECOVERY = "/api/auth/totp/recovery-codes/"
DISABLE = "/api/auth/totp/disable/"
LOGOUT = "/api/auth/logout/"
NEW_PASSWORD = "nouveau-mot-de-passe-2026"


def journal(school) -> list[AuditLog]:
    """Entrées de l'école, la plus ancienne d'abord."""
    return list(AuditLog.all_schools.filter(school=school).order_by("created_at"))


def actions(school) -> list[str]:
    return [log.action for log in journal(school)]


def only(school, action) -> AuditLog:
    return AuditLog.all_schools.get(school=school, action=action)


def last_login(school) -> AuditLog:
    return AuditLog.all_schools.filter(school=school, action="auth.login").latest("created_at")


def role_of(school, code) -> Role:
    with use_school(school):
        return Role.objects.get(code=code)


def summary(role) -> dict:
    return {"id": str(role.id), "code": role.code, "name": role.name}


def ok(response):
    assert response.status_code in (200, 201, 204), response.content
    return response


def log_in(client, user, password=TEST_PASSWORD) -> str:
    return ok(client.post(LOGIN, {"phone": user.phone, "password": password})).json()["step"]


# Rôles


def test_role_created(api, school, head):
    response = api(head).post(ROLES, {"name": "Chef d'atelier", "permissions": ["students.view"]})

    log = only(school, "roles.created")
    assert log.actor == head
    assert (log.entity_type, str(log.entity_id), log.entity_label) == (
        "accounts.role",
        response.json()["id"],
        "Chef d'atelier",
    )
    assert log.before is None
    assert log.after == {"name": "Chef d'atelier", "permissions": ["students.view"]}
    # Adresse du client de test de Django.
    assert log.ip == "127.0.0.1"


def test_role_changed_keeps_what_it_was_and_what_it_is(api, school, head):
    cashier = role_of(school, "cashier")
    permissions_before = list(cashier.permissions)
    permissions = [*permissions_before, "students.edit"]

    ok(api(head).patch(f"{ROLES}{cashier.id}/", {"permissions": permissions}))

    cashier.refresh_from_db()
    log = only(school, "roles.updated")
    assert log.before == {"permissions": permissions_before}
    assert log.after == {"permissions": cashier.permissions}
    # Rôle système sans nom propre : l'interface affiche le nom traduit de son code.
    assert (log.entity_id, log.entity_label) == (cashier.id, "")


def test_role_renamed(api, school, head):
    head_role = role_of(school, "head")

    ok(api(head).patch(f"{ROLES}{head_role.id}/", {"name": "Préfet des études"}))

    log = only(school, "roles.updated")
    assert (log.before, log.after) == ({"name": ""}, {"name": "Préfet des études"})
    assert log.entity_label == "Préfet des études"


def test_nothing_changed_nothing_written(api, school, head):
    cashier = role_of(school, "cashier")

    ok(api(head).patch(f"{ROLES}{cashier.id}/", {"name": "", "permissions": cashier.permissions}))

    assert actions(school) == []


def test_role_deleted(api, school, head):
    with use_school(school):
        role = Role.objects.create(name="Chef d'atelier", permissions=["students.view"])

    ok(api(head).delete(f"{ROLES}{role.id}/"))

    log = only(school, "roles.deleted")
    assert (log.entity_id, log.entity_label) == (role.id, "Chef d'atelier")
    assert log.before == {"name": "Chef d'atelier", "permissions": ["students.view"]}
    assert log.after is None


def test_refused_change_writes_nothing(api, school, head):
    # Le seul directeur perdrait `roles.manage` : refusé, rien dans le journal.
    head_role = role_of(school, "head")

    response = api(head).patch(f"{ROLES}{head_role.id}/", {"permissions": ["students.view"]})

    assert response.json()["code"] == "last_role_manager"
    assert actions(school) == []


# Comptes du personnel


def test_new_account_added(api, school, head):
    cashier = role_of(school, "cashier")

    response = api(head).post(
        STAFF, {"phone": "0100091001", "last_name": "Kahindo", "roles": [str(cashier.id)]}
    )

    data = ok(response).json()
    log = only(school, "staff.added")
    assert log.actor == head
    assert (log.entity_type, str(log.entity_id), log.entity_label) == (
        "accounts.membership",
        data["id"],
        "Kahindo",
    )
    assert log.after == {"roles": [summary(cashier)], "new_account": True}


def test_existing_account_added(api, school, other_school, head):
    user = MembershipFactory(school=other_school, roles=["teacher"]).user
    teacher = role_of(school, "teacher")

    ok(api(head).post(STAFF, {"phone": user.phone, "roles": [str(teacher.id)]}))

    assert only(school, "staff.added").after == {"roles": [summary(teacher)], "new_account": False}
    # L'autre école n'en sait rien.
    assert actions(other_school) == []


def test_roles_changed(api, school, head):
    membership = MembershipFactory(school=school, roles=["teacher"])
    teacher, secretary = role_of(school, "teacher"), role_of(school, "secretary")

    ok(api(head).patch(f"{STAFF}{membership.id}/", {"roles": [str(secretary.id), str(teacher.id)]}))

    log = only(school, "staff.roles_changed")
    assert (log.entity_id, log.entity_label) == (membership.id, str(membership.user))
    assert log.before == {"roles": [summary(teacher)]}
    assert log.after == {
        "roles": sorted([summary(teacher), summary(secretary)], key=lambda role: role["id"])
    }


def test_same_roles_in_another_order_write_nothing(api, school, head):
    membership = MembershipFactory(school=school, roles=["teacher", "secretary"])
    teacher, secretary = role_of(school, "teacher"), role_of(school, "secretary")

    ok(api(head).patch(f"{STAFF}{membership.id}/", {"roles": [str(secretary.id), str(teacher.id)]}))

    assert actions(school) == []


def test_deactivated_then_reactivated(api, school, head):
    membership = MembershipFactory(school=school, roles=["teacher"])
    client = api(head)

    for is_active in (False, False, True):
        ok(client.patch(f"{STAFF}{membership.id}/", {"is_active": is_active}))

    # La deuxième demande ne change rien : pas d'entrée.
    assert actions(school) == ["staff.deactivated", "staff.reactivated"]


def test_names_and_phone_changed(api, school, head):
    membership = MembershipFactory(
        school=school, roles=["teacher"], user__last_name="Kahindo", user__first_name="Grace"
    )
    old_phone = membership.user.phone

    ok(
        api(head).patch(
            f"{STAFF}{membership.id}/",
            {"last_name": "Kahindo", "first_name": "Grâce", "phone": "0100091002"},
        )
    )

    log = only(school, "staff.account_changed")
    assert log.before == {"first_name": "Grace", "phone": old_phone}
    assert log.after == {"first_name": "Grâce", "phone": "+243100091002"}
    assert log.entity_label == "Kahindo Grâce"


def test_temporary_password_given_by_the_school(api, school, head):
    membership = MembershipFactory(school=school, roles=["teacher"])

    ok(api(head).post(f"{STAFF}{membership.id}/new-password/"))

    log = only(school, "staff.password_reset")
    assert (log.actor, log.entity_id) == (head, membership.id)
    assert (log.before, log.after) == (None, None)


def test_two_factor_reset_by_the_school(api, school, head):
    membership = MembershipFactory(school=school, roles=["cashier"])
    enable_totp(membership.user)

    ok(api(head).post(f"{STAFF}{membership.id}/reset-totp/"))

    assert only(school, "staff.totp_reset").entity_id == membership.id


def test_refused_account_change_writes_nothing(api, school, other_school, head):
    membership = MembershipFactory(school=school, roles=["teacher"])
    MembershipFactory(school=other_school, user=membership.user)

    response = api(head).post(f"{STAFF}{membership.id}/new-password/")

    assert response.json()["code"] == "account_used_elsewhere"
    assert actions(school) == []


# Mon compte : dans chaque école où la personne est active


@pytest.fixture
def teacher_of_two_schools(school, other_school):
    """Enseignant des deux écoles, et désactivé dans une troisième."""
    user = MembershipFactory(school=school, roles=["teacher"]).user
    MembershipFactory(school=other_school, user=user, roles=["teacher"])
    MembershipFactory(school=SchoolFactory(code="gamma"), user=user, is_active=False)
    return user


def test_password_change_goes_to_each_school_of_the_person(
    api, school, other_school, teacher_of_two_schools
):
    user = teacher_of_two_schools

    ok(api(user).post(PASSWORD, {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}))

    for each in (school, other_school):
        log = only(each, "account.password_changed")
        membership = Membership.objects.get(user=user, school=each)
        # L'entrée de chaque école désigne sa propre appartenance : rien sur l'autre école.
        assert (log.actor, log.entity_id, log.entity_label) == (user, membership.id, str(user))
        assert (log.before, log.after) == (None, None)
    assert not AuditLog.all_schools.filter(school__code="gamma").exists()


def test_wrong_current_password_writes_nothing(api, school, teacher_of_two_schools):
    response = api(teacher_of_two_schools).post(
        PASSWORD, {"current_password": "pas-le-bon", "new_password": NEW_PASSWORD}
    )

    assert response.json()["code"] == "wrong_password"
    assert not AuditLog.all_schools.exists()


def test_two_factor_turned_on_moved_renewed_and_off(
    api, school, other_school, teacher_of_two_schools
):
    client = api(teacher_of_two_schools)

    secret = ok(client.post(SETUP)).json()["secret"]
    ok(client.post(ACTIVATE, {"code": totp_code(secret)}))
    # Nouveau téléphone : nouvelle clé, après le code actuel.
    new_secret = ok(client.post(SETUP, {"code": totp_code(secret, shift=1)})).json()["secret"]
    ok(client.post(ACTIVATE, {"code": totp_code(new_secret)}))
    codes = ok(client.post(RECOVERY, {"code": totp_code(new_secret, shift=1)})).json()[
        "recovery_codes"
    ]
    ok(client.post(DISABLE, {"code": codes[0]}))

    expected = [
        "account.totp_enabled",
        "account.totp_changed",
        "account.recovery_codes_renewed",
        "account.totp_disabled",
    ]
    assert actions(school) == expected
    assert actions(other_school) == expected


# Connexion : dans l'école de l'adresse


def test_login_goes_to_the_school_of_the_address(api, school, other_school, teacher_of_two_schools):
    user = teacher_of_two_schools

    assert log_in(api(), user) == "done"

    log = only(school, "auth.login")
    membership = Membership.objects.get(user=user, school=school)
    assert (log.actor, log.entity_id) == (user, membership.id)
    assert (log.after, log.ip) == ({"second_factor": None}, "127.0.0.1")
    assert actions(other_school) == []


def test_login_with_the_code(api, school, head):
    secret = enable_totp(head)
    client = api()
    log_in(client, head)

    ok(client.post(CODE, {"code": totp_code(secret)}))

    assert last_login(school).after == {"second_factor": "totp"}


def test_login_with_a_recovery_code(api, school, head):
    secret = enable_totp(head)
    codes = services.enable_totp(head, secret, totp_code(secret))
    client = api()
    log_in(client, head)

    ok(client.post(CODE, {"code": codes[0]}))

    assert last_login(school).after == {"second_factor": "recovery_code"}


def test_login_on_a_trusted_device(api, school, head):
    secret = enable_totp(head)
    client = api()
    log_in(client, head)
    ok(client.post(CODE, {"code": totp_code(secret), "trust_device": True}))
    ok(client.post(LOGOUT))

    assert log_in(client, head) == "done"

    assert last_login(school).after == {"second_factor": "trusted_device"}


def test_two_factor_turned_on_while_logging_in(api, school):
    promoter = MembershipFactory(school=school, roles=["promoter"]).user
    client = api()

    assert log_in(client, promoter) == "totp_setup"
    secret = ok(client.post(SETUP)).json()["secret"]
    ok(client.post(ACTIVATE, {"code": totp_code(secret)}))

    assert actions(school) == ["account.totp_enabled", "auth.login"]
    assert last_login(school).after == {"second_factor": "totp"}


def test_temporary_password_replaced_while_logging_in(api, school):
    user = MembershipFactory(school=school, roles=["teacher"], user__must_change_password=True).user
    client = api()

    assert log_in(client, user) == "new_password"
    ok(client.post(PASSWORD, {"new_password": NEW_PASSWORD}))

    assert actions(school) == ["account.password_changed", "auth.login"]


def test_no_login_entry_where_the_person_does_not_work(api, school, other_school):
    # Compte de l'école beta qui se connecte à l'adresse d'alpha.
    user = MembershipFactory(school=other_school, roles=["teacher"]).user

    log_in(api(), user)

    assert not AuditLog.all_schools.exists()


def test_failed_login_writes_nothing(api, school, head):
    response = api().post(LOGIN, {"phone": head.phone, "password": "pas-le-bon"})

    assert response.json()["code"] == "invalid_credentials"
    assert not AuditLog.all_schools.exists()


# Jamais de secret


def test_no_secret_ever_reaches_the_journal(api, school, head):
    client = api(head)
    cashier = role_of(school, "cashier")
    new_cashier = {"phone": "0100091003", "last_name": "Kahindo", "roles": [str(cashier.id)]}
    created = ok(client.post(STAFF, new_cashier)).json()
    reset = ok(client.post(f"{STAFF}{created['id']}/new-password/")).json()["temporary_password"]

    # La nouvelle caissière se connecte : nouveau mot de passe, double authentification.
    newcomer = api()
    assert ok(newcomer.post(LOGIN, {"phone": "0100091003", "password": reset})).json() == {
        "step": "new_password"
    }
    ok(newcomer.post(PASSWORD, {"new_password": NEW_PASSWORD}))
    key = ok(newcomer.post(SETUP)).json()["secret"]
    codes = ok(newcomer.post(ACTIVATE, {"code": totp_code(key)})).json()["recovery_codes"]
    renewed = ok(newcomer.post(RECOVERY, {"code": totp_code(key, shift=1)})).json()[
        "recovery_codes"
    ]

    assert sorted(actions(school)) == sorted(
        [
            "staff.added",
            "staff.password_reset",
            "account.password_changed",
            "account.totp_enabled",
            "auth.login",
            "account.recovery_codes_renewed",
        ]
    )
    dump = json.dumps(list(AuditLog.all_schools.values()), cls=DjangoJSONEncoder)
    for secret in [created["temporary_password"], reset, NEW_PASSWORD, key, *codes, *renewed]:
        assert secret not in dump
    assert "argon2" not in dump
