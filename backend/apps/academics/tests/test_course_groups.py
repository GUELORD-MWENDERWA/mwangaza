"""Cours communs (8.1.2a) : un enseignant pour toutes les classes du groupe, notes et maxima
propres à chaque classe, droit `courses.configure`, isolation entre écoles, journal."""

import pytest

from apps.academics.models import Course, CourseGroup
from apps.academics.tests.test_courses import classes, courses_url, grid
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

GROUPS = "/api/course-groups/"


@pytest.fixture
def alpha(school, head):
    return classes(school, head)


@pytest.fixture
def teachers(school):
    return [MembershipFactory(school=school, roles=["teacher"]).user for _ in range(2)]


@pytest.fixture
def ready(api, alpha, head, teachers):
    """Français dans les sections A et B (maxima différents), enseignant propre à chacune."""
    client = api(head)
    client.put(courses_url(alpha["a"]), {"courses": grid(str(teachers[0].pk))})
    other = grid(str(teachers[1].pk))
    other[0]["period_max"] = 30
    client.put(courses_url(alpha["b"]), {"courses": other})
    return client


def create(client, alpha, teacher=None, name="français"):
    return client.post(
        GROUPS,
        {
            "name": name,
            "class_groups": [str(alpha["a"].pk), str(alpha["b"].pk)],
            "teacher_id": str(teacher.pk) if teacher else None,
        },
    )


def test_one_teacher_for_the_group_each_class_keeps_its_maximum(
    ready, alpha, api, school, teachers
):
    response = create(ready, alpha, teachers[0])
    assert response.status_code == 201
    group = response.json()
    assert group["name"] == "Français"
    assert group["teacher"]["id"] == str(teachers[0].pk)
    assert sorted(c["period_max"] for c in group["classes"]) == [30, 50]
    with use_school(school):
        french = Course.objects.filter(name="Français")
        assert {c.teacher_id for c in french} == {teachers[0].pk}
        assert french.filter(course_group__isnull=False).count() == 2
        assert AuditLog.objects.filter(action="course_group.changed").count() == 1

    # Changer l'enseignant du groupe le change partout ; enregistrer la grille ne le défait pas.
    ready.patch(f"{GROUPS}{group['id']}/", {"teacher_id": str(teachers[1].pk)})
    ready.put(
        courses_url(alpha["a"]),
        {"courses": [dict(c, teacher_id=str(teachers[0].pk)) for c in _grid_of(ready, alpha["a"])]},
    )
    with use_school(school):
        assert {c.teacher_id for c in Course.objects.filter(name="Français")} == {teachers[1].pk}
    # Ses notes : les deux cours, marqués du groupe (la fiche commune les réunit).
    mine = api(teachers[1]).get("/api/grading/").json()["classes"]
    assert [c["course_group"] for k in mine for c in k["courses"] if c["teaches"]] == [
        group["id"]
    ] * 2


def _grid_of(client, group):
    rows = client.get(courses_url(group)).json()
    return [
        {"id": r["id"], "name": r["name"], "period_max": r["period_max"], "has_exam": r["has_exam"]}
        for r in rows
    ]


def test_leaving_keeps_the_grades_and_a_lone_course_dissolves_the_group(
    ready, alpha, school, teachers
):
    group = create(ready, alpha, teachers[0]).json()
    out = ready.post(f"{GROUPS}{group['id']}/remove-class/", {"class_group": str(alpha["b"].pk)})
    assert out.status_code == 204
    with use_school(school):
        assert not CourseGroup.objects.exists()
        # La classe qui sort garde son cours, son maximum et son enseignant.
        kept = Course.objects.get(name="Français", class_group=alpha["b"])
        assert kept.course_group_id is None and kept.teacher_id == teachers[0].pk
        assert kept.period_max == 30


def test_rules_of_a_group(ready, alpha, api, school, teachers):
    assert create(ready, alpha, name="Chimie").status_code == 201
    assert create(ready, alpha, name="Chimie").status_code == 400  # déjà en groupe
    assert create(ready, alpha, name="Histoire").status_code == 400  # cours absent
    alone = ready.post(GROUPS, {"name": "Français", "class_groups": [str(alpha["a"].pk)]})
    assert alone.status_code == 400
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert api(secretary).get(GROUPS).status_code == 403
    assert api(secretary).post(GROUPS, {}).status_code == 403


def test_another_school_neither_reads_nor_changes_a_group(
    ready, alpha, api, other_school, other_head, teachers
):
    group = create(ready, alpha, teachers[0]).json()
    from_beta = api(other_head, host="beta.localhost")
    assert from_beta.get(GROUPS).json() == []
    assert from_beta.patch(f"{GROUPS}{group['id']}/", {"teacher_id": None}).status_code == 404
    assert from_beta.delete(f"{GROUPS}{group['id']}/").status_code == 404
    mixed = from_beta.post(
        GROUPS, {"name": "Français", "class_groups": [str(alpha["a"].pk), str(alpha["b"].pk)]}
    )
    assert mixed.status_code == 404
    with use_school(other_school):
        assert not CourseGroup.objects.exists()
