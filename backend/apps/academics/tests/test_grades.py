"""Notes (8.2.1) : feuille d'un cours dans une période ou des examens, d'un seul envoi ; droits
`grades.enter` (ses cours, sa classe de titulaire) et `grades.enter_any`, module `academics`,
isolation entre écoles, note de la période ramenée au maximum, journal."""

from decimal import Decimal

import pytest

from apps.academics.grades import period_score
from apps.academics.models import Course, Evaluation, Grade
from apps.academics.tests.test_courses import classes, courses_url
from apps.audit.models import AuditLog
from apps.core.errors import BusinessError
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.schools.models import ClassGroup, School, Term
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

GRADING = "/api/grading/"


def sheet_url(course, term) -> str:
    return f"/api/courses/{course.pk}/terms/{term.pk}/grades/"


def setup(school, actor, teacher=None) -> dict:
    """Classes A et B : en A, « Physique » sur 20 (donnée par `teacher`) et un atelier sans
    examen, deux élèves ; en B, « Physique » et un élève."""
    data = classes(school, actor)
    with use_school(school):
        new = Course.objects.create
        data["physics"] = new(
            class_group=data["a"], name="Physique", period_max=20, teacher=teacher
        )
        data["workshop"] = new(
            class_group=data["a"], name="Atelier", period_max=100, has_exam=False
        )
        data["b_physics"] = new(class_group=data["b"], name="Physique", period_max=20)
        terms = Term.objects.filter(academic_year=data["year"]).order_by("order")
        data["p1"] = terms.filter(kind="period").first()
        data["exam"] = terms.filter(kind="exam").first()
        data["semester"] = terms.filter(kind="semester").first()
    for key, group, name in (
        ("amani", "a", "Bahati"),
        ("josue", "a", "Kambale"),
        ("b", "b", "Sikuli"),
    ):
        student = enrolled(school, actor, data[group], last_name=name, first_name="X")
        with use_school(school):
            data[key] = str(student.enrollments.get().pk)
    return data


@pytest.fixture
def secretary(school):
    return MembershipFactory(school=school, roles=["secretary"]).user


def grades_log(school) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action="grades.changed").order_by("created_at"))


# Droits et isolation


def test_teachers_grade_their_courses_and_homeroom_teachers_their_class(api, school, head):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    data = setup(school, head, teacher=teacher)
    client = api(teacher)
    assert client.get(sheet_url(data["physics"], data["p1"])).status_code == 200
    refused = client.get(sheet_url(data["workshop"], data["p1"]))
    assert refused.status_code == 403 and refused.json()["code"] == "not_your_course"
    assert client.put(sheet_url(data["workshop"], data["p1"]), {}).status_code == 403
    listed = client.get(GRADING).json()
    assert [(c["name"], [x["name"] for x in c["courses"]]) for c in listed["classes"]] == [
        ("1RE ÉLECTRICITÉ A", ["Physique"])
    ]
    assert listed["academic_year"] == str(data["year"].pk) and listed["terms"]

    # Le titulaire note tous les cours de sa classe, pas ceux d'une autre.
    homeroom = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=homeroom)
    assert api(homeroom).get(sheet_url(data["workshop"], data["p1"])).status_code == 200
    assert api(homeroom).get(sheet_url(data["b_physics"], data["p1"])).status_code == 403

    # Sans droit sur les notes : 403 ; le secrétariat (`grades.enter_any`) voit toutes les classes.
    assert api(head).get(sheet_url(data["physics"], data["p1"])).status_code == 403
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert len(api(secretary).get(GRADING).json()["classes"]) == 2

    School.objects.filter(pk=school.pk).update(modules=["students"])
    response = client.get(sheet_url(data["physics"], data["p1"]))
    assert response.status_code == 403 and response.json()["code"] == "module_missing"


