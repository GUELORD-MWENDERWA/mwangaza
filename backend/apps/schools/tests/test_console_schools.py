"""Écoles dans la console de la plateforme (5.3, A1 à A3) : super-admin seulement, à l'adresse de la
console ; création avec le premier directeur, liste (élèves, dernière activité), modification de
l'identité et de l'abonnement, suspension, arrêt et réactivation, notées dans le journal de l'école
et dans celui de la plateforme ; type d'espace (réel, essai, démonstration) fixé à la création
(4.15). Suppression d'un espace d'essai ou de démonstration : `test_deletion.py`."""

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, User
from apps.audit.actions import Action
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.core.tenancy import use_school
from apps.schools import services
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
        "head": {"phone": "0100003001", "last_name": "Kasereka", "first_name": "Dieudonné"},
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
        ("post", f"{detail}stop/", {"reason": "Piratage", "confirm": "alpha"}),
        ("post", f"{detail}reactivate/", None),
        ("post", f"{detail}delete/", {"confirm": "alpha"}),
        ("post", f"{SCHOOLS}demo/", {"code": "gamma", "name": "Gamma", "profile": "small"}),
        ("post", f"{detail}reset/", {"confirm": "alpha"}),
        ("get", f"{detail}access-sheet/?output=html", None),
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
    # Un espace réel ne se supprime jamais (essai et démonstration : `test_deletion.py`).
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
    # Sans type choisi : un espace réel (jamais supprimable).
    assert gamma.environment == School.Environment.LIVE
    # Mot de passe provisoire renvoyé une seule fois, à transmettre au directeur.
    head = User.objects.get(phone="+243100003001")
    assert head.check_password(data["temporary_password"]) and head.must_change_password
    assert data["head"]["last_name"] == "Kasereka"
    with use_school(gamma):
        roles = Membership.objects.get(user=head, school=gamma).roles.all()
        assert [role.name for role in roles] == ["Directeur"]
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
        ({"head": {"phone": "0100003001", "last_name": ""}}, "head"),
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
    assert not User.objects.filter(phone="+243100003001").exists()
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


def test_stop_closes_the_space_keeps_its_data_and_needs_a_reason(
    api, platform_admin, school, other_school, head
):
    console = api(platform_admin, host=CONSOLE)
    MembershipFactory(user=head, school=other_school, roles=["teacher"])
    stop = f"{SCHOOLS}{school.pk}/stop/"

    reason = "L'école a quitté la plateforme"
    assert console.post(stop, {"reason": " ", "confirm": school.code}).status_code == 400
    # Action sans retour (EQ.2) : sans le code de l'école retapé, rien ne change.
    assert console.post(stop, {"reason": reason}).status_code == 400
    wrong = console.post(stop, {"reason": reason, "confirm": "beta"})
    assert wrong.status_code == 400
    assert "confirm" in wrong.json()["fields"]
    assert api(head).get("/api/school/").status_code == 200

    stopped = console.post(stop, {"reason": reason, "confirm": f" {school.code.upper()} "})
    assert stopped.json()["status"] == "stopped"

    # Plus personne n'y entre, ni à son adresse ni depuis une autre école ; rien n'est supprimé.
    refused = api(head).get("/api/school/")
    assert (refused.status_code, refused.json()["code"]) == (403, "school_stopped")
    mine = api(head, host="beta.localhost").get("/api/me/").json()["schools"]
    assert [item["code"] for item in mine] == ["beta"]
    assert Membership.objects.filter(user=head, school=school, is_active=True).exists()
    log = PlatformAuditLog.objects.get()
    assert (log.action, log.actor) == ("school.stopped", platform_admin)
    assert (log.before, log.after) == (
        {"status": "active"},
        {"status": "stopped", "reason": reason},
    )
    # Déjà fermé : « Suspendre » n'y change rien ; une erreur se rattrape en le relançant.
    assert console.post(f"{SCHOOLS}{school.pk}/suspend/").json()["status"] == "stopped"
    assert console.post(f"{SCHOOLS}{school.pk}/reactivate/").json()["status"] == "active"
    assert journal(school) == [Action.SCHOOL_STOPPED, Action.SCHOOL_REACTIVATED]
    assert platform_journal() == ["school.stopped", "school.reactivated"]


def test_the_kind_of_space_is_chosen_at_creation_and_never_changes(api, platform_admin, school):
    console = api(platform_admin, host=CONSOLE)

    created = console.post(SCHOOLS, form(environment="test")).json()["school"]

    assert created["environment"] == "test"
    assert PlatformAuditLog.objects.get().after["environment"] == "test"
    for kind, codes in (("live", ["alpha"]), ("test", ["gamma"]), ("demo", [])):
        rows = console.get(SCHOOLS, environment=kind).json()["results"]
        assert [row["code"] for row in rows] == codes
    # Ignoré par la modification, refusé par le service : on repart d'un espace neuf.
    detail = f"{SCHOOLS}{created['id']}/"
    assert console.patch(detail, {"environment": "live"}).json()["environment"] == "test"
    gamma = School.objects.get(code="gamma")
    with pytest.raises(ValueError, match="type"):
        services.update_school(gamma, actor=platform_admin, environment="live")
    gamma.refresh_from_db()
    assert gamma.environment == School.Environment.TEST


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
