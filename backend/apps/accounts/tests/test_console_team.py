"""Équipe de la plateforme (EQ.1) : chaque point de la console demande un droit, chaque rôle fixe
reçoit 403 hors des siens ; invitation, rôles et retrait (sessions coupées) au journal avec leur
auteur ; la plateforme garde toujours un propriétaire."""

from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import URLResolver, get_resolver

from apps.accounts import platform_roles as team
from apps.accounts.login import MFA_SESSION_KEY
from apps.accounts.models import User
from apps.accounts.permissions import HasPlatformPermission, platform_rights_required
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.notifications import console as alerts
from apps.notifications.models import PushSubscription
from apps.schools.models import School
from tests.factories import SchoolFactory, UserFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
TEAM = "/api/console/team/"


def member(role: str) -> User:
    return UserFactory(is_platform_admin=True, platform_roles=[role])


def _routes(patterns, prefix=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _routes(pattern.url_patterns, prefix + str(pattern.pattern))
        else:
            yield prefix + str(pattern.pattern), pattern.callback


def test_every_console_endpoint_demands_a_platform_right():
    """Garde : un point de la console ajouté sans droit déclaré fait échouer ce test."""
    routes = [
        (route, callback)
        for route, callback in _routes(get_resolver().url_patterns)
        if route.startswith("api/") and "console/" in route
    ]
    assert len(routes) >= 15
    for route, callback in routes:
        cls = getattr(callback, "cls", None) or callback.view_class
        assert cls.permission_classes == [HasPlatformPermission], route
        actions = getattr(callback, "actions", None) or {
            method: None for method in ("get", "post", "patch", "delete") if hasattr(cls, method)
        }
        for method, action in actions.items():
            view = cls()
            if action is not None:
                view.action = action
            rights = platform_rights_required(SimpleNamespace(method=method.upper()), view)
            assert rights and rights <= set(team.PLATFORM_PERMISSIONS), (route, method)


@pytest.mark.parametrize("role", list(team.PLATFORM_ROLES))
def test_each_role_gets_403_outside_its_rights_on_every_console_endpoint(api, school, head, role):
    user = member(role)
    rights = team.PLATFORM_ROLES[role][1]
    live = school.pk
    sandbox = SchoolFactory(code="essai", environment=School.Environment.TEST).pk
    other = member("support").pk
    calls = [
        ("get", "/api/console/dashboard/", None, {team.SCHOOLS_VIEW}),
        ("get", "/api/console/schools/", None, {team.SCHOOLS_VIEW, team.DEMOS_MANAGE}),
        ("get", f"/api/console/schools/{live}/", None, {team.SCHOOLS_VIEW}),
        ("post", "/api/console/schools/", {"environment": "live"}, {team.SCHOOLS_MANAGE}),
        ("post", "/api/console/schools/", {"environment": "test"}, {team.DEMOS_MANAGE}),
        ("post", "/api/console/schools/demo/", {}, {team.DEMOS_MANAGE}),
        ("patch", f"/api/console/schools/{sandbox}/", {}, {team.DEMOS_MANAGE}),
        ("post", f"/api/console/schools/{sandbox}/stop/", {}, {team.DEMOS_MANAGE}),
        ("post", f"/api/console/schools/{sandbox}/delete/", {}, {team.DEMOS_MANAGE}),
        ("post", f"/api/console/schools/{live}/suspend/", None, {team.SCHOOLS_MANAGE}),
        ("post", f"/api/console/schools/{live}/reactivate/", None, {team.SCHOOLS_MANAGE}),
        ("post", f"/api/console/schools/{live}/stop/", {}, {team.SCHOOLS_STOP}),
        ("get", "/api/console/platform/", None, {team.IDENTITY_EDIT}),
        ("patch", "/api/console/platform/", {}, {team.IDENTITY_EDIT}),
        ("delete", "/api/console/platform/logo/", None, {team.IDENTITY_EDIT}),
        ("get", "/api/console/demo-requests/", None, {team.LEADS_MANAGE}),
        ("get", "/api/console/site/entries/", None, {team.SITE_EDIT}),
        ("post", "/api/console/site/entries/", {}, {team.SITE_EDIT}),
        ("patch", "/api/console/site/banner/", {}, {team.SITE_EDIT}),
        ("post", "/api/console/site/testimonials/", {}, {team.SITE_EDIT}),
        ("get", "/api/console/site/references/", None, {team.SITE_EDIT}),
        ("get", "/api/console/site/plans/", None, {team.SITE_EDIT}),
        ("get", "/api/console/site/partners/", None, {team.SITE_EDIT}),
        ("patch", "/api/console/site/pages/home/", {}, {team.SITE_EDIT}),
        ("get", "/api/console/site/articles/", None, {team.SITE_EDIT}),
        ("post", "/api/console/site/articles/preview/", {"body": ""}, {team.SITE_EDIT}),
        ("get", "/api/console/site/photos/", None, {team.SITE_EDIT}),
        ("patch", "/api/console/site/social/", {}, {team.SITE_EDIT}),
        ("get", "/api/console/announcements/", None, {team.NEWS_PUBLISH}),
        ("post", "/api/console/announcements/", {}, {team.NEWS_PUBLISH}),
        (
            "post",
            "/api/console/alerts/unsubscribe/",
            {"endpoint": "https://push.example/x"},
            {team.AUDIT_VIEW, team.LEADS_MANAGE},
        ),
        ("get", "/api/console/devices/", None, {team.HEALTH_VIEW}),
        ("get", "/api/console/audit/", None, {team.AUDIT_VIEW}),
        ("get", "/api/console/accounts/", None, {team.ACCOUNTS_SUPPORT}),
        ("post", f"/api/console/accounts/{head.pk}/reset-totp/", None, {team.ACCOUNTS_SUPPORT}),
        ("get", "/api/console/support-sessions/", None, {team.ACCOUNTS_SUPPORT, team.AUDIT_VIEW}),
        ("get", TEAM, None, {team.TEAM_MANAGE}),
        ("get", f"{TEAM}roles/", None, {team.TEAM_MANAGE}),
        ("post", TEAM, {}, {team.TEAM_MANAGE}),
        ("patch", f"{TEAM}{other}/", {}, {team.TEAM_MANAGE}),
    ]
    client = api(user, host=CONSOLE)
    live_hidden = team.DEMOS_MANAGE in rights and team.SCHOOLS_VIEW not in rights
    for method, path, data, required in calls:
        args = (path,) if method in ("get", "delete") else (path, data)
        status = getattr(client, method)(*args).status_code
        if rights & required:
            assert status != 403, (role, method, path)
        elif str(live) in path and live_hidden:
            # Essais et démonstrations sans `platform.schools.view` : un espace réel n'existe pas.
            assert status == 404, (role, method, path)
        else:
            assert status == 403, (role, method, path, status)

    # Session support dans une école (données de l'école) : le droit du support seulement.
    started = api(user).post("/api/support/", {"reason": "L'école demande de l'aide"})
    assert (started.status_code == 403) == (team.ACCOUNTS_SUPPORT not in rights)

    # Administration Django (elle peut tout changer) : le propriétaire seulement.
    admin = Client(HTTP_HOST="localhost")
    admin.force_login(user)
    session = admin.session
    session[MFA_SESSION_KEY] = True
    session.save()
    assert admin.get("/admin/").status_code == (200 if role == team.OWNER else 302)


def test_sales_see_only_sandbox_and_demonstration_spaces(api, school):
    sandbox = SchoolFactory(code="essai", environment=School.Environment.TEST)
    listed = api(member("commercial"), host=CONSOLE).get("/api/console/schools/").json()
    assert [row["code"] for row in listed["results"]] == [sandbox.code]


def test_owner_invites_changes_and_removes_a_member_each_step_in_the_journal(
    api, platform_admin, head
):
    owner = api(platform_admin, host=CONSOLE)
    data = {
        "phone": "0971112233",
        "last_name": "Kahindo",
        "first_name": "Esther",
        "roles": ["support", "commercial"],
    }
    invited = owner.post(TEAM, data)
    assert invited.status_code == 201
    person = User.objects.get(phone="+243971112233")
    assert person.is_platform_admin and person.must_change_password
    assert person.platform_roles == ["commercial", "support"]
    assert person.check_password(invited.json()["temporary_password"])
    # Un compte d'école garde son numéro : un membre de l'équipe a le sien.
    assert owner.post(TEAM, {**data, "phone": head.phone}).json()["code"] == "phone_in_use"
    assert owner.post(TEAM, data).json()["code"] == "already_in_team"
    assert owner.post(TEAM, {**data, "phone": "0971112234", "roles": []}).status_code == 400

    # Nouveaux rôles : effectifs dès la requête suivante du membre.
    session = api(person, host=CONSOLE)
    assert session.get("/api/console/demo-requests/").status_code == 200
    assert owner.patch(f"{TEAM}{person.pk}/", {"roles": ["technical"]}).status_code == 200
    assert session.get("/api/console/demo-requests/").status_code == 403
    me = session.get("/api/me/").json()
    assert me["platform_roles"] == ["technical"]
    assert team.HEALTH_VIEW in me["platform_permissions"]

    # Retrait : sa session ouverte ne sert plus, tout de suite.
    assert session.get("/api/console/devices/").status_code == 200
    assert owner.post(f"{TEAM}{person.pk}/remove/").status_code == 204
    assert session.get("/api/console/devices/").status_code == 403
    person.refresh_from_db()
    assert not person.is_active and person.platform_roles == []
    assert [row["id"] for row in owner.get(TEAM).json()["results"]] == [str(platform_admin.pk)]

    # Réinvité : il repart avec un mot de passe provisoire.
    assert owner.post(TEAM, {**data, "roles": ["support"]}).status_code == 201
    person.refresh_from_db()
    assert person.is_active and person.platform_roles == ["support"]

    journal = PlatformAuditLog.objects.filter(entity_id=str(person.pk)).order_by("created_at")
    assert [(e.action, e.actor, e.before, e.after) for e in journal] == [
        (PlatformAction.TEAM_MEMBER_INVITED, platform_admin, None, {"roles": data["roles"][::-1]}),
        (
            PlatformAction.TEAM_ROLES_CHANGED,
            platform_admin,
            {"roles": ["commercial", "support"]},
            {"roles": ["technical"]},
        ),
        (PlatformAction.TEAM_MEMBER_REMOVED, platform_admin, {"roles": ["technical"]}, None),
        (PlatformAction.TEAM_MEMBER_INVITED, platform_admin, None, {"roles": ["support"]}),
    ]


def test_the_platform_always_keeps_an_owner(api, platform_admin):
    owner = api(platform_admin, host=CONSOLE)
    myself = f"{TEAM}{platform_admin.pk}/"
    assert owner.post(myself + "remove/").json()["code"] == "last_owner"
    assert owner.patch(myself, {"roles": ["support"]}).json()["code"] == "last_owner"
    assert not PlatformAuditLog.objects.filter(action__startswith="team.").exists()

    User.objects.create_superuser("0971112244", "secret-123", last_name="Second")
    assert owner.patch(myself, {"roles": ["support"]}).status_code == 200
    # Plus propriétaire : l'équipe ne lui est plus ouverte.
    assert owner.get(TEAM).status_code == 403


def test_alerts_go_to_the_members_whose_work_they_concern(platform_admin):
    sales, technical = member("commercial"), member("technical")
    for user in (platform_admin, sales, technical):
        PushSubscription.objects.create(
            user=user,
            app="console",
            endpoint=f"https://push.example/{user.pk}",
            p256dh="k",
            auth="a",
        )

    def receivers(action, concerned=None):
        return {row.user for row in alerts.subscriptions(action, concerned).select_related("user")}

    assert receivers(PlatformAction.ACCESS_LOGIN) == {platform_admin, technical}
    assert receivers(alerts.DEMO_REQUEST) == {platform_admin, sales}
    # Le compte qui sert est prévenu lui aussi : son mot de passe a pu être volé.
    assert receivers(PlatformAction.ACCESS_LOGIN, sales.pk) == {platform_admin, technical, sales}
