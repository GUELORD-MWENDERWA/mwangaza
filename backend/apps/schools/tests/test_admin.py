"""Écoles dans l'administration Django (A1, A2) : création avec le directeur, liste, suspension."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Membership, User
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

ADD = "/admin/schools/school/add/"
LIST = "/admin/schools/school/"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def form(**fields) -> dict:
    return {
        "code": "gamma",
        "name": "Institut Gamma",
        "official_name": "Institut technique Gamma (fictif)",
        "primary_color": "#7a3e00",
        "timezone": "Africa/Lubumbashi",
        "enabled_currencies": ["USD", "CDF"],
        "default_currency": "USD",
        "director_phone": "0000003001",
        "director_last_name": "Kasereka",
        "director_middle_name": "",
        "director_first_name": "Dieudonné",
        "status": "trial",
        "plan": "Essai",
        "trial_ends_on": "2026-12-15",
        "paid_until": "",
        **fields,
    }


def journal(school) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.order_by("created_at", "id"))


def test_create_a_school_with_its_head(admin_client, platform_admin):
    response = admin_client.post(ADD, form())

    assert response.status_code == 200, response.content.decode()[:3000]
    password = response.context["temporary_password"]
    assert password and password in response.content.decode()
    gamma = School.objects.get(code="gamma")
    assert gamma.primary_color == "#7A3E00"
    assert str(gamma.trial_ends_on) == "2026-12-15"
    head = User.objects.get(phone="+243000003001")
    assert head.check_password(password)
    assert head.must_change_password
    membership = Membership.objects.get(user=head, school=gamma)
    with use_school(gamma):
        assert [role.code for role in membership.roles.all()] == ["head"]
    assert [entry.action for entry in journal(gamma)] == [
        Action.SCHOOL_CREATED,
        Action.STAFF_ADDED,
    ]
    assert all(entry.actor == platform_admin for entry in journal(gamma))


def test_create_a_school_with_a_logo(admin_client):
    data = form(logo=SimpleUploadedFile("logo.png", PNG, "image/png"))

    assert admin_client.post(ADD, data).status_code == 200

    assert School.objects.get(code="gamma").logo.name.endswith(".png")


def test_head_with_an_existing_account(admin_client, school):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user

    response = admin_client.post(ADD, form(director_phone=teacher.phone, director_last_name=""))

    assert response.status_code == 200
    assert response.context["temporary_password"] is None
    assert Membership.objects.filter(user=teacher, school__code="gamma").exists()


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ({"director_last_name": ""}, "director_last_name"),
        ({"director_phone": "12"}, "director_phone"),
        ({"primary_color": "#ff0000"}, "primary_color"),
        ({"code": "admin"}, "code"),
        ({"code": "Gamma École"}, "code"),
        ({"enabled_currencies": ["USD"], "default_currency": "CDF"}, "default_currency"),
        ({"timezone": "Goma"}, "timezone"),
        ({"logo": SimpleUploadedFile("logo.png", b"%PDF-1.7", "image/png")}, "logo"),
    ],
)
def test_invalid_creation_is_refused(admin_client, fields, error):
    response = admin_client.post(ADD, form(**fields))

    assert response.status_code == 200
    assert error in response.context["adminform"].form.errors
    assert not School.objects.filter(code="gamma").exists()
    assert not User.objects.filter(phone="+243000003001").exists()


def test_the_list_shows_status_subscription_and_activity(admin_client, school, other_school, head):
    other_school.status = School.Status.SUSPENDED
    other_school.save()
    with use_school(school):
        AuditLog.objects.create(action=Action.AUTH_LOGIN, actor=head)

    content = admin_client.get(LIST).content.decode()

    assert "École Alpha (fictive)" in content and "École Beta (fictive)" in content
    assert "http://alpha.localhost:5173/app/support" in content
    # École suspendue : pas de session support.
    assert "beta.localhost:5173/app/support" not in content


def test_support_actions_are_not_school_activity(admin_client, school, platform_admin):
    with use_school(school):
        AuditLog.objects.create(action=Action.SUPPORT_STARTED, actor=platform_admin)

    response = admin_client.get(LIST)

    [alpha] = [row for row in response.context["cl"].result_list if row.pk == school.pk]
    assert alpha.last_activity_at is None


def test_last_activity_is_the_last_entry_of_the_school(admin_client, school, other_school, head):
    with use_school(school):
        first = AuditLog.objects.create(action=Action.AUTH_LOGIN, actor=head)
        last = AuditLog.objects.create(action=Action.AUTH_LOGIN, actor=None)

    rows = {row.pk: row for row in admin_client.get(LIST).context["cl"].result_list}

    assert first.created_at < last.created_at
    assert rows[school.pk].last_activity_at == last.created_at
    assert rows[other_school.pk].last_activity_at is None


def test_last_activity_is_shown_as_a_date(admin_client, school, head):
    from django.utils import timezone

    with use_school(school):
        entry = AuditLog.objects.create(action=Action.AUTH_LOGIN, actor=head)

    content = admin_client.get(LIST, HTTP_ACCEPT_LANGUAGE="fr").content.decode()

    assert f"{timezone.localtime(entry.created_at):%d/%m/%Y %H:%M}" in content


def test_suspend_and_reactivate_from_the_list(admin_client, school, platform_admin):
    admin_client.post(LIST, {"action": "suspend", "_selected_action": [str(school.pk)]})
    school.refresh_from_db()
    assert school.status == School.Status.SUSPENDED

    admin_client.post(LIST, {"action": "reactivate", "_selected_action": [str(school.pk)]})
    school.refresh_from_db()
    assert school.status == School.Status.ACTIVE

    actions = [entry.action for entry in journal(school)]
    assert actions == [Action.SCHOOL_SUSPENDED, Action.SCHOOL_REACTIVATED]


def test_changing_a_school_is_noted(admin_client, school):
    change = f"/admin/schools/school/{school.pk}/change/"
    page = admin_client.get(change)
    assert page.status_code == 200

    response = admin_client.post(
        change,
        {
            "code": "alpha",
            "name": "École Alpha",
            "official_name": "",
            "primary_color": "#0e5c6b",
            "timezone": "Africa/Lubumbashi",
            "enabled_currencies": ["USD", "CDF"],
            "default_currency": "USD",
            "status": "suspended",
            "plan": "Standard",
            "trial_ends_on": "",
            "paid_until": "2026-12-31",
        },
    )

    assert response.status_code == 302, response.context["adminform"].form.errors
    entries = journal(school)
    assert [entry.action for entry in entries] == [Action.SCHOOL_UPDATED, Action.SCHOOL_SUSPENDED]
    assert entries[0].after == {"name": "École Alpha"}


def test_a_school_is_never_deleted(admin_client, school):
    response = admin_client.get(f"/admin/schools/school/{school.pk}/delete/")

    assert response.status_code == 403