def test_another_school_can_neither_read_nor_change_the_grades(
    api, school, other_school, head, other_head, secretary
):
    data = setup(school, head)
    theirs = setup(other_school, other_head)
    outsider = MembershipFactory(school=other_school, roles=["secretary"]).user
    beta = api(outsider, host="beta.localhost")
    with use_school(other_school):
        their_evaluation = Evaluation.objects.create(
            course=theirs["physics"], term=theirs["p1"], name="Interro", max_score=10
        )
    url = sheet_url(data["physics"], data["p1"])
    assert beta.get(url).status_code == 404
    assert beta.put(url, {"evaluations": [{"name": "Interro", "max_score": 10}]}).status_code == 404
    listed = {c["id"] for group in beta.get(GRADING).json()["classes"] for c in group["courses"]}
    assert str(theirs["physics"].pk) in listed and str(data["physics"].pk) not in listed
    # Une période de B avec un cours de A : introuvable aussi.
    assert api(secretary).get(sheet_url(data["physics"], theirs["p1"])).status_code == 404

    # L'identifiant d'une évaluation de B, envoyé par A comme nouveau : refusé, rien ne bouge.
    sent = {"evaluations": [{"id": str(their_evaluation.pk), "name": "Volée", "max_score": 20}]}
    refused = api(secretary).put(url, sent)
    assert refused.status_code == 400
    assert refused.json()["fields"]["evaluations"][0]["code"] == "unknown_evaluation"
    with use_school(other_school):
        their_evaluation.refresh_from_db()
        assert (their_evaluation.name, their_evaluation.course_id) == (
            "Interro",
            theirs["physics"].pk,
        )
    with use_school(school):
        assert not Evaluation.objects.exists()


# Règles de la feuille


def test_period_score_is_brought_back_to_the_maximum_to_a_tenth():
    assert period_score([Decimal(8), Decimal(9), Decimal(14)], [10, 10, 20], 20) == Decimal("15.5")
    assert period_score([Decimal(10)], [30], 20) == Decimal("6.7")
    # La moitié vers le haut : 1 / 80 * 20 = 0,25.
    assert period_score([Decimal(1)], [80], 20) == Decimal("0.3")
    assert period_score([Decimal(8), None], [10, 10], 20) is None
    assert period_score([], [], 20) is None


