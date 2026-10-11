"""Accès au portail des familles (H1, M19) : activation, connexion, mot de passe oublié avec un
nouveau code, et « Nouveau code » de la fiche famille."""

from datetime import timedelta

from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students import services as students
from apps.students.models import Family
from tests.factories import (
    TEST_PASSWORD,
    MembershipFactory,
    SchoolFactory,
    UserFactory,
    enable_totp,
)

PHONE = "+243971234567"
PASSWORD = "Lac-Kivu-2026"
PORTAL = "parents.localhost"


def new_family(school, actor, phone=PHONE) -> Family:
    guardian = {"full_name": "Kahindo Neema", "relationship": "mother", "phone": phone}
    with use_school(school):
        return students.create_family(actor=actor, guardians=[{**guardian, "is_primary": True}])


def portal(host=PORTAL) -> Client:
    return Client(HTTP_HOST=host)


def post(client, path, **data):
    return client.post(f"/api/portal/{path}", data, content_type="application/json")


def activate(client, code, phone="0971234567", **data):
    body = {"phone": phone, "code": code, "password": PASSWORD, **data}
    return post(client, "auth/activate/", **body)


def reset(client, code, phone=PHONE):
    return post(client, "auth/reset/", phone=phone, code=code, password="Nyiragongo-2026")


def reloaded(family) -> Family:
    return Family.all_schools.select_related("primary_user").get(pk=family.pk)


def actions(school, action):
    with use_school(school):
        return list(AuditLog.objects.filter(action=action))


def test_activation_creates_the_account_links_the_family_and_logs_in(school, head):
    family = new_family(school, head)
    client = portal()
    printed = f"{family.code[:4]}-{family.code[4:]}".lower()

    response = activate(client, printed, remember=True)

    assert response.status_code == 200
    assert response.json()["phone"] == PHONE
    family = reloaded(family)
    assert family.primary_user.phone == PHONE and family.activated_at is not None
    assert client.get("/api/portal/me/").json()["name"] == "Kahindo Neema"
    assert client.session.get_expiry_age() == 90 * 24 * 3600
    [entry] = actions(school, "portal.activated")
    assert entry.actor == family.primary_user and entry.entity_id == family.pk
    # Le code a servi : une seconde activation ne prend pas la famille.
    assert activate(portal(), family.code).json()["code"] == "already_activated"


def test_wrong_phone_wrong_or_expired_code_same_error_and_attempts_counted(school, head):
    family = new_family(school, head)
    other = new_family(school, head, phone="+243990000001")
    Family.all_schools.filter(pk=other.pk).update(code_expires_at=timezone.now())

    refused = [
        activate(portal(), family.code, phone="0990000001"),
        activate(portal(), "ABCD-EFGH"),
        activate(portal(), other.code, phone="0990000001"),
    ]

    assert {r.json()["code"] for r in refused} == {"invalid_family_code"}
    for _ in range(4):
        activate(portal(), "ABCD-EFGH")
    # 5 essais ratés pour ce numéro : bloqué, même avec le bon code.
    assert activate(portal(), family.code).status_code == 429
    assert reloaded(family).primary_user is None


def test_number_with_an_account_or_suspended_school_does_not_activate(school, head, other_school):
    UserFactory(phone=PHONE)
    family = new_family(school, head)
    assert activate(portal(), family.code).json()["code"] == "account_exists"

    elsewhere = new_family(other_school, head, phone="+243990000002")
    School.objects.filter(pk=other_school.pk).update(status=School.Status.SUSPENDED)
    response = activate(portal(), elsewhere.code, phone="+243990000002")
    assert (response.status_code, response.json()["code"]) == (403, "school_unavailable")
    assert reloaded(family).primary_user is None and reloaded(elsewhere).primary_user is None


def test_a_reserved_number_only_activates_in_a_demo_space_which_takes_no_other(school, head):
    """Pas de mélange (`03` § 4 bis) : le compte d'une vraie personne n'est jamais relié à une
    famille fictive, ni un compte de démonstration à une vraie famille."""
    fictitious = new_family(school, head, phone="+243004100001")
    assert activate(portal(), fictitious.code, "0004100001").json()["code"] == "demo_number"

    demo = SchoolFactory(code="vitrine", environment=School.Environment.DEMO)
    actor = MembershipFactory(school=demo, roles=["head"]).user
    real = new_family(demo, actor)
    assert activate(portal(), real.code).json()["code"] == "demo_space_numbers"
    assert not User.objects.filter(phone=PHONE).exists()

    shown = new_family(demo, actor, phone="+243004100002")
    assert activate(portal(), shown.code, "0004100002").status_code == 200


