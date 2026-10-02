"""Écoles dans la console de la plateforme (5.3, A1 à A3) : super-admin seulement, à l'adresse de la
console ; création avec le premier directeur, liste (élèves, dernière activité), modification de
l'identité et de l'abonnement, suspension et réactivation, notées dans le journal de l'école et
dans celui de la plateforme. Une école ne se supprime jamais."""

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, User
from apps.audit.actions import Action
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
SCHOOLS = "/api/console/schools/"


def form(**fields) -> dict:
    return {
        "code": "gamma",
        "name": "Institut Gamma",
        "official_name": "Institut technique Gamma (fictif)",
        "enabled_currencies": ["USD", "CDF"],
        "default_currency": "USD",
        "status": "trial",
        "plan": "Essai",
        "trial_ends_on": "2026-12-15",
        "paid_until": None,
        "head": {"phone": "0000003001", "last_name": "Kasereka", "first_name": "Dieudonné"},
        **fields,
    }


def journal(school) -> list[str]:
    with use_school(school):
        return list(AuditLog.objects.order_by("created_at", "id").values_list("action", flat=True))


def platform_journal() -> list[str]:
    return list(
        PlatformAuditLog.objects.order_by("created_at", "id").values_list("action", flat=True)
    )


def test_only_the_platform_admin_manages_schools_at_the_console(api, platform_admin, head, school):
    detail = f"{SCHOOLS}{school.pk}/"
    calls = [
        ("get", SCHOOLS, None),
        ("post", SCHOOLS, form()),
        ("get", detail, None),
        ("patch", detail, {"name": "Piratée"}),
        ("post", f"{detail}suspend/", None),
        ("post", f"{detail}reactivate/", None),
    ]
    for method, url, data in calls:

        def call(client, method=method, url=url, data=data):
            return client.get(url) if method == "get" else getattr(client, method)(url, data)

        assert call(api(head, host=CONSOLE)).status_code == 403
        assert call(api(platform_admin, host=CONSOLE, mfa=False)).status_code == 403
        # À l'adresse d'une école, ces points d'API n'existent pas.
        assert call(api(platform_admin)).status_code == 404
    school.refresh_from_db()
    assert (school.name, school.status) == ("École Alpha (fictive)", School.Status.ACTIVE)
    assert not School.objects.filter(code="gamma").exists()
    # Une école ne se supprime jamais : on la suspend.
    assert api(platform_admin, host=CONSOLE).delete(detail).status_code == 405


def test_create_a_school_with_its_head(api, platform_admin):
    response = api(platform_admin, host=CONSOLE).post(SCHOOLS, form())

    assert response.status_code == 201, response.json()
    data = response.json()
    gamma = School.objects.get(code="gamma")
    assert (data["school"]["id"], data["school"]["url"]) == (
        str(gamma.pk),
        "http://gamma.localhost:5173",
    )
    assert str(gamma.trial_ends_on) == "2026-12-15" and gamma.plan == "Essai"
    # Mot de passe provisoire renvoyé une seule fois, à transmettre au directeur.
    head = User.objects.get(phone="+243000003001")
    assert head.check_password(data["temporary_password"]) and head.must_change_password
    assert data["head"]["last_name"] == "Kasereka"
    with use_school(gamma):
        roles = Membership.objects.get(user=head, school=gamma).roles.all()
        assert [role.code for role in roles] == ["head"]
    assert journal(gamma) == [Action.SCHOOL_CREATED, Action.STAFF_ADDED]
    log = PlatformAuditLog.objects.get()
    assert (log.action, log.actor, log.entity_label) == (
        "school.created",
        platform_admin,
        "Institut Gamma",
    )
    assert log.after["code"] == "gamma" and log.after["trial_ends_on"] == "2026-12-15"


def test_head_with_an_existing_account_keeps_it(api, platform_admin, school):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    names = (teacher.last_name, teacher.first_name)

    data = (
        api(platform_admin, host=CONSOLE)
        .post(SCHOOLS, form(head={"phone": teacher.phone, "last_name": "Autre"}))
        .json()
    )

    assert data["temporary_password"] is None
    teacher.refresh_from_db()
    assert (teacher.last_name, teacher.first_name) == names
    assert Membership.objects.filter(user=teacher, school__code="gamma").exists()


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ({"head": {"phone": "0000003001", "last_name": ""}}, "head"),
        ({"head": {"phone": "12", "last_name": "Kasereka"}}, "head"),
        ({"code": "admin"}, "code"),
        ({"code": "Gamma École"}, "code"),
        ({"code": "alpha"}, "code"),
        ({"enabled_currencies": ["USD"], "default_currency": "CDF"}, "default_currency"),
        ({"status": "suspended"}, "status"),
    ],
)
def test_invalid_creation_creates_nothing(api, platform_admin, school, fields, error):
    response = api(platform_admin, host=CONSOLE).post(SCHOOLS, form(**fields))

    assert response.status_code == 400
    fields = response.json()["fields"]
    assert any(key.split(".")[0] == error for key in fields), fields
    assert School.objects.count() == 1
    assert not User.objects.filter(phone="+243000003001").exists()
    assert not PlatformAuditLog.objects.exists()


