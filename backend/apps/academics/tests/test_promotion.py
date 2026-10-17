"""Passage de classe et confirmation de place (8.4.5) : place proposée d'après la décision
proclamée, réponse du parent au Portail, inscription en lot par l'école (frais dus, matricule
gardé, pas de doublon) ; journal, droits, isolation entre écoles."""

from datetime import date

import pytest
from django.utils import timezone

from apps.academics.models import Deliberation, DeliberationSnapshot, PlaceConfirmation
from apps.audit.models import AuditLog
from apps.core.tenancy import use_all_schools, use_school
from apps.finance.models import StudentCharge
from apps.finance.tests.test_charges import once, rule
from apps.notifications.models import Notification
from apps.portal.tests.test_access import activate, new_family, portal, reloaded
from apps.schools import organisation
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SUMMARY = "/api/promotion/"
PLACES = "/api/portal/places/"


def class_url(group, tail="") -> str:
    return f"/api/class-groups/{group.pk}/promotion/{tail}"


def setup(school, actor) -> dict:
    """2026-2027 (en cours) : 1re ELEC A, cinq élèves aux décisions proclamées, et 2e ELEC A
    (dernière année, Examen d'État) ; 2027-2028 copiée de ses classes, avec un minerval."""
    data = {}
    with use_school(school):
        year = organisation.create_year(
            actor=actor, starts_on=date(2026, 9, 1), ends_on=date(2027, 7, 2)
        )
        first = organisation.create_level(actor=actor, name="1re", cycle="secondary_technical")
        last = organisation.create_level(actor=actor, name="2e", cycle="secondary_technical")
        last.has_state_exam = True
        last.save(update_fields=["has_state_exam"])
        track = organisation.create_track(actor=actor, name="Électricité", code="ELEC")
        data["a"], data["final"] = (
            organisation.create_class_group(
                actor=actor, academic_year=year, level=level, track=track, section="A"
            )
            for level in (first, last)
        )
    decisions = {
        "amani": "pass",
        "josue": "repeat",
        "kavira": "resit",
        "sikuli": "exclude",
        "masika": "orient",
    }
    for key in decisions:
        student = enrolled(school, actor, data["a"], last_name=key.title(), first_name="X")
        with use_school(school):
            data[key] = student.enrollments.get()
    paluku = enrolled(school, actor, data["final"], last_name="Paluku", first_name="X")
    with use_school(school):
        data["paluku"] = paluku.enrollments.get()
        proclaim(data["a"], actor, {data[key]: value for key, value in decisions.items()})
        proclaim(data["final"], actor, {data["paluku"]: "pass"})
        data["next"] = organisation.create_year(
            actor=actor,
            starts_on=date(2027, 9, 1),
            ends_on=date(2028, 7, 2),
            copy_classes_from=year,
        )
        copied = data["next"].class_groups.select_related("level", "track")
        groups = {g.level.name: g for g in copied}
        data["next_1re"], data["next_2e"] = groups["1re"], groups["2e"]
        rule(
            actor, {"year": data["next"]}, "Minerval", "USD", once("Minerval", 15000, "2027-10-01")
        )
    return data


def proclaim(group, actor, decisions: dict) -> None:
    deliberation = Deliberation.objects.create(
        class_group=group, held_on=date(2027, 6, 25), status="proclaimed", version=1
    )
    DeliberationSnapshot.objects.create(
        deliberation=deliberation,
        version=1,
        held_on=deliberation.held_on,
        proclaimed_at=timezone.now(),
        proclaimed_by=actor,
        rows=[
            {"enrollment": str(e.pk), "percent": "61.5", "decision": value}
            for e, value in decisions.items()
        ],
    )


@pytest.fixture
def secretary(school):
    return MembershipFactory(school=school, roles=["secretary"]).user


def rows(client, data) -> dict:
    body = client.get(class_url(data["a"])).json()
    return {r["full_name"].split()[0].lower(): r for r in body["students"]}


def places_log(school, action) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action).order_by("created_at"))


