"""Pointage à l'entrée (6.3) : opération hors ligne `attendance.scan`. Un passage s'enregistre une
seule fois, rejoué ou lu par deux appareils ; retard après l'heure de l'école ; carte révoquée,
inconnue ou d'une autre école refusée ; le jeton n'est gardé nulle part."""

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.attendance import cards
from apps.attendance.models import AttendanceRecord, IdCard
from apps.audit.models import AuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.students.tests.conftest import enrolled
from apps.sync.tests.test_devices import remember
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PUSH = "/api/sync/push/"


def yesterday(school, hour, minute) -> str:
    day = timezone.localdate() - timedelta(days=1)
    return datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(school.timezone)).isoformat()


def scan(seen_at, *, token=None, **holder) -> dict:
    payload = {"id": str(uuid7()), "seen_at": seen_at, **holder}
    if token:
        payload["card_hash"] = cards.fingerprint(token)
    return {"op_id": str(uuid7()), "type": "attendance.scan", "payload": payload}


def push(client, op) -> dict:
    return client.post(PUSH, {"operations": [op]}).json()["results"][0]


@pytest.fixture
def gate(school):
    """Directeur de discipline à la porte, sa tablette enregistrée."""
    return MembershipFactory(school=school, roles=["discipline_master"]).user


@pytest.fixture
def pupils(school, head, alpha):
    josue = enrolled(school, head, alpha["group"], last_name="Kambale", first_name="Josué")
    amina = enrolled(school, head, alpha["group"], last_name="Mapendo", first_name="Amina")
    school.settings = {**school.settings, "card": {"valid_until": "2099-08-31"}}
    school.save()
    with use_school(school):
        [issued] = cards.issue(actor=head, enrollments=list(cards.current_enrollments()[:1]))
    assert issued.card.student_id == josue.pk
    return josue, amina, issued.token


def test_a_card_read_offline_is_recorded_once_whatever_the_device_or_replay(
    api, school, gate, pupils
):
    josue, _amina, token = pupils
    first = api(gate)
    remember(first)
    op = scan(yesterday(school, 7, 30), token=token)
    result = push(first, op)
    assert result["status"] == "applied", result
    assert (result["result"]["status"], result["result"]["already"]) == ("present", False)
    assert push(first, op)["status"] == "duplicate"
    # Une autre tablette, à l'autre porte, lit la même carte plus tard : « déjà passé ».
    second = api(gate)
    remember(second, label="Android · Chrome")
    later = push(second, scan(yesterday(school, 7, 50), token=token))
    assert later["result"]["already"] is True
    with use_school(school):
        record = AttendanceRecord.objects.get()
        assert (record.student_id, record.method, str(record.pk)) == (
            josue.pk,
            "qr",
            op["payload"]["id"],
        )
        # Seule l'empreinte est gardée ; le jeton n'est ni sur la carte ni au journal.
        card = IdCard.objects.get()
        assert card.token_hash == cards.fingerprint(token) != token
        assert token not in json.dumps(list(AuditLog.objects.values_list("after", flat=True)))


def test_lateness_manual_entry_and_refused_cards_follow_the_rules(
    api, school, head, gate, pupils, other_school, other_head, beta
):
    josue, amina, token = pupils
    client = api(gate)
    remember(client)
    # Matricule tapé, après l'heure limite réglée par l'école : retard.
    limit = api(head).patch("/api/school/settings/", {"attendance": {"late_after": "08:00"}})
    assert limit.json()["attendance"] == {"late_after": "08:00"}
    on_time = push(client, scan(yesterday(school, 7, 58), student=str(josue.pk)))
    assert on_time["result"]["status"] == "present"
    late = push(client, scan(yesterday(school, 8, 5), student=str(amina.pk)))
    assert late["result"]["status"] == "late"
    with use_school(school):
        assert AttendanceRecord.objects.get(student=amina).method == "manual"
        card = IdCard.objects.get()
        cards.revoke(card, actor=head, reason="lost")
    # Lue hors ligne avant la révocation : gardée ; lue après : refusée.
    assert push(client, scan(yesterday(school, 7, 30), token=token))["status"] == "applied"
    now = timezone.now().isoformat()
    assert push(client, scan(now, token=token))["error"]["code"] == "card_revoked"
    # Carte d'une autre école (ou inventée) : inconnue ici.
    stranger = enrolled(other_school, other_head, beta["group"], last_name="Safari")
    with use_school(other_school):
        [foreign] = cards.issue(actor=other_head, enrollments=list(cards.current_enrollments()))
    assert foreign.card.student_id == stranger.pk
    assert push(client, scan(now, token=foreign.token))["error"]["code"] == "card_unknown"
    assert push(client, scan(now, student=str(stranger.pk)))["status"] == "rejected"
    # Horloge de l'appareil en avance d'une heure : refusé, pas de passage du lendemain.
    ahead = (timezone.now() + timedelta(hours=1)).isoformat()
    assert push(client, scan(ahead, student=str(josue.pk)))["error"]["code"] == "device_clock_ahead"


def test_staff_cards_scan_and_scanning_needs_its_right(api, school, head, gate, pupils):
    with use_school(school):
        member = cards.staff().get(user=gate)
        [issued] = cards.issue(actor=head, members=[member])
    client = api(gate)
    remember(client)
    result = push(client, scan(yesterday(school, 7, 10), token=issued.token))
    assert result["result"]["member"] == str(member.pk)
    teacher = api(MembershipFactory(school=school, roles=["teacher"]).user)
    remember(teacher)
    refused = push(teacher, scan(yesterday(school, 7, 10), student=str(pupils[1].pk)))
    assert refused["error"]["code"] == "permission_denied"
