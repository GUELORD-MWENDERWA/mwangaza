"""Cours de chaque classe (8.1) : grille d'un seul bloc, copie, charges des enseignants ; droit
`courses.configure`, module `academics`, isolation entre écoles, journal."""

from datetime import date

import pytest

from apps.academics.models import Course
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.schools.models import School
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

LOADS = "/api/teaching-loads/"


def courses_url(group) -> str:
    return f"/api/class-groups/{group.pk}/courses/"


def classes(school, actor) -> dict:
    """Une année (modèle secondaire : 4 périodes, 2 examens), deux sections d'une classe."""
    with use_school(school):
        year = organisation.create_year(
            actor=actor, starts_on=date(2026, 9, 1), ends_on=date(2027, 7, 2)
        )
        level = organisation.create_level(actor=actor, name="1re", cycle="secondary_technical")
        track = organisation.create_track(actor=actor, name="Électricité", code="ELEC")
        a, b = (
            organisation.create_class_group(
                actor=actor, academic_year=year, level=level, track=track, section=section
            )
            for section in "AB"
        )
    return {"year": year, "a": a, "b": b}


@pytest.fixture
def alpha(school, head):
    return classes(school, head)


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


def grid(teacher=None) -> list[dict]:
    return [
        {"name": "Français", "period_max": 50, "weekly_hours": 5, "teacher_id": teacher},
        {"name": "Chimie", "period_max": 20, "weekly_hours": 1},
        {"name": "Atelier électrique", "period_max": 100, "has_exam": False, "weekly_hours": 8},
    ]


def changes(school) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action="courses.changed").order_by("created_at"))


# Droits et isolation


def test_courses_need_the_right_and_the_module(api, school, alpha, head):
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert api(secretary).get(courses_url(alpha["a"])).status_code == 403
    assert api(secretary).get(LOADS).status_code == 403
    director = MembershipFactory(school=school, roles=["study_director"]).user
    assert api(director).put(courses_url(alpha["a"]), {"courses": grid()}).status_code == 200
    # Sans le droit, la classe se lit quand même pour qui a `courses.configure` (choix de classe).
    assert api(director).get("/api/class-groups/").status_code == 200

    School.objects.filter(pk=school.pk).update(modules=["students"])
    response = api(head).get(courses_url(alpha["a"]))
    assert response.status_code == 403
    assert response.json()["code"] == "module_missing"


def test_another_school_can_neither_read_nor_change_the_courses(
    api, school, other_school, alpha, head, other_head, teacher
):
    api(head).put(courses_url(alpha["a"]), {"courses": grid(str(teacher.pk))})
    beta = classes(other_school, other_head)
    from_beta = api(other_head, host="beta.localhost")

    assert from_beta.get(courses_url(alpha["a"])).status_code == 404
    assert from_beta.put(courses_url(alpha["a"]), {"courses": []}).status_code == 404
    copy = from_beta.post(f"{courses_url(beta['a'])}copy/", {"class_groups": [str(alpha["b"].pk)]})
    assert copy.status_code == 400
    loads = from_beta.get(LOADS).json()
    assert loads["unassigned_count"] == 0
    assert all(load["hours"] == 0 for load in loads["loads"])
    assert str(teacher.pk) not in {load["teacher"]["id"] for load in loads["loads"]}
    # Un enseignant d'une autre école n'entre pas dans la grille.
    refused = from_beta.put(courses_url(beta["a"]), {"courses": grid(str(teacher.pk))})
    assert refused.status_code == 400
    assert "courses.0.teacher_id" in str(refused.json())
    with use_school(school):
        assert Course.objects.filter(class_group=alpha["a"]).count() == 3


# La grille d'une classe


def test_the_grid_is_saved_in_one_block_and_noted_when_it_changes(
    api, school, alpha, head, teacher
):
    client = api(head)
    saved = client.put(courses_url(alpha["a"]), {"courses": grid(str(teacher.pk))}).json()
    assert [c["name"] for c in saved] == ["Français", "Chimie", "Atelier électrique"]
    assert saved[0]["teacher"]["id"] == str(teacher.pk)
    assert saved[2]["has_exam"] is False
    (created,) = changes(school)
    assert created.before is None and len(created.after["courses"]) == 3

    # Français gardé (même id, nouveau maximum), Chimie retirée, Physique ajoutée, ordre changé.
    french, _chemistry, workshop = saved
    update = [
        {"id": workshop["id"], "name": "Atelier électrique", "period_max": 100, "has_exam": False},
        {"id": french["id"], "name": "Français", "period_max": 60, "weekly_hours": 5},
        {"name": "Physique", "period_max": 20},
    ]
    after = client.put(courses_url(alpha["a"]), {"courses": update}).json()
    assert [c["name"] for c in after] == ["Atelier électrique", "Français", "Physique"]
    assert after[1]["id"] == french["id"] and after[1]["teacher"] is None
    entry = changes(school)[-1]
    assert {row["name"] for row in entry.before["courses"]} == {
        "Atelier électrique",  # heures retirées
        "Français",
        "Chimie",
    }
    assert {row["name"] for row in entry.after["courses"]} == {
        "Atelier électrique",
        "Français",
        "Physique",
    }

    # Même grille renvoyée : rien au journal.
    same = [{**row, "id": c["id"]} for row, c in zip(update, after, strict=True)]
    assert client.put(courses_url(alpha["a"]), {"courses": same}).status_code == 200
    assert len(changes(school)) == 2


