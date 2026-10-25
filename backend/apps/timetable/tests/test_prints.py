"""Impressions de l'horaire (EDT.4c) : droit, isolation entre écoles, contenu juste (heures,
charge de l'enseignant, récréation, séance hors grille), PDF gardé."""

import pytest

from apps.academics.tests.test_courses import classes
from apps.core.models import KeptDocument
from apps.core.tenancy import use_school
from apps.timetable import prints
from apps.timetable.models import Room, TimeSlot, Timetable, TimetableEntry
from apps.timetable.tests.test_constraints import new
from apps.timetable.tests.test_drafts import DRAFTS
from apps.timetable.tests.test_schedule import publish
from apps.timetable.tests.test_timetable import new_grid
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PRINT = "/api/timetable/print/"


def setup_horaire(school, head, api):
    data = classes(school, head)
    client = api(head)
    new_grid(client)
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    maths = new(data["a"], "Mathématique", 4, teacher=teacher)
    english = new(data["a"], "Anglais", 2, teacher=teacher)
    new(data["b"], "Physique", 3)
    published = publish(client, [(maths, 1, 1, 2), (maths, 3, 1, 2), (english, 1, 4, 1)])
    return data, client, teacher, published


def test_rights_isolation_and_html(api, school, head, other_school, other_head):
    data, client, teacher, published = setup_horaire(school, head, api)
    classes(other_school, other_head)
    beta = api(other_head, host="beta.localhost")
    new_grid(beta)
    theirs = beta.post(DRAFTS, {"name": "Brouillon B"}).json()
    mine = f"{PRINT}?kind=class&output=html"

    # Droit `timetable.manage` : l'enseignant n'imprime pas l'horaire de l'école.
    assert api(teacher).get(mine).status_code == 403
    page = client.get(f"{mine}&subject={data['a'].pk}")
    assert page.status_code == 200
    assert "Mathématique" in page.content.decode() and "Physique" not in page.content.decode()
    # Sans sujet : les classes qui ont des séances (la B n'en a pas).
    assert client.get(mine).content.decode().count('<h1 class="lh-title">') == 1

    # École B : ni la version ni la classe de A ; son propre tout est vide, jamais celui de A.
    assert beta.get(f"{mine}&timetable={published['id']}").status_code == 404
    assert beta.get(f"{mine}&timetable={theirs['id']}&subject={data['a'].pk}").status_code == 404
    assert beta.get(f"{PRINT}?kind=general&output=html&timetable={theirs['id']}").status_code == 409
    assert client.get(f"{mine}&timetable={theirs['id']}").status_code == 404


def test_content_of_each_document(school, head, api):
    data, _client, teacher, published = setup_horaire(school, head, api)
    with use_school(school):
        version = Timetable.objects.get(pk=published["id"])
        room = Room.objects.create(name="Atelier électricité")
        TimetableEntry.objects.filter(timetable=version, weekday=1, first=1).update(room=room)
        ((_pk, page),) = prints.document(prints.CLASS, version, data["a"].pk)
        # Lundi : 1re et 2e heure en une case de 2 lignes ; la récréation suit la 3e.
        monday = [row["cells"][0] for row in page["rows"]]
        assert monday[0]["rowspan"] == 2 and monday[0]["lessons"][0]["title"] == "Mathématique"
        assert monday[0]["lessons"][0]["detail"].endswith("Atelier électricité")
        assert monday[1] == "skip"
        assert [row["is_break"] for row in page["rows"]][:5] == [False, False, False, True, False]
        assert page["rows"][0]["times"] == "07:30\N{EN DASH}08:20"
        assert page["hours"] == 5

        # Enseignant : 4 h de maths + 1 h d'anglais placées sur 6 h dues ; charge par cours.
        ((_pk, page),) = prints.document(prints.TEACHER, version, teacher.pk)
        assert (page["hours"], page["due"]) == (5, 6)
        assert [(r["course"], r["due"], r["placed"]) for r in page["load"]] == [
            ("Anglais", 2, 1),
            ("Mathématique", 4, 4),
        ]
        # Salle : seulement ce qui s'y passe ; une salle vide n'a pas de page dans « toutes ».
        ((_pk, page),) = prints.document(prints.ROOM, version, None)
        assert page["hours"] == 2
        # Général : une classe sans séance n'y est pas ; deux pages A4, une seule en A3.
        ((_pk, page),) = prints.document(prints.GENERAL, version, None)
        assert [line["name"] for line in page["sheets"][0]["lines"]] == [data["a"].name]
        assert len(page["sheets"]) == 2 and page["legend"][0][0] == "Angl"
        ((_pk, page),) = prints.document(prints.GENERAL, version, None, one_sheet=True)
        assert len(page["sheets"]) == 1

        # Lundi retiré de la grille après la publication : ses séances sont listées à part.
        TimeSlot.objects.filter(weekday=1).delete()
        ((_pk, page),) = prints.document(prints.CLASS, version, data["a"].pk)
        assert [x["title"] for x in page["outside"]] == ["Mathématique", "Anglais"]


def test_pdf_is_kept_and_served_again(school, head, api):
    _data, client, _teacher, _published = setup_horaire(school, head, api)
    url = f"{PRINT}?kind=general&paper=a3"
    first = client.get(url)
    assert first.status_code == 200 and first.content.startswith(b"%PDF")
    with use_school(school):
        assert KeptDocument.objects.filter(kind="timetable_general").count() == 1
    assert client.get(url).content.startswith(b"%PDF")
    with use_school(school):
        assert KeptDocument.objects.filter(kind="timetable_general").count() == 1
