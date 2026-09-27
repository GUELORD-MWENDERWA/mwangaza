"""`/api/audit/` : journal d'audit de l'école (M6), en lecture seule, permission `audit.view`."""

import io
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import openpyxl
import pytest

from apps.accounts.models import Role
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

AUDIT = "/api/audit/"
GOMA = ZoneInfo("Africa/Lubumbashi")


def entry(school, action=Action.ROLES_CREATED, *, at=None, **fields) -> AuditLog:
    fields = {"entity_type": "accounts.role", "entity_label": "Chef d'atelier", **fields}
    with use_school(school):
        if at is None:
            return AuditLog.objects.create(action=action, **fields)
        with mock.patch("django.utils.timezone.now", return_value=at):
            return AuditLog.objects.create(action=action, **fields)


def ids(response) -> list[str]:
    assert response.status_code == 200, response.content
    return [item["id"] for item in response.json()["results"]]


@pytest.fixture
def promoter(school):
    return MembershipFactory(school=school, roles=["promoter"]).user


# Qui peut lire le journal


def test_head_and_promoter_read_the_journal(api, school, head, promoter):
    log = entry(school)

    for user in (head, promoter):
        assert ids(api(user).get(AUDIT)) == [str(log.id)]


@pytest.mark.parametrize(
    "role", ["cashier", "accountant", "secretary", "study_director", "discipline_master", "teacher"]
)
def test_other_roles_cannot_read_it(api, school, role):
    user = MembershipFactory(school=school, roles=[role]).user
    log = entry(school)

    for path in (AUDIT, f"{AUDIT}{log.id}/"):
        response = api(user).get(path)
        assert response.status_code == 403
        assert response.json()["code"] == "permission_denied"


def test_anonymous_is_refused(api, school):
    response = api().get(AUDIT)

    assert response.status_code == 403
    assert response.json()["code"] == "not_authenticated"


def test_two_factor_authentication_is_required(api, head):
    response = api(head, mfa=False).get(AUDIT)

    assert response.status_code == 403
    assert response.json()["code"] == "totp_required"


# Isolation des écoles


def test_a_school_sees_only_its_own_journal(api, school, other_school, head, other_head):
    mine, theirs = entry(school), entry(other_school)

    assert ids(api(head).get(AUDIT)) == [str(mine.id)]
    assert ids(api(other_head, "beta.localhost").get(AUDIT)) == [str(theirs.id)]

    response = api(head).get(f"{AUDIT}{theirs.id}/")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    # Le directeur de l'une n'a aucun droit à l'adresse de l'autre.
    assert api(head, "beta.localhost").get(AUDIT).status_code == 403


def test_the_journal_cannot_be_written_through_the_api(api, school, head):
    log = entry(school)
    client = api(head)

    assert client.post(AUDIT, {"action": "roles.created"}).status_code == 405
    assert client.patch(f"{AUDIT}{log.id}/", {"entity_label": "x"}).status_code == 405
    assert client.delete(f"{AUDIT}{log.id}/").status_code == 405
    assert AuditLog.all_schools.get().entity_label == "Chef d'atelier"


# Contenu d'une entrée


def test_an_entry_says_who_did_what_on_what(api, school, head):
    actor = MembershipFactory(school=school, roles=["accountant"]).user
    role_id = uuid7()
    log = entry(
        school,
        Action.ROLES_UPDATED,
        actor=actor,
        entity_id=role_id,
        before={"permissions": ["students.view"]},
        after={"permissions": ["students.view", "students.edit"]},
        ip="41.243.12.7",
        user_agent="Mozilla/5.0 Edg/140.0",
    )

    data = api(head).get(f"{AUDIT}{log.id}/").json()

    assert data == {
        "id": str(log.id),
        "created_at": data["created_at"],
        "action": "roles.updated",
        "domain": "roles",
        "actor": {
            "id": str(actor.id),
            "last_name": actor.last_name,
            "middle_name": actor.middle_name,
            "first_name": actor.first_name,
        },
        "by_support": False,
        "entity_type": "accounts.role",
        "entity_id": str(role_id),
        "entity_label": "Chef d'atelier",
        "role_code": None,
        "before": {"permissions": ["students.view"]},
        "after": {"permissions": ["students.view", "students.edit"]},
        "ip": "41.243.12.7",
        "user_agent": "Mozilla/5.0 Edg/140.0",
    }


def test_support_is_shown_as_mwangaza_support(api, school, head):
    # Le super-admin n'est pas nommé : l'interface affiche « Support Mwangaza » (M6).
    support = UserFactory(is_platform_admin=True)
    log = entry(school, Action.ACCOUNT_TOTP_RESET, actor=support)

    data = api(head).get(f"{AUDIT}{log.id}/").json()

    assert data["actor"] is None
    assert data["by_support"] is True


def test_newest_first_by_pages_of_50(api, school, head):
    logs = [entry(school) for _ in range(51)]

    first = api(head).get(AUDIT).json()
    second = api(head).get(AUDIT, page=2).json()

    assert first["count"] == 51
    assert [item["id"] for item in first["results"]] == [str(log.id) for log in logs[:0:-1]]
    assert [item["id"] for item in second["results"]] == [str(logs[0].id)]


# Filtres (M6 : personne, action, domaine, date, recherche)


def test_filter_by_person(api, school, head):
    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    by_head, _other = entry(school, actor=head), entry(school, actor=cashier)

    assert ids(api(head).get(AUDIT, actor=head.id)) == [str(by_head.id)]