def test_the_sheet_is_saved_in_one_go_and_noted_once_per_save(
    api, school, head, secretary, django_assert_max_num_queries
):
    data = setup(school, head)
    client = api(secretary)
    url = sheet_url(data["physics"], data["p1"])
    first, second = str(uuid7()), str(uuid7())
    amani, josue = data["amani"], data["josue"]
    # Autant de requêtes quel que soit le nombre de notes (aucune par note).
    with django_assert_max_num_queries(29):
        response = client.put(
            url,
            {
                "evaluations": [
                    {"id": first, "name": "Interrogation 1", "max_score": 10},
                    {"id": second, "name": "Interrogation 2", "max_score": 10},
                    {"name": "TP", "max_score": 20},
                ],
                "grades": [
                    {"enrollment_id": amani, "evaluation_id": first, "score": "8"},
                    {"enrollment_id": amani, "evaluation_id": second, "score": "9"},
                    {"enrollment_id": josue, "evaluation_id": first, "score": "7.5"},
                ],
            },
        )
    assert response.status_code == 200, response.json()
    sheet = response.json()
    tp = sheet["evaluations"][2]["id"]
    assert [e["id"] for e in sheet["evaluations"][:2]] == [first, second]
    assert sheet["maximum"] == 20 and sheet["class_group"] == "1RE ÉLECTRICITÉ A"
    # Les élèves de la classe seulement, par nom ; « incomplet » tant qu'une case manque.
    assert [(row["full_name"], row["total"]) for row in sheet["students"]] == [
        ("Bahati X", None),
        ("Kambale X", None),
    ]

    sent = {"grades": [{"enrollment_id": amani, "evaluation_id": tp, "score": 14}]}
    rows = client.put(url, sent).json()["students"]
    assert rows[0]["total"] == "15.5"

    # Une case vidée, une note corrigée, une évaluation retirée avec ses notes.
    response = client.put(
        url,
        {
            "evaluations": [{"id": second, "name": "Interrogation 2", "max_score": 10}],
            "removed_evaluations": [tp],
            "grades": [
                {"enrollment_id": josue, "evaluation_id": first, "score": None},
                {"enrollment_id": amani, "evaluation_id": second, "score": "10"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["students"][0]["total"] == "18.0"
    with use_school(school):
        assert sorted(Grade.objects.values_list("score", flat=True)) == [8, 10]
        assert Evaluation.objects.count() == 2

    # Rien de changé : pas d'entrée au journal.
    client.put(url, {"grades": [{"enrollment_id": amani, "evaluation_id": first, "score": "8.0"}]})
    logs = grades_log(school)
    assert len(logs) == 3
    assert logs[0].actor_id == secretary.pk and logs[0].entity_type == "academics.gradesheet"
    assert logs[0].entity_label == "Physique · 1RE ÉLECTRICITÉ A · Période 1"
    assert len(logs[0].after["evaluations"]) == 3 and len(logs[0].after["grades"]) == 3
    assert logs[0].before is None
    assert logs[2].before["grades"] == [
        {"student": "Kambale X", "evaluation": "Interrogation 1", "score": "7.5"},
        {"student": "Bahati X", "evaluation": "Interrogation 2", "score": "9.0"},
        {"student": "Bahati X", "evaluation": "TP", "score": "14.0"},
    ]
    assert logs[2].before["evaluations"] == [{"name": "TP", "max_score": 20}]
    assert logs[2].after == {
        "grades": [{"student": "Bahati X", "evaluation": "Interrogation 2", "score": "10.0"}]
    }


def test_wrong_grades_change_nothing(api, school, head, secretary):
    data = setup(school, head)
    client = api(secretary)
    url = sheet_url(data["physics"], data["p1"])
    interro = str(uuid7())
    new = [{"id": interro, "name": "Interrogation", "max_score": 10}]

    def refused(body, path):
        response = client.put(url, body)
        assert response.status_code == 400, response.json()
        return response.json()["fields"][path][0]["code"]

    def grade(enrollment, score):
        return [{"enrollment_id": enrollment, "evaluation_id": interro, "score": score}]

    assert refused({"evaluations": new, "grades": grade(data["amani"], 11)}, "grades.0.score") == (
        "above_maximum"
    )
    assert refused({"evaluations": new, "grades": grade(data["amani"], "7.25")}, "grades.0.score")
    assert refused(
        {"evaluations": new, "grades": grade(data["b"], 5)}, "grades.0.enrollment_id"
    ) == ("unknown_student")
    with use_school(school):
        assert not Evaluation.objects.exists()

    assert (
        client.put(url, {"evaluations": new, "grades": grade(data["amani"], 9)}).status_code == 200
    )
    lowered = [{"id": interro, "name": "Interrogation", "max_score": 8}]
    assert refused({"evaluations": lowered}, "evaluations.0.max_score") == "below_a_grade"

    # Examens : deux fois le maximum, seulement pour un cours avec examen ; jamais un semestre.
    assert client.get(sheet_url(data["physics"], data["exam"])).json()["maximum"] == 40
    for course, term in ((data["workshop"], data["exam"]), (data["physics"], data["semester"])):
        response = client.get(sheet_url(course, term))
        assert response.status_code == 400 and response.json()["code"] == "not_graded_here"


def test_a_graded_course_keeps_its_place_and_its_exam(api, school, head, secretary):
    data = setup(school, head)
    exam = str(uuid7())
    sent = {"evaluations": [{"id": exam, "name": "Examen", "max_score": 40}]}
    assert api(secretary).put(sheet_url(data["physics"], data["exam"]), sent).status_code == 200
    without_exam = [
        {"id": str(data["physics"].pk), "name": "Physique", "period_max": 20, "has_exam": False},
        {"id": str(data["workshop"].pk), "name": "Atelier", "period_max": 100, "has_exam": False},
    ]
    client = api(head)
    response = client.put(courses_url(data["a"]), {"courses": without_exam})
    assert response.status_code == 409 and response.json()["code"] == "exam_graded"
    response = client.put(courses_url(data["a"]), {"courses": without_exam[1:]})
    assert response.status_code == 409 and response.json()["code"] == "course_in_use"


def test_a_graded_period_keeps_its_kind_and_its_place(api, school, head, secretary):
    data = setup(school, head)
    sent = {"evaluations": [{"name": "Interro", "max_score": 10}]}
    assert api(secretary).put(sheet_url(data["physics"], data["p1"]), sent).status_code == 200

    def tree(change=None):
        with use_school(school):
            terms = list(Term.objects.filter(academic_year=data["year"]).order_by("order"))
        nodes = []
        for term in terms:
            node = organisation.TermNode(kind=term.kind, id=term.pk)
            if change and term.pk == data["p1"].pk:
                change(node)
            if term.parent_id is None:
                nodes.append(node)
            else:
                next(n for n in nodes if n.id == term.parent_id).children.append(node)
        return nodes

    def refused(nodes):
        with use_school(school), pytest.raises(BusinessError) as error:
            organisation.set_terms(data["year"], nodes, actor=head)
        return error.value.error.code

    def as_exam(node):
        node.kind = "exam"

    assert refused(tree(as_exam)) == "term_in_use"
    removed = tree()
    removed[0].children = [n for n in removed[0].children if n.id != data["p1"].pk]
    assert refused(removed) == "term_in_use"

    # Son nom et ses dates, eux, se changent.
    def dated(node):
        node.name = "P1"

    with use_school(school):
        organisation.set_terms(data["year"], tree(dated), actor=head)
        assert Term.objects.get(pk=data["p1"].pk).name == "P1"


def test_totals_only_sheet_has_one_total_at_the_period_maximum(api, school, head, secretary):
    """Saisie sans devoirs (8.4.0) : réglage de l'école, dérogation d'un cours ; une feuille aux
    devoirs détaillés les garde ; le bulletin lit le total comme une note de période."""
    data = setup(school, head)
    client = api(head)
    saved = client.patch("/api/school/settings/", {"grading": {"entry": "totals"}})
    assert saved.status_code == 200, saved.json()
    with use_school(school):
        assert AuditLog.objects.filter(after__grading_entry="totals").exists()
    url = sheet_url(data["physics"], data["p1"])
    sheet = api(secretary).get(url).json()
    assert sheet["entry"] == "totals" and sheet["evaluations"] == []

    total = str(uuid7())
    one = {"id": total, "name": "Total", "max_score": 20}
    grade = {"enrollment_id": data["amani"], "evaluation_id": total, "score": "15.5"}
    response = api(secretary).put(url, {"evaluations": [one], "grades": [grade]})
    assert response.status_code == 200, response.json()
    assert response.json()["students"][0]["total"] == "15.5"

    # Un devoir de plus, un autre maximum ou aucune évaluation : refusés.
    for evaluations in (
        [one, {"name": "TP", "max_score": 20}],
        [{"id": total, "name": "Total", "max_score": 10}],
    ):
        refused = api(secretary).put(url, {"evaluations": evaluations, "grades": []})
        assert refused.status_code == 400
        assert refused.json()["code"] == "totals_only"
    # Les examens : le double du maximum du cours.
    exam = sheet_url(data["physics"], data["exam"])
    ok = api(secretary).put(
        exam, {"evaluations": [{"name": "Total", "max_score": 40}], "grades": []}
    )
    assert ok.status_code == 200 and ok.json()["maximum"] == 40

    # Le cours peut déroger au réglage de l'école : devoirs détaillés.
    with use_school(school):
        Course.objects.filter(pk=data["workshop"].pk).update(grade_entry="detailed")
    detailed = sheet_url(data["workshop"], data["p1"])
    assert api(secretary).get(detailed).json()["entry"] == "detailed"
    two = [{"name": "A", "max_score": 50}, {"name": "B", "max_score": 50}]
    assert api(secretary).put(detailed, {"evaluations": two, "grades": []}).status_code == 200


def test_a_sheet_with_several_evaluations_stays_detailed_when_the_school_changes(
    api, school, head, secretary
):
    data = setup(school, head)
    url = sheet_url(data["physics"], data["p1"])
    two = [{"name": "A", "max_score": 10}, {"name": "B", "max_score": 10}]
    assert api(secretary).put(url, {"evaluations": two, "grades": []}).status_code == 200
    api(head).patch("/api/school/settings/", {"grading": {"entry": "totals"}})
    assert api(secretary).get(url).json()["entry"] == "detailed"


def test_the_grading_setting_of_a_school_does_not_reach_another(
    api, school, other_school, head, secretary
):
    api(head).patch("/api/school/settings/", {"grading": {"entry": "totals"}})
    other_school.refresh_from_db()
    assert other_school.grading["entry"] == "detailed"
    # Réglage de l'école : droit `school.configure` seulement.
    refused = api(secretary).patch("/api/school/settings/", {"grading": {"entry": "totals"}})
    assert refused.status_code == 403