def test_the_list_counts_students_and_activity_without_support(
    api, platform_admin, school, other_school, head, django_assert_max_num_queries
):
    from apps.schools.tests.test_organisation_api import structure
    from apps.students.tests.conftest import enrolled

    group = structure(school, head)["group"]
    enrolled(school, head, group)
    enrolled(school, head, group, first_name="Esther", sex="F")
    with use_school(school):
        login = AuditLog.objects.create(action=Action.AUTH_LOGIN, actor=head)
        # Le support et le super-admin ne sont pas l'activité de l'école.
        AuditLog.objects.create(action=Action.SUPPORT_STARTED, actor=platform_admin)
    for code in ("delta", "epsilon", "zeta"):
        School.objects.create(code=code, name=f"École {code}")

    console = api(platform_admin, host=CONSOLE)
    with django_assert_max_num_queries(6):
        response = console.get(SCHOOLS)

    rows = {row["code"]: row for row in response.json()["results"]}
    assert (rows["alpha"]["student_count"], rows["beta"]["student_count"]) == (2, 0)
    last = timezone.localtime(login.created_at).isoformat()
    assert rows["alpha"]["last_activity_at"] == last
    assert rows["beta"]["last_activity_at"] is None
    assert [r["code"] for r in console.get(SCHOOLS, search="bet").json()["results"]] == ["beta"]
    other_school.status = School.Status.SUSPENDED
    other_school.save()
    suspended = console.get(SCHOOLS, status="suspended").json()["results"]
    assert [row["code"] for row in suspended] == ["beta"]


def test_subscription_changes_go_to_the_platform_journal_only(api, platform_admin, school):
    console = api(platform_admin, host=CONSOLE)
    detail = f"{SCHOOLS}{school.pk}/"

    data = console.patch(
        detail, {"name": "École Alpha", "plan": "Standard", "paid_until": "2026-12-31"}
    ).json()

    assert (data["name"], data["plan"], data["paid_until"]) == (
        "École Alpha",
        "Standard",
        "2026-12-31",
    )
    # L'école voit son nom changer, pas son abonnement.
    with use_school(school):
        entry = AuditLog.objects.get()
    assert (entry.action, entry.after) == (Action.SCHOOL_UPDATED, {"name": "École Alpha"})
    log = PlatformAuditLog.objects.get()
    assert log.action == "school.updated"
    assert log.after == {"name": "École Alpha", "plan": "Standard", "paid_until": "2026-12-31"}
    assert [entry["action"] for entry in console.get(detail).json()["history"]] == [
        "school.updated"
    ]
    # Suspendre passe par son action, jamais par une modification.
    assert console.patch(detail, {"status": "suspended"}).status_code == 400


def test_suspend_and_reactivate(api, platform_admin, school, other_school):
    console = api(platform_admin, host=CONSOLE)
    school.trial_ends_on = timezone.localdate()
    school.save()

    assert console.post(f"{SCHOOLS}{school.pk}/suspend/").json()["status"] == "suspended"
    assert api(None).get("/api/school/").status_code == 403
    # Encore en essai : réactivée, elle revient en essai.
    assert console.post(f"{SCHOOLS}{school.pk}/reactivate/").json()["status"] == "trial"

    assert journal(school) == [Action.SCHOOL_SUSPENDED, Action.SCHOOL_REACTIVATED]
    assert journal(other_school) == []
    assert platform_journal() == ["school.suspended", "school.reactivated"]


def test_the_admin_only_shows_schools(admin_client, school):
    assert admin_client.get("/admin/schools/school/").status_code == 200
    assert admin_client.get("/admin/schools/school/add/").status_code == 403
    change = f"/admin/schools/school/{school.pk}/change/"
    assert admin_client.get(change).status_code == 200
    admin_client.post(change, {"name": "Piratée", "code": "alpha"})
    school.refresh_from_db()
    assert school.name == "École Alpha (fictive)"
    # Lien vers la session support, à l'adresse de l'école (A3).
    content = admin_client.get("/admin/schools/school/").content.decode()
    assert "http://alpha.localhost:5173/app/support" in content