def test_filter_by_action_and_domain(api, school, head):
    created = entry(school, Action.ROLES_CREATED)
    deleted = entry(school, Action.ROLES_DELETED)
    login = entry(school, Action.AUTH_LOGIN)

    assert ids(api(head).get(AUDIT, action="roles.deleted")) == [str(deleted.id)]
    assert ids(api(head).get(AUDIT, domain="roles")) == [str(deleted.id), str(created.id)]
    assert ids(api(head).get(AUDIT, domain="auth")) == [str(login.id)]


def test_history_of_one_object(api, school, head):
    role_id = uuid7()
    first, second = entry(school, entity_id=role_id), entry(school, entity_id=role_id)
    entry(school, entity_id=uuid7())

    assert ids(api(head).get(AUDIT, entity=role_id)) == [str(second.id), str(first.id)]


def test_filter_by_dates_of_goma(api, school, head):
    early = entry(school, at=datetime(2026, 9, 20, 10, 0, tzinfo=GOMA))
    late_evening = entry(school, at=datetime(2026, 9, 25, 23, 30, tzinfo=GOMA))
    # 00:30 à Goma, le 26 : encore le 25 en temps universel.
    after_midnight = entry(school, at=datetime(2026, 9, 26, 0, 30, tzinfo=GOMA))
    client = api(head)

    assert ids(client.get(AUDIT, since="2026-09-26")) == [str(after_midnight.id)]
    assert ids(client.get(AUDIT, until="2026-09-25")) == [str(late_evening.id), str(early.id)]
    assert ids(client.get(AUDIT, since="2026-09-21", until="2026-09-25")) == [str(late_evening.id)]


def test_search_by_name_of_the_object(api, school, head):
    workshop = entry(school, entity_label="Chef d'atelier")
    entry(school, entity_label="Kambale Muhindo Patrice")

    assert ids(api(head).get(AUDIT, search="ATELIER")) == [str(workshop.id)]


@pytest.mark.parametrize(
    "params",
    [
        {"actor": "pas-un-identifiant"},
        {"action": "roles.renamed"},
        {"domain": "cuisine"},
        {"since": "26/09/2026"},
        {"since": "2026-09-26", "until": "2026-09-25"},
    ],
)
def test_invalid_filters_are_refused(api, school, head, params):
    assert api(head).get(AUDIT, **params).status_code == 400


# Personnes du journal (filtre « Personne » de M6)


def test_actors_are_the_people_of_the_school_journal(api, school, other_school, head, promoter):
    kavira = UserFactory(last_name="Kavira")
    elsewhere = UserFactory(last_name="Ailleurs")
    admin = UserFactory(last_name="Support", is_platform_admin=True)
    entry(school, actor=kavira)
    entry(school, actor=kavira)
    entry(school, actor=head)
    entry(school, actor=admin)  # le support n'est pas nommé à l'école
    entry(school, actor=head, impersonated_by=admin)
    entry(other_school, actor=elsewhere)

    response = api(promoter).get(f"{AUDIT}actors/")

    assert response.status_code == 200
    assert {person["id"] for person in response.json()} == {str(kavira.id), str(head.id)}
    assert set(response.json()[0]) == {"id", "last_name", "middle_name", "first_name"}


def test_actors_need_audit_view(api, cashier):
    assert api(cashier).get(f"{AUDIT}actors/").status_code == 403


def test_a_system_role_without_its_own_name_comes_with_its_code(api, school, head):
    with use_school(school):
        cashier = Role.objects.get(code="cashier")
        workshop = Role.objects.create(name="Chef d'atelier")
    entry(school, entity_id=cashier.id, entity_label="")
    entry(school, entity_id=workshop.id, entity_label="Chef d'atelier")
    entry(school, action=Action.STAFF_ADDED, entity_type="accounts.membership", entity_label="")

    results = api(head).get(AUDIT).json()["results"]

    assert [item["role_code"] for item in results] == [None, None, "cashier"]


def test_export_gives_the_filtered_period_of_the_school_and_is_itself_logged(
    api, school, other_school, head, cashier
):
    entry(school, at=datetime(2026, 9, 10, 23, 30, tzinfo=GOMA), entity_label="Dans la période")
    entry(school, at=datetime(2026, 9, 11, 0, 30, tzinfo=GOMA), entity_label="Le lendemain")
    entry(other_school, at=datetime(2026, 9, 10, 9, 0, tzinfo=GOMA), entity_label="Autre école")
    client = api(head)
    period = {"since": "2026-09-01", "until": "2026-09-10"}

    response = client.get(f"{AUDIT}export/", **period)
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    labels = [row[3] for row in sheet.iter_rows(min_row=2, values_only=True)]

    assert response.status_code == 200, response.content
    assert labels == ["Dans la période"]
    with use_school(school):
        exported = AuditLog.objects.get(action=Action.AUDIT_EXPORTED)
    assert exported.actor == head and exported.after == period
    # Période obligatoire, une année au plus ; `audit.view` exigé.
    assert client.get(f"{AUDIT}export/", since="2026-09-01").status_code == 400
    too_long = client.get(f"{AUDIT}export/", since="2025-09-01", until="2026-09-10")
    assert too_long.status_code == 400
    assert api(cashier).get(f"{AUDIT}export/", **period).status_code == 403