def test_places_follow_the_decision_and_the_school_enrolls_once_with_fees(
    api, school, head, secretary, django_assert_max_num_queries
):
    data = setup(school, head)
    client = api(secretary)
    summary = client.get(SUMMARY).json()
    assert (summary["year"]["name"], summary["following"]["name"]) == ("2026-2027", "2027-2028")
    line = next(c for c in summary["classes"] if c["id"] == str(data["a"].pk))
    assert (line["proclaimed_on"], line["counts"]["students"]) == ("2027-06-25", 5)

    # Proposition d'après la décision figée : admis → niveau suivant, doublant → même niveau,
    # réorienté → à choisir ; repêchage, exclusion, dernière année : pas de place.
    with django_assert_max_num_queries(20):
        students = rows(client, data)
    proposed = {k: (r["proposal"], r["proposed_class"]) for k, r in students.items()}
    assert proposed == {
        "amani": ("next_level", str(data["next_2e"].pk)),
        "josue": ("same_level", str(data["next_1re"].pk)),
        "kavira": ("waiting", None),
        "sikuli": ("no_place", None),
        "masika": ("choose", None),
    }
    final = client.get(class_url(data["final"])).json()["students"][0]
    assert final["proposal"] == "finished"

    # Refus : pas de place pour un élève en repêchage, ni dans une classe de l'année finie.
    def offer(**choices):
        places = [
            {"enrollment": str(data[k].pk), "class_group": str(g.pk)} for k, g in choices.items()
        ]
        return client.post(class_url(data["a"], "offer/"), {"places": places})

    assert offer(kavira=data["next_1re"]).json()["code"] == "no_place_for_decision"
    assert offer(amani=data["a"]).json()["code"] == "not_next_year"
    assert not places_log(school, "students.place_offered")

    answer = offer(amani=data["next_2e"], josue=data["next_1re"], masika=data["next_1re"])
    assert answer.status_code == 200
    assert answer.json()["counts"]["offered"] == 3
    assert len(places_log(school, "students.place_offered")) == 3
    # La même proposition une seconde fois ne change rien ; un retrait est noté au journal.
    offer(amani=data["next_2e"])
    assert len(places_log(school, "students.place_offered")) == 3
    client.post(class_url(data["a"], "withdraw/"), {"enrollments": [str(data["masika"].pk)]})
    assert places_log(school, "students.place_withdrawn")[0].after["status"] == "withdrawn"

    # Inscription : seulement les places proposées (pas celle retirée), frais de l'année
    # suivante, matricule gardé ; une seconde demande ne crée pas de doublon.
    chosen = [str(data[k].pk) for k in ("amani", "josue", "masika")]
    for _ in range(2):
        answer = client.post(class_url(data["a"], "enroll/"), {"enrollments": chosen})
        assert answer.status_code == 200
    with use_school(school):
        created = Enrollment.objects.filter(academic_year=data["next"]).select_related("student")
        assert {(e.student.last_name, e.class_group_id) for e in created} == {
            ("Amani", data["next_2e"].pk),
            ("Josue", data["next_1re"].pk),
        }
        assert {e.student.matricule for e in created} == {
            data["amani"].student.matricule,
            data["josue"].student.matricule,
        }
        assert set(
            StudentCharge.objects.filter(enrollment__in=created).values_list(
                "amount_minor", "currency"
            )
        ) == {(15000, "USD")}
        assert StudentCharge.objects.filter(enrollment__in=created).count() == 2
        assert set(PlaceConfirmation.objects.values_list("status", flat=True)) == {
            "enrolled",
            "withdrawn",
        }
    # Six inscriptions au départ (`setup`), deux de plus.
    assert len(places_log(school, "students.enrolled")) == 8
    students = rows(client, data)
    assert students["amani"]["enrolled_class"] == data["next_2e"].name


def test_the_parent_answers_for_their_own_child_until_the_school_enrolls(
    api, school, other_school, head, other_head, secretary
):
    data = setup(school, head)
    with use_school(school):
        amani_family = data["amani"].student.family
    parent = portal()
    activate(parent, amani_family.code)
    stranger = portal()
    activate(
        stranger,
        new_family(other_school, other_head, phone="+243990000001").code,
        phone="0990000001",
    )
    client = api(secretary)
    places = [
        {"enrollment": str(data[k].pk), "class_group": str(data[g].pk)}
        for k, g in (("amani", "next_2e"), ("josue", "next_1re"))
    ]
    assert client.post(class_url(data["a"], "offer/"), {"places": places}).status_code == 200
    # Seule la famille qui a un compte est prévenue.
    with use_all_schools():
        notified = list(
            Notification.all_schools.filter(kind="place_offered").values_list("user", flat=True)
        )
    assert notified == [reloaded(amani_family).primary_user_id]

    # Le parent ne voit que la place de son enfant ; un autre compte ne la voit pas.
    [place] = parent.get(PLACES).json()
    assert (place["full_name"], place["class_name"], place["year_name"]) == (
        "Amani X",
        data["next_2e"].name,
        "2027-2028",
    )
    assert stranger.get(PLACES).json() == []
    url = f"{PLACES}{place['id']}/"
    assert stranger.put(url, {"answer": "no"}, content_type="application/json").status_code == 404

    # Réponse, puis changement d'avis : au journal ; l'école la voit.
    for value in ("no", "yes"):
        answered = parent.put(url, {"answer": value}, content_type="application/json")
        assert answered.json()["answer"] == value
    logged = places_log(school, "students.place_answered")
    assert [e.after["answer"] for e in logged] == ["no", "yes"]
    assert rows(client, data)["amani"]["place"]["answer"] == "yes"

    # Inscrit par l'école : la carte disparaît, la réponse ne se change plus.
    enroll = {"enrollments": [str(data["amani"].pk)]}
    assert client.post(class_url(data["a"], "enroll/"), enroll).status_code == 200
    assert parent.get(PLACES).json() == []
    assert parent.put(url, {"answer": "no"}, content_type="application/json").status_code == 404


def test_only_staff_who_enroll_and_only_their_school(api, school, other_school, head, other_head):
    data = setup(school, head)
    teacher = api(MembershipFactory(school=school, roles=["teacher"]).user)
    assert teacher.get(SUMMARY).status_code == 403
    assert teacher.get(class_url(data["a"])).status_code == 403
    enroll = {"enrollments": [str(data["amani"].pk)]}
    assert teacher.post(class_url(data["a"], "enroll/"), enroll).status_code == 403

    beta = api(other_head, host="beta.localhost")
    assert beta.get(SUMMARY).json()["classes"] == []
    assert beta.get(class_url(data["a"])).status_code == 404
    place = {
        "places": [{"enrollment": str(data["amani"].pk), "class_group": str(data["next_2e"].pk)}]
    }
    assert beta.post(class_url(data["a"], "offer/"), place).status_code == 404
    assert beta.post(class_url(data["a"], "enroll/"), enroll).status_code == 404
    with use_school(school):
        assert not PlaceConfirmation.objects.exists()
        assert not Enrollment.objects.filter(academic_year=data["next"]).exists()