def test_login_with_the_password_only_temporary_password_refused(school):
    user = UserFactory(phone=PHONE)
    enable_totp(user)
    client = portal()

    wrong = post(client, "auth/login/", phone="0971234567", password="mauvais")
    assert wrong.json()["code"] == "invalid_credentials"
    # La double authentification protège l'adresse de l'école, pas le portail.
    logged_in = post(client, "auth/login/", phone="0971234567", password=TEST_PASSWORD)
    assert logged_in.status_code == 200
    # Sans « Rester connecté » : 12 heures, cookie daté (gardé en quittant l'application installée).
    assert logged_in.cookies["sessionid"]["max-age"] == 12 * 3600
    assert client.get("/api/portal/me/").json()["phone"] == PHONE

    User.objects.filter(pk=user.pk).update(must_change_password=True)
    refused = post(portal(), "auth/login/", phone=PHONE, password=TEST_PASSWORD)
    assert (refused.status_code, refused.json()["code"]) == (403, "password_change_required")


def test_session_extended_when_the_parent_comes_back_one_write_a_day_at_most(db, monkeypatch):
    """« Rester connecté » : 90 jours après la dernière visite, prolongés par `/me/` (lu à chaque
    ouverture du portail), une seule écriture par jour ; décoché : 12 heures, jamais prolongées."""
    UserFactory(phone=PHONE)
    clock = [timezone.now().replace(hour=10, minute=0)]  # midi à Lubumbashi
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    kept, short = portal(), portal()
    post(kept, "auth/login/", phone=PHONE, password=TEST_PASSWORD, remember=True)
    post(short, "auth/login/", phone=PHONE, password=TEST_PASSWORD)

    def expires(client):
        return Session.objects.get(pk=client.cookies["sessionid"].value).expire_date

    opened = expires(kept)
    clock[0] += timedelta(hours=2)
    same_day = kept.get("/api/portal/me/")
    assert "sessionid" not in same_day.cookies and expires(kept) == opened
    assert short.get("/api/portal/me/").status_code == 200 and expires(short) < opened

    clock[0] += timedelta(hours=11)  # le lendemain, 13 heures après la connexion
    assert short.get("/api/portal/me/").json()["code"] == "not_authenticated"
    next_day = kept.get("/api/portal/me/")
    assert next_day.cookies["sessionid"]["max-age"] == 90 * 24 * 3600
    assert expires(kept) == clock[0] + timedelta(days=90)
    assert "sessionid" not in kept.get("/api/portal/me/").cookies

    clock[0] += timedelta(days=89)  # au-delà des 90 jours de la connexion : toujours connecté
    assert kept.get("/api/portal/me/").json()["phone"] == PHONE


def test_forgot_password_with_the_new_code_given_by_the_school_once(api, school, head):
    family = new_family(school, head)
    first_phone = portal()
    activate(first_phone, family.code)
    # Le premier code, imprimé sur la fiche d'inscription, ne change pas un mot de passe.
    assert reset(portal(), family.code).json()["code"] == "invalid_family_code"

    response = api(head).post(f"/api/families/{family.pk}/new-code/")

    assert response.status_code == 200
    new_code = response.json()["code"]
    assert new_code != family.code and response.json()["code_expires_at"]
    assert reset(portal(), family.code).json()["code"] == "invalid_family_code"
    other_phone = portal()
    assert reset(other_phone, new_code).status_code == 200
    # Mot de passe changé : l'autre téléphone est déconnecté, celui-ci connecté.
    assert first_phone.get("/api/portal/me/").status_code == 403
    assert other_phone.get("/api/portal/me/").status_code == 200
    assert reset(portal(), new_code).json()["code"] == "invalid_family_code"
    login = post(portal(), "auth/login/", phone=PHONE, password="Nyiragongo-2026")
    assert login.status_code == 200
    [renewed] = actions(school, "students.family_code_renewed")
    assert renewed.actor == head and renewed.entity_label == family.code
    assert new_code not in str(renewed.after)
    [entry] = actions(school, "portal.password_reset")
    assert entry.actor == reloaded(family).primary_user


def test_forgot_password_refused_for_a_staff_account(school, head):
    family = new_family(school, head, phone=head.phone)
    Family.all_schools.filter(pk=family.pk).update(primary_user=head)
    with use_school(school):
        students.renew_family_code(family, actor=head)

    response = reset(portal(), family.code, phone=head.phone)

    assert (response.status_code, response.json()["code"]) == (403, "staff_account")
    head.refresh_from_db()
    assert head.check_password(TEST_PASSWORD)


def test_new_code_needs_students_edit_and_stays_in_its_school(api, school, head, other_head):
    family = new_family(school, head)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    path = f"/api/families/{family.pk}/new-code/"

    assert api(teacher).post(path).status_code == 403
    assert api(other_head, host="beta.localhost").post(path).status_code == 404
    assert reloaded(family).code == family.code
    assert actions(school, "students.family_code_renewed") == []


def test_portal_endpoints_do_not_exist_at_a_school_address(school, head):
    family = new_family(school, head)
    at_school = portal("alpha.localhost")

    assert activate(at_school, family.code).status_code == 404
    login = post(at_school, "auth/login/", phone=head.phone, password=TEST_PASSWORD)
    assert login.status_code == 404
    assert reloaded(family).primary_user is None
