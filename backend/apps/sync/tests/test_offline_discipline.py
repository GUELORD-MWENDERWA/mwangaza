"""Infractions attribuées hors ligne (HL.2) : l'opération `incident.record` suit les règles de la
saisie en ligne, garde l'identifiant de l'appareil, s'applique une seule fois (même après
l'effacement de sa trace) et ne touche jamais une autre école."""

import pytest
from django.utils import timezone

from apps.academics.models import DisciplineIncident, DisciplineRule
from apps.academics.tests.test_grades import setup
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.sync.models import SyncOperation
from apps.sync.tests.test_devices import remember
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PUSH = "/api/sync/push/"


def incident_op(data, rule, *, incident=None, student="amani") -> dict:
    return {
        "op_id": str(uuid7()),
        "type": "incident.record",
        "payload": {
            "id": str(incident or uuid7()),
            "enrollment": data[student],
            "rule": str(rule.pk),
            "occurred_on": str(timezone.localdate()),
            "term": str(data["p1"].pk),
            "note": "Téléphone en classe",
        },
        "created_at": "2026-10-05T09:00:00Z",
    }


def push(client, op) -> dict:
    return client.post(PUSH, {"operations": [op]}).json()["results"][0]


@pytest.fixture
def data(school, head):
    data = setup(school, head)
    with use_school(school):
        data["rule"] = DisciplineRule.objects.create(label="Téléphone", points=3)
    return data


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


def test_an_offence_recorded_offline_is_written_once_with_the_id_of_the_device(
    api, school, teacher, data
):
    client = api(teacher)
    remember(client)
    incident = uuid7()
    op = incident_op(data, data["rule"], incident=incident)
    assert push(client, op)["status"] == "applied"
    assert push(client, op)["status"] == "duplicate"
    # Trace effacée (90 jours), l'appareil renvoie : rien de plus, même la liste changée depuis.
    with use_school(school):
        SyncOperation.objects.all().delete()
        DisciplineRule.objects.filter(pk=data["rule"].pk).update(is_active=False, points=9)
    assert push(client, {**op, "op_id": str(uuid7())})["status"] == "applied"
    with use_school(school):
        saved = DisciplineIncident.objects.get()
        assert saved.pk == incident and saved.points == 3 and saved.recorded_by == teacher
        assert AuditLog.objects.filter(action=Action.DISCIPLINE_INCIDENT_RECORDED).count() == 1


def test_an_offline_offence_follows_the_online_rules(api, school, teacher, data):
    client = api(teacher)
    remember(client)
    first = incident_op(data, data["rule"])
    assert push(client, first)["status"] == "applied"
    # Le même identifiant pour un autre élève : refusé, l'incident écrit ne change pas.
    stolen = incident_op(data, data["rule"], incident=first["payload"]["id"], student="josue")
    assert push(client, stolen)["error"]["code"] == "incident_id_taken"
    # Infraction retirée de la liste avant l'envoi : refusée avec la raison.
    with use_school(school):
        DisciplineRule.objects.filter(pk=data["rule"].pk).update(is_active=False)
    assert push(client, incident_op(data, data["rule"]))["error"]["code"] == "rule_inactive"
    # Sans `discipline.record` (le secrétariat envoie ses notes, pas d'infraction) : refusé.
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    clerk = api(secretary)
    remember(clerk)
    assert push(clerk, incident_op(data, data["rule"]))["error"]["code"] == "permission_denied"
    with use_school(school):
        assert DisciplineIncident.objects.count() == 1


def test_a_school_cannot_record_an_offence_in_another_school_offline(
    api, school, other_school, other_head, teacher, data
):
    client = api(teacher)
    remember(client)
    mine = incident_op(data, data["rule"])
    assert push(client, mine)["status"] == "applied"
    stranger = MembershipFactory(school=other_school, roles=["discipline_master"]).user
    other = api(stranger, "beta.localhost")
    remember(other)
    # Élève et infraction d'une autre école : introuvables.
    assert push(other, incident_op(data, data["rule"]))["status"] == "rejected"
    # Ses propres élève et infraction, mais l'identifiant d'un incident de l'autre école : pris.
    theirs = setup(other_school, other_head)
    with use_school(other_school):
        rule = DisciplineRule.objects.create(label="Retard", points=1)
    reused = incident_op(theirs, rule, incident=mine["payload"]["id"])
    assert push(other, reused)["error"]["code"] == "incident_id_taken"
    with use_school(school):
        assert DisciplineIncident.objects.count() == 1
    with use_school(other_school):
        assert DisciplineIncident.objects.count() == 0
