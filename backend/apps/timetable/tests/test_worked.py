"""Heures prestées (EDT.6) : calcul du mois (versions de l'horaire, congé, absence, remplacement,
annulation annulée, heure en plus), refus, droits, isolation, journal, fiche et export."""

from datetime import date

import pytest

from apps.academics.tests.test_courses import classes
from apps.accounts.models import Role
from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.notifications.models import SchoolEvent
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_schedule import publish
from apps.timetable.tests.test_timetable import log, new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

WORKED = "/api/timetable/worked/"
EXCEPTIONS = f"{WORKED}exceptions/"


def day_entries(client, day: str, teacher) -> dict[str, str]:
    """Cours → séance du jour (pour noter une exception)."""
    rows = client.get(f"{WORKED}day/?date={day}&teacher={teacher.pk}").json()
    return {row["course"]: row["entry"] for row in rows}


def test_month_of_hours_worked(api, school, head, other_school, other_head):
    data = classes(school, head)
    classes(other_school, other_head)
    client, beta = api(head), api(other_head, host="beta.localhost")
    new_grid(client)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    stand_in = MembershipFactory(school=school, roles=["teacher"]).user
    maths = new(data["a"], "Mathématique", 4, teacher=teacher)  # séances 2 + 2
    french = new(data["b"], "Français", 1, teacher=teacher)
    # Octobre 2026 : lundi 2 h de maths, mardi le français ; dès le mercredi 14, le français passe
    # au mercredi. Le lundi 12 est un congé du calendrier.
    publish(client, [(maths, 1, 1, 2), (french, 2, 1, 1)], "2026-10-01")
    publish(client, [(maths, 1, 1, 2), (french, 3, 1, 1)], "2026-10-14")
    with use_school(school):
        SchoolEvent.objects.create(
            title="Fête", kind="holiday", starts_on=date(2026, 10, 12), ends_on=date(2026, 10, 12)
        )

    # Droits : un enseignant ne voit rien ; un rôle avec le seul droit des heures prestées, oui.
    assert api(teacher).get(f"{WORKED}?month=2026-10").status_code == 403
    with use_school(school):
        role = Role.objects.create(name="Surveillant", permissions=["timetable.record_exceptions"])
    clerk = api(MembershipFactory(school=school, roles=[role]).user)

    # Lundi 5 : absent (2 h) ; mardi 6 : remplacé (1 h) ; mercredi 21 : annulé, puis annulation.
    absent = clerk.post(
        EXCEPTIONS,
        {
            "date": "2026-10-05",
            "kind": "teacher_absent",
            "teacher": str(teacher.pk),
            "entries": [day_entries(clerk, "2026-10-05", teacher)["Mathématique"]],
            "reason": "Malade",
        },
    )
    assert absent.status_code == 201, absent.json()
    replaced = {
        "date": "2026-10-06",
        "kind": "replaced",
        "teacher": str(teacher.pk),
        "entries": [day_entries(clerk, "2026-10-06", teacher)["Français"]],
        "reason": "Formation",
    }
    assert clerk.post(EXCEPTIONS, replaced).json()["code"] == "replacement_required"
    assert clerk.post(EXCEPTIONS, replaced | {"replacement": str(stand_in.pk)}).status_code == 201
    # La même heure deux fois : refusé.
    again = clerk.post(EXCEPTIONS, replaced | {"replacement": str(stand_in.pk)})
    assert again.json()["code"] == "already_recorded"
    cancelled = clerk.post(
        EXCEPTIONS,
        {
            "date": "2026-10-21",
            "kind": "cancelled",
            "teacher": str(teacher.pk),
            "entries": [day_entries(clerk, "2026-10-21", teacher)["Français"]],
            "reason": "Sortie",
        },
    ).json()[0]
    undo = clerk.post(f"{EXCEPTIONS}{cancelled['id']}/cancel/", {"reason": "Erreur"})
    assert undo.status_code == 200
    assert clerk.post(f"{EXCEPTIONS}{cancelled['id']}/cancel/", {"reason": "x"}).status_code == 409
    # Heure en plus : 2 h de maths par le remplaçant le samedi 24.
    extra = {
        "date": "2026-10-24",
        "kind": "extra",
        "teacher": str(stand_in.pk),
        "course": str(maths.pk),
        "hours": 2,
        "reason": "Rattrapage",
    }
    assert clerk.post(EXCEPTIONS, extra).status_code == 201

    # Refus : congé, jour à venir, séance d'une version plus en vigueur ce jour-là.
    v1_maths = day_entries(clerk, "2026-10-05", teacher)["Mathématique"]
    body = {"kind": "teacher_absent", "teacher": str(teacher.pk), "reason": "x"}
    assert (
        clerk.post(EXCEPTIONS, body | {"date": "2026-10-12", "entries": [v1_maths]}).json()["code"]
        == "not_a_school_day"
    )
    assert (
        clerk.post(EXCEPTIONS, body | {"date": "2099-01-05", "entries": [v1_maths]}).json()["code"]
        == "future_date"
    )
    assert (
        clerk.post(EXCEPTIONS, body | {"date": "2026-10-19", "entries": [v1_maths]}).json()["code"]
        == "not_in_timetable"
    )

    # Prévues : maths 3 lundis (5, 19, 26 ; le 12 est un congé) de 2 h = 6 ; français : mardis 6
    # et 13, puis mercredis 14, 21 et 28 = 5. Soit 11 ; moins 2 (absent) et 1 (remplacé) = 8.
    report = clerk.get(f"{WORKED}?month=2026-10").json()
    lines = {row["teacher"]: row for row in report["teachers"]}
    mine, theirs = lines[str(teacher.pk)], lines[str(stand_in.pk)]
    assert (mine["planned"], mine["absent"], mine["cancelled"], mine["given"]) == (11, 3, 0, 8)
    assert (theirs["planned"], theirs["replacements"], theirs["extra"], theirs["given"]) == (
        0,
        1,
        2,
        3,
    )
    assert report["holidays"] == ["2026-10-12"]
    assert report["totals"] == {"planned": 11, "missed": 3, "added": 3}
    assert clerk.get(f"{EXCEPTIONS}?month=2026-10").json()["count"] == 3  # l'annulée sort

    # Journal : chaque exception notée, l'annulation avec son motif.
    assert len(log(school, Action.LESSON_EXCEPTION_RECORDED)) == 4
    [undone] = log(school, Action.LESSON_EXCEPTION_CANCELLED)
    assert undone.after == {"cancelled": True, "reason": "Erreur"}

    # Fiche (aperçu) et export du mois.
    sheet = clerk.get(f"{WORKED}sheet/?month=2026-10&teacher={teacher.pk}&output=html")
    assert sheet.status_code == 200 and "Malade" in sheet.content.decode()
    export = clerk.get(f"{WORKED}export/?month=2026-10")
    assert export.status_code == 200 and export["Content-Type"].startswith("application/vnd")

    # L'école B ne lit ni n'annule rien de A, ni ne note pour un enseignant de A.
    assert beta.get(f"{WORKED}?month=2026-10").json()["teachers"] == []
    assert beta.get(f"{EXCEPTIONS}?month=2026-10").json()["count"] == 0
    assert beta.post(f"{EXCEPTIONS}{cancelled['id']}/cancel/", {"reason": "x"}).status_code == 404
    assert beta.get(f"{WORKED}day/?date=2026-10-05&teacher={teacher.pk}").status_code == 404
    assert beta.get(f"{WORKED}sheet/?month=2026-10&teacher={teacher.pk}").status_code == 404
    assert beta.post(EXCEPTIONS, extra).status_code == 400
