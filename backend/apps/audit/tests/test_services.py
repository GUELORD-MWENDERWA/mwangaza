"""Utilitaire d'enregistrement : `record()`, `changes()`, adresse et navigateur de la requête."""

import uuid
from datetime import date

import pytest
from django.db import transaction
from django.test import RequestFactory

from apps.accounts.models import Role
from apps.audit import services as audit
from apps.audit.actions import DOMAINS, Action, domain_of
from apps.audit.context import current_request_info
from apps.audit.middleware import AuditMiddleware
from apps.audit.models import AuditLog
from apps.core.tenancy import SchoolNotSetError, use_school
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def role(school):
    with use_school(school):
        return Role.objects.create(name="Chef d'atelier", permissions=["students.view"])


def test_an_entry_goes_to_the_current_school(school, other_school, role):
    actor = UserFactory()

    with use_school(school):
        log = audit.record(
            Action.ROLES_CREATED, role, actor=actor, after={"name": role.name}, label=role.name
        )

    assert log.school == school
    assert log.actor == actor
    assert log.created_by == actor
    assert (log.entity_type, log.entity_id, log.entity_label) == (
        "accounts.role",
        role.id,
        "Chef d'atelier",
    )
    assert (log.before, log.after) == (None, {"name": "Chef d'atelier"})
    assert not AuditLog.all_schools.filter(school=other_school).exists()


def test_label_is_the_name_of_the_object_by_default(school, role):
    with use_school(school):
        log = audit.record(Action.ROLES_DELETED, role, actor=None)

    assert log.entity_label == str(role)
    assert log.actor is None


def test_no_entry_without_a_school(role):
    with pytest.raises(SchoolNotSetError):
        audit.record(Action.ROLES_CREATED, role, actor=None)


def test_unknown_action_is_refused(school, role):
    with use_school(school), pytest.raises(ValueError, match=r"roles\.renamed"):
        audit.record("roles.renamed", role, actor=None)


@pytest.mark.parametrize(
    "data",
    [
        {"password": "x"},
        {"temporary_password": "x"},
        {"totp_secret": "x"},
        {"recovery_codes": ["x"]},
        {"account": {"secret": "x"}},
        {"accounts": [{"new_password": "x"}]},
    ],
)
def test_secrets_never_go_into_the_journal(school, role, data):
    # Mots de passe, codes et clés : jamais dans le journal (note de M6).
    with use_school(school):
        with pytest.raises(ValueError, match="secret"):
            audit.record(Action.ROLES_UPDATED, role, actor=None, after=data)
        with pytest.raises(ValueError, match="secret"):
            audit.record(Action.ROLES_UPDATED, role, actor=None, before=data)

    assert not AuditLog.all_schools.exists()


def test_values_are_stored_as_json(school, role):
    some_id = uuid.uuid4()

    with use_school(school):
        log = audit.record(
            Action.ROLES_UPDATED, role, actor=None, after={"id": some_id, "on": date(2026, 9, 26)}
        )

    log = AuditLog.all_schools.get(pk=log.pk)
    assert log.after == {"id": str(some_id), "on": "2026-09-26"}


def test_an_action_undone_leaves_no_entry(school, role):
    # L'entrée est écrite dans la transaction de l'action : l'une ne va pas sans l'autre.
    with use_school(school), pytest.raises(RuntimeError), transaction.atomic():
        audit.record(Action.ROLES_DELETED, role, actor=None)
        raise RuntimeError("l'action échoue après l'entrée")

    assert not AuditLog.all_schools.exists()


def test_changes_keeps_only_what_changed():
    before = {"name": "Caisse", "permissions": ["a"], "is_active": True}
    after = {"name": "Caisse", "permissions": ["a", "b"], "is_active": False}

    assert audit.changes(before, after) == (
        {"permissions": ["a"], "is_active": True},
        {"permissions": ["a", "b"], "is_active": False},
    )
    assert audit.changes(before, dict(before)) == ({}, {})


def test_domains_come_from_the_action_codes():
    assert domain_of(Action.STAFF_PASSWORD_RESET) == "staff"
    assert {"auth", "account", "roles", "staff"} <= set(DOMAINS)
    assert all(value.count(".") == 1 for value in Action.values)


# Adresse IP et navigateur de la requête


def test_ip_and_browser_come_from_the_request(school, role):
    request = RequestFactory().get(
        "/api/roles/", REMOTE_ADDR="41.243.12.7", HTTP_USER_AGENT="Mozilla/5.0 Edg/140.0"
    )
    logs = []

    def view(request):
        with use_school(school):
            logs.append(audit.record(Action.ROLES_CREATED, role, actor=None))

    AuditMiddleware(view)(request)

    assert (logs[0].ip, logs[0].user_agent) == ("41.243.12.7", "Mozilla/5.0 Edg/140.0")
    # Après la requête : plus rien.
    assert current_request_info().ip is None


def test_long_browser_names_are_cut(school, role):
    request = RequestFactory().get("/", HTTP_USER_AGENT="x" * 1000)
    logs = []

    def view(request):
        with use_school(school):
            logs.append(audit.record(Action.ROLES_CREATED, role, actor=None))

    AuditMiddleware(view)(request)

    assert len(logs[0].user_agent) == 255


def test_outside_a_request_there_is_no_address(school, role):
    # Commande, tâche Celery.
    with use_school(school):
        log = audit.record(Action.ROLES_CREATED, role, actor=None)

    assert (log.ip, log.user_agent) == (None, "")
