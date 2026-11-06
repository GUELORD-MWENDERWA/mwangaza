"""Suivi des présences (6.5) et parents (6.6) : absents calculés (corrections, justifications,
congés), journal et audit, droits, isolation entre écoles, Portail, parents prévenus une fois le
matin et direction alertée au seuil."""

import io
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.attendance import cards, follow, scans
from apps.attendance.models import AbsenceJustification, AttendanceRecord
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.notifications import scheduled
from apps.notifications.models import Notification, SchoolEvent
from apps.portal.tests.test_access import activate, portal
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()
D1, D2, D3 = (TODAY - timedelta(days=n) for n in (3, 2, 1))


def at(school, day, hour, minute=0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(school.timezone))


def exported(client) -> list[tuple]:
    """Lignes du rapport Excel du J1 au J3, sans les titres."""
    export = client.get("/api/attendance/export/", date_from=D1, date_to=D3)
    return list(openpyxl.load_workbook(io.BytesIO(export.content)).active.values)[1:]


def parent_of(school, student):
    with use_school(school):
        code = student.family.code
    parent = portal()
    assert activate(parent, code).status_code == 200
    return parent


def passed(school, actor, student, day, status="present"):
    with use_school(school):
        AttendanceRecord.objects.create(
            session=scans.entrance(day),
            student=student,
            seen_at=at(school, day, 7 if status == "present" else 8),
            method="manual",
            status=status,
            created_by=actor,
        )


@pytest.fixture
def pupils(school, head, alpha):
    """Trois élèves inscrits depuis la rentrée. J1 : Josué à l'heure ; J2 : Josué en retard,
    Amina à l'heure ; J3, congé : Josué passe quand même (rien ne compte)."""
    names = ("Josué", "Amina", "Neema")
    found = [enrolled(school, head, alpha["group"], first_name=name) for name in names]
    with use_school(school):
        Enrollment.objects.update(enrolled_on=date(2026, 9, 1))
        SchoolEvent.objects.create(
            title="Congé", kind=SchoolEvent.Kind.HOLIDAY, starts_on=D3, ends_on=D3, created_by=head
        )
    josue, amina, _neema = found
    passed(school, head, josue, D1)
    passed(school, head, josue, D2, "late")
    passed(school, head, amina, D2)
    passed(school, head, josue, D3)
    return found


def test_absences_follow_corrections_justifications_and_holidays(
    api, school, head, alpha, pupils, django_assert_max_num_queries
):
    josue, amina, neema = pupils
    client = api(head)
    # Neema avait oublié sa carte le J1 : corrigée au journal, avec l'audit.
    fixed = client.post(
        "/api/attendance/corrections/",
        {"date": D1, "student": neema.pk, "status": "present", "reason": "Carte oubliée"},
    )
    assert fixed.status_code == 201, fixed.json()
    assert (fixed.json()["previous_status"], fixed.json()["status"]) == ("absent", "present")
    # Le parent d'Amina apporte un mot pour le J1 : noté par l'école, accepté d'emblée.
    noted = client.post(
        "/api/attendance/justifications/",
        {"student": amina.pk, "starts_on": D1, "ends_on": D1, "reason": "Malade"},
    )
    assert noted.json()["status"] == "accepted"
    with use_school(school):
        assert set(AuditLog.objects.values_list("action", flat=True)) >= {
            "attendance.corrected",
            "attendance.justification_recorded",
        }
        counts = follow.totals(
            follow.windows(Enrollment.objects.all(), D1), follow.school_days(D1, D3)
        )
    assert (counts[josue.pk].days, counts[josue.pk].present, counts[josue.pk].late) == (2, 1, 1)
    assert (counts[amina.pk].absent, counts[amina.pk].justified) == (1, 1)
    assert (counts[neema.pk].present, counts[neema.pk].unjustified) == (1, 1)

    with django_assert_max_num_queries(20):
        day = client.get("/api/attendance/day/", date=D1).json()
    assert (day["present"], day["absent"], day["justified"], day["rate"]) == (2, 1, 1, 67)
    assert day["classes"][0]["absent"] == 1
    holiday = client.get("/api/attendance/day/", date=D3).json()
    assert (holiday["school_day"], holiday["holiday"], holiday["absent"]) == (False, True, 0)
    [row] = client.get("/api/attendance/absences/", date=D2).json()["results"]
    assert (row["name"], row["state"], row["unjustified"]) == (str(neema), "absent", 1)
    assert row["parent_on_portal"] is False

    by_name = {line[1]: line for line in exported(client)}
    assert by_name[str(neema)][3:] == (2, 1, 0, 1, 0, 50)
    assert by_name[str(amina)][3:] == (2, 1, 0, 1, 1, 50)