def test_a_grid_with_errors_changes_nothing(api, school, alpha, head):
    client = api(head)
    client.put(courses_url(alpha["a"]), {"courses": grid()})
    with use_school(school):
        other = Course.objects.create(class_group=alpha["b"], name="Histoire", period_max=20)
    duplicate = [*grid(), {"name": "  français ", "period_max": 10}]
    foreign = [{"id": str(other.pk), "name": "Histoire", "period_max": 20}]
    for courses in (duplicate, foreign):
        assert client.put(courses_url(alpha["a"]), {"courses": courses}).status_code == 400
    with use_school(school):
        assert Course.objects.filter(class_group=alpha["a"]).count() == 3
        assert Course.objects.filter(class_group=alpha["b"]).count() == 1
    assert len(changes(school)) == 1


def test_copy_gives_the_grid_and_keeps_teachers_of_the_same_course(
    api, school, alpha, head, teacher
):
    client = api(head)
    client.put(courses_url(alpha["a"]), {"courses": grid()})
    client.put(
        courses_url(alpha["b"]),
        {
            "courses": [
                {"name": "FRANÇAIS", "period_max": 40, "teacher_id": str(teacher.pk)},
                {"name": "Dessin", "period_max": 40},
            ]
        },
    )
    response = client.post(
        f"{courses_url(alpha['a'])}copy/",
        {"class_groups": [str(alpha["b"].pk), str(alpha["a"].pk)]},
    )
    assert response.json() == {"copied": 1}
    copied = client.get(courses_url(alpha["b"])).json()
    assert [(c["name"], c["period_max"]) for c in copied] == [
        ("Français", 50),
        ("Chimie", 20),
        ("Atelier électrique", 100),
    ]
    assert copied[0]["teacher"]["id"] == str(teacher.pk)
    assert changes(school)[-1].entity_label == alpha["b"].name


# Charges des enseignants


def test_teaching_loads_add_the_hours_of_the_year(api, school, alpha, head, teacher):
    client = api(head)
    client.put(courses_url(alpha["a"]), {"courses": grid(str(teacher.pk))})
    client.put(
        courses_url(alpha["b"]),
        {
            "courses": [
                {
                    "name": "Français",
                    "period_max": 50,
                    "weekly_hours": 4,
                    "teacher_id": str(teacher.pk),
                }
            ]
        },
    )
    loads = client.get(LOADS).json()
    first = loads["loads"][0]
    assert (first["teacher"]["id"], first["hours"], len(first["courses"])) == (
        str(teacher.pk),
        9,
        2,
    )
    assert {c["name"] for c in loads["unassigned"]} == {"Chimie", "Atelier électrique"}

    # Parti de l'école : ses cours sont à réattribuer.
    with use_school(school):
        teacher.memberships.filter(school=school).update(is_active=False)
    loads = client.get(LOADS).json()
    assert str(teacher.pk) not in {load["teacher"]["id"] for load in loads["loads"]}
    assert (loads["unassigned_count"], loads["unassigned_hours"]) == (4, 18)


def test_a_new_year_with_the_classes_takes_their_courses_without_teachers(
    school, alpha, head, teacher, api
):
    api(head).put(courses_url(alpha["a"]), {"courses": grid(str(teacher.pk))})
    with use_school(school):
        year = organisation.create_year(
            actor=head,
            starts_on=date(2027, 9, 1),
            ends_on=date(2028, 7, 2),
            copy_classes_from=alpha["year"],
        )
        copied = Course.objects.filter(class_group__academic_year=year)
        assert sorted(copied.values_list("name", "period_max", "teacher")) == [
            ("Atelier électrique", 100, None),
            ("Chimie", 20, None),
            ("Français", 50, None),
        ]
        created = AuditLog.objects.get(action="organisation.year_created", entity_id=year.pk)
    assert created.after["course_count"] == 3