def test_following_and_correcting_need_their_rights_and_stay_in_the_school(
    api, school, head, cashier, alpha, pupils, other_school, other_head, beta
):
    josue, _amina, neema = pupils
    assert api(cashier).get("/api/attendance/day/").status_code == 403
    teacher = api(MembershipFactory(school=school, roles=["teacher"]).user)
    body = {"date": D2, "student": neema.pk, "status": "present", "reason": "Carte oubliée"}
    assert teacher.post("/api/attendance/corrections/", body).status_code == 403
    client = api(head)
    # Un jour sans pointage, ou un état déjà juste : rien à corriger.
    quiet = client.post("/api/attendance/corrections/", {**body, "date": TODAY - timedelta(5)})
    assert quiet.json()["code"] == "not_a_school_day"
    same = client.post(
        "/api/attendance/corrections/", {**body, "student": josue.pk, "status": "late"}
    )
    assert same.json()["code"] == "nothing_to_correct"
    with use_school(school):
        justification = AbsenceJustification.objects.create(
            student=neema,
            starts_on=D2,
            ends_on=D2,
            reason="Deuil",
            source="portal",
            document=SimpleUploadedFile("mot.pdf", b"%PDF-1.4 mot"),
            created_by=head,
        )
    # L'autre école ne voit ni ne touche rien de l'école Alpha.
    other = api(other_head, host="beta.localhost")
    enrolled(other_school, other_head, beta["group"], first_name="Safari")
    assert other.post("/api/attendance/corrections/", body).status_code == 400
    with use_school(school):
        member = cards.staff().get(user=head)
    staff_body = {"date": D2, "member": member.pk, "status": "present", "reason": "Oubli"}
    assert other.post("/api/attendance/corrections/", staff_body).status_code == 400
    assert other.get("/api/attendance/day/", date=D2).json()["school_day"] is False
    assert other.get("/api/attendance/corrections/").json()["count"] == 0
    assert other.get("/api/attendance/justifications/").json()["count"] == 0
    for path in ("document/", "decide/"):
        url = f"/api/attendance/justifications/{justification.pk}/{path}"
        call = other.get(url) if path == "document/" else other.post(url, {"accept": True})
        assert call.status_code == 404
    assert [line[2] for line in exported(other)] == [beta["group"].name]
    own = client.get(f"/api/attendance/justifications/{justification.pk}/document/")
    assert (own.status_code, own["Content-Type"]) == (200, "application/pdf")


def test_a_parent_justifies_from_the_portal_and_the_school_answers(
    api, school, head, pupils, other_school, other_head, beta
):
    _josue, _amina, neema = pupils
    parent = parent_of(school, neema)
    base = f"/api/portal/children/{neema.pk}/attendance/"
    seen = parent.get(base).json()
    assert [absence["state"] for absence in seen["absences"]] == ["absent", "absent"]
    certificate = SimpleUploadedFile("certificat.pdf", b"%PDF-1.4 certificat")
    sent = parent.post(
        f"{base}justify/",
        {"starts_on": D1, "ends_on": D2, "reason": "Paludisme", "document": certificate},
    )
    assert sent.status_code == 201, sent.json()
    assert sent.json()["status"] == "pending"
    again = parent.post(f"{base}justify/", {"starts_on": D2, "ends_on": D2, "reason": "Paludisme"})
    assert again.json()["code"] == "already_justified"
    old = TODAY - timedelta(days=40)
    late = parent.post(f"{base}justify/", {"starts_on": old, "ends_on": old, "reason": "Malade"})
    assert late.json()["code"] == "justification_too_early"
    # Un parent ne voit que ses enfants ; un enfant d'une autre école non plus.
    stranger = enrolled(other_school, other_head, beta["group"], first_name="Safari")
    assert parent.get(f"/api/portal/children/{stranger.pk}/attendance/").status_code == 404

    client = api(head)
    with use_school(school):
        told = Notification.objects.get(kind="justification_sent")
        assert told.user_id == head.pk
    [pending] = client.get("/api/attendance/justifications/", status="pending").json()["results"]
    decided = client.post(
        f"/api/attendance/justifications/{pending['id']}/decide/",
        {"accept": True, "note": "Bon rétablissement"},
    )
    assert decided.json()["status"] == "accepted"
    twice = client.post(
        f"/api/attendance/justifications/{pending['id']}/decide/", {"accept": False}
    )
    assert twice.json()["code"] == "already_decided"
    with use_school(school):
        assert AuditLog.objects.filter(action="attendance.justification_decided").count() == 1
        assert Notification.objects.filter(kind="justification_decided").count() == 1
    totals = parent.get(base).json()["totals"]
    assert (totals["absent"], totals["justified"], totals["pending"]) == (2, 2, 0)
    # École sans le module des présences : rien sur le Portail.
    school.modules = [module for module in school.modules if module != "attendance"]
    school.save()
    assert parent.get(base).status_code == 404


def test_parents_are_told_once_in_the_morning_and_the_direction_alerted_at_the_threshold(
    api, school, head, pupils
):
    neema = pupils[2]
    client = api(head)
    early = client.patch("/api/school/settings/", {"attendance": {"notify_at": "07:30"}})
    assert early.json()["code"] == "notify_before_late"
    client.patch("/api/school/settings/", {"attendance": {"alert_after": 2}})
    parent_of(school, neema)

    def told(kind):
        with use_school(school):
            return Notification.objects.filter(kind=kind).count()

    scheduled.tick(at(school, D1, 9, 30))
    assert (told("absence"), told("absence_alert")) == (1, 0)
    scheduled.tick(at(school, D2, 8, 30))
    assert told("absence") == 1
    scheduled.tick(at(school, D2, 9, 30))
    scheduled.tick(at(school, D2, 9, 45))
    # Neema, absente J1 et J2 : prévenu chaque matin, une fois ; seuil de 2 atteint le J2.
    assert (told("absence"), told("absence_alert")) == (2, 1)
    with use_school(school):
        alert = Notification.objects.get(kind="absence_alert")
        assert alert.user_id == head.pk and str(neema) in alert.body
    # Congé : personne n'est prévenu, même si quelqu'un a pointé.
    scheduled.tick(at(school, D3, 9, 30))
    assert told("absence") == 2
