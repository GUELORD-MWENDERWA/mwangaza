"""Contrôle des notes (8.2.2, NB.1) : état de la feuille (brouillon, envoyée et signée, validée,
renvoyée avec remarques), fiche de cotes (totaux seuls) pour le directeur des études et le
titulaire, notifications, date limite de saisie, motif d'une modification après envoi, maximum d'un
cours déjà noté, historique et isolation entre écoles."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics.models import Course, GradeDeadline
from apps.academics.tests.test_courses import courses_url
from apps.academics.tests.test_grades import setup, sheet_url
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.notifications.models import Notification
from apps.schools.models import ClassGroup
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

VALIDATION = "/api/grading/validation/"
REMINDERS = "/api/grading/reminders/"


def states(client, term=None) -> dict:
    """Tableau du directeur des études (NB.2) : état de chaque cours, par classe."""
    board = client.get(VALIDATION, **({"term": term.pk} if term else {})).json()
    return {
        group["name"]: {course["name"]: course["status"] for course in group["courses"]}
        for group in board["classes"]
    }


def deadline_url(term) -> str:
    return f"/api/terms/{term.pk}/grades-deadline/"


def action_url(course, term, action) -> str:
    return f"{sheet_url(course, term)}{action}/"


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def director(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


def fill(client, data, *, amani="12", josue="15", reason=None) -> dict:
    """Une évaluation sur 20 et les deux notes ; renvoie la feuille."""
    url = sheet_url(data["physics"], data["p1"])
    body = {"evaluations": [{"name": "Interro", "max_score": 20}]}
    first = client.put(url, body).json()["evaluations"][0]["id"]
    body = {
        "grades": [
            {"enrollment_id": data["amani"], "evaluation_id": first, "score": amani},
            {"enrollment_id": data["josue"], "evaluation_id": first, "score": josue},
        ],
        **({"reason": reason} if reason else {}),
    }
    return client.put(url, body)


def notified(school, kind) -> list[tuple[str, str]]:
    with use_school(school):
        rows = Notification.objects.filter(kind=kind).select_related("user").order_by("user_id")
        return [(row.user_id, row.url) for row in rows]


def test_a_sheet_is_sent_and_signed_then_validated_or_returned_with_remarks(
    api, school, head, teacher, director
):
    data = setup(school, head, teacher=teacher)
    homeroom = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=homeroom)
    client, boss = api(teacher), api(director)
    submit = action_url(data["physics"], data["p1"], "submit")
    totals = f"{sheet_url(data['physics'], data['p1'])}totals/"
    assert fill(client, data).json()["status"] == "draft"
    # Pas encore envoyée : la fiche de cotes ne montre que son état.
    early = boss.get(totals).json()
    assert early["status"] == "draft" and early["students"] == []

    # Une case manque : refusé ; complète : envoyée et signée, le directeur des études et le
    # titulaire sont avertis et lisent les totaux, sans les évaluations.
    url = sheet_url(data["physics"], data["p1"])
    evaluation = client.get(url).json()["evaluations"][0]["id"]
    client.put(
        url,
        {"grades": [{"enrollment_id": data["josue"], "evaluation_id": evaluation, "score": None}]},
    )
    refused = client.post(submit)
    assert refused.status_code == 400 and refused.json()["code"] == "incomplete_sheet"
    client.put(
        url,
        {"grades": [{"enrollment_id": data["josue"], "evaluation_id": evaluation, "score": "15"}]},
    )
    sent_sheet = client.post(submit).json()
    assert sent_sheet["status"] == "submitted" and sent_sheet["submitted_by"] == str(teacher)
    assert client.post(submit).json()["code"] == "sheet_not_draft"
    assert states(boss, data["p1"])["1RE ÉLECTRICITÉ A"]["Physique"] == "submitted"
    link = f"/grade-sheets/totals?course={data['physics'].pk}&term={data['p1'].pk}"
    assert notified(school, "grades_sent") == sorted([(director.pk, link), (homeroom.pk, link)])
    for reader in (boss, api(homeroom)):
        fiche = reader.get(totals).json()
        assert "evaluations" not in fiche and fiche["submitted_by"] == str(teacher)
        assert [(row["full_name"], row["total"]) for row in fiche["students"]] == [
            ("Bahati X", "12.0"),
            ("Kambale X", "15.0"),
        ]
        assert all("scores" not in row for row in fiche["students"])
    # Un autre enseignant, ni titulaire ni enseignant du cours : pas même la fiche.
    other = api(MembershipFactory(school=school, roles=["teacher"]).user)
    assert other.get(totals).status_code == 403

    # Envoyée : changer une note demande un motif, gardé dans l'historique de la feuille.
    sent = {
        "grades": [{"enrollment_id": data["amani"], "evaluation_id": evaluation, "score": "13"}]
    }
    refused = client.put(url, sent)
    assert refused.status_code == 400 and refused.json()["code"] == "reason_required"
    changed = client.put(url, {**sent, "reason": "Erreur de copie"}).json()
    assert (
        changed["history"][0]["reason"] == "Erreur de copie"
        and changed["history"][0]["changes"] == 1
    )

    # Seul qui a `grades.validate` valide ; la feuille validée est fermée à tous.
    assert client.post(action_url(data["physics"], data["p1"], "validate")).status_code == 403
    validated = boss.post(action_url(data["physics"], data["p1"], "validate")).json()
    assert validated["status"] == "validated" and "evaluations" not in validated
    closed = client.put(url, {**sent, "reason": "Encore"})
    assert closed.status_code == 409 and closed.json()["code"] == "sheet_validated"
    assert states(boss)["1RE ÉLECTRICITÉ A"]["Physique"] == "validated"

    # Renvoyée avec remarques (obligatoires) : brouillon rouvert, l'enseignant est averti et lit
    # les remarques dans son carnet ; elles sont au journal.
    reopen = action_url(data["physics"], data["p1"], "reopen")
    assert boss.post(reopen, {"reason": ""}).status_code == 400
    assert client.post(reopen, {"reason": "Moi"}).status_code == 403
    returned = boss.post(reopen, {"reason": "Note à corriger"}).json()
    assert returned["status"] == "draft" and returned["reopened"] is True
    assert notified(school, "grades_returned") == [
        (teacher.pk, f"/grades?course={data['physics'].pk}&term={data['p1'].pk}")
    ]
    assert states(boss)["1RE ÉLECTRICITÉ A"]["Physique"] == "returned"
    remarks = client.get(url).json()["returned"]
    assert (remarks["reason"], remarks["by"]) == ("Note à corriger", str(director))
    with use_school(school):
        actions = list(
            AuditLog.objects.filter(action__startswith="grades.")
            .values_list("action", flat=True)
            .order_by("created_at")
        )
        reason = AuditLog.objects.get(action="grades.reopened").after["reason"]
    assert "grades.submitted" in actions
    assert actions[-3:] == ["grades.changed", "grades.validated", "grades.reopened"]
    assert reason == "Note à corriger"
    # Envoyée de nouveau : les remarques ne sont plus affichées.
    assert client.post(submit).json()["returned"] is None


def test_the_board_shows_each_course_and_late_teachers_are_reminded_once_a_day(
    api, school, head, teacher, director, django_assert_max_num_queries
):
    """NB.2 : pas commencée (aucune évaluation), en cours ; rappel groupé par enseignant (une
    notification), cours sans enseignant ou déjà rappelé aujourd'hui ignoré, trace au journal."""
    data = setup(school, head, teacher=teacher)
    other = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        Course.objects.filter(pk=data["b_physics"].pk).update(teacher=other)
    fill(api(teacher), data)
    boss = api(director)
    # Période par défaut : la dernière commencée ; requêtes bornées.
    with django_assert_max_num_queries(16):
        board = boss.get(VALIDATION).json()
    assert board["term"] == str(data["p1"].pk)
    assert states(boss, data["p1"]) == {
        "1RE ÉLECTRICITÉ A": {"Physique": "in_progress", "Atelier": "not_started"},
        "1RE ÉLECTRICITÉ B": {"Physique": "not_started"},
    }
    assert api(teacher).post(REMINDERS, {"term": data["p1"].pk, "courses": []}).status_code == 403

    courses = [data["physics"].pk, data["workshop"].pk, data["b_physics"].pk]
    body = {"term": data["p1"].pk, "courses": courses}
    assert boss.post(REMINDERS, body).json() == {"notified": 2, "reminded": 2, "skipped": 1}
    link = f"/grades?course={data['physics'].pk}&term={data['p1'].pk}"
    other_link = f"/grades?course={data['b_physics'].pk}&term={data['p1'].pk}"
    expected = sorted([(teacher.pk, link), (other.pk, other_link)])
    assert notified(school, "grades_reminder") == expected
    # Le même jour : personne n'est rappelé deux fois.
    assert boss.post(REMINDERS, body).json() == {"notified": 0, "reminded": 0, "skipped": 3}
    first = boss.get(VALIDATION).json()["classes"][0]["courses"]
    assert {c["name"]: c["reminded_today"] for c in first} == {"Atelier": False, "Physique": True}
    with use_school(school):
        log = AuditLog.objects.get(action="grades.reminded")
    assert sorted(log.after["courses"]) == sorted(str(pk) for pk in courses[::2])
    # Sans le module Notifications, rien ne part.
    with use_school(school):
        school.modules = [m for m in school.modules if m != "notifications"]
        school.save(update_fields=["modules"])
    refused = boss.post(REMINDERS, body)
    assert refused.status_code == 409 and refused.json()["code"] == "notifications_off"


def test_the_deadline_closes_the_entry_except_for_a_reopened_sheet_or_the_validator(
    api,
    school,
    head,
    teacher,
    director,
):
    data = setup(school, head, teacher=teacher)
    client, boss = api(teacher), api(director)
    fill(client, data)
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    assert client.put(deadline_url(data["p1"]), {"due_on": yesterday}).status_code == 403
    assert boss.put(deadline_url(data["p1"]), {"due_on": yesterday}).status_code == 200
    # Pas une période regroupant d'autres : on ne note que périodes et examens.
    assert boss.put(deadline_url(data["semester"]), {"due_on": yesterday}).status_code == 400

    url = sheet_url(data["physics"], data["p1"])
    evaluation = client.get(url).json()["evaluations"][0]["id"]
    late = {"grades": [{"enrollment_id": data["amani"], "evaluation_id": evaluation, "score": "9"}]}
    refused = client.put(url, late)
    assert refused.status_code == 409 and refused.json()["code"] == "deadline_passed"
    assert client.get(url).json()["due_on"] == yesterday
    # Le jour même est encore permis ; le directeur des études peut saisir un total après la date.
    today = timezone.localdate().isoformat()
    boss.put(deadline_url(data["p1"]), {"due_on": today})
    assert client.put(url, late).status_code == 200
    boss.put(deadline_url(data["p1"]), {"due_on": yesterday})
    assert boss.put(url, late).status_code == 200
    # Une feuille envoyée puis rouverte n'est plus fermée par la date.
    assert client.post(action_url(data["physics"], data["p1"], "submit")).status_code == 200
    boss.post(action_url(data["physics"], data["p1"], "reopen"), {"reason": "Retard justifié"})
    assert client.put(url, late).status_code == 200
    boss.put(deadline_url(data["p1"]), {"due_on": None})
    with use_school(school):
        assert not GradeDeadline.objects.exists()


def test_the_maximum_of_a_graded_course_changes_only_with_validation_rights(
    api,
    school,
    head,
    teacher,
    director,
):
    data = setup(school, head, teacher=teacher)
    fill(api(teacher), data)
    grid = [
        {
            "id": str(c["id"]),
            "name": c["name"],
            "period_max": c["period_max"],
            "has_exam": c["has_exam"],
        }
        for c in api(head).get(courses_url(data["a"])).json()
    ]
    for row in grid:
        if row["name"] == "Physique":
            row["period_max"] = 40
    # Le directeur (`courses.configure` seul) est refusé ; le directeur des études passe.
    refused = api(head).put(courses_url(data["a"]), {"courses": grid})
    assert refused.status_code == 409 and refused.json()["code"] == "max_graded"
    assert api(director).put(courses_url(data["a"]), {"courses": grid}).status_code == 200


def test_another_school_cannot_see_validate_or_reopen_these_grades(
    api,
    school,
    other_school,
    head,
    other_head,
    teacher,
    director,
):
    data = setup(school, head, teacher=teacher)
    setup(other_school, other_head)
    fill(api(teacher), data)
    api(teacher).post(action_url(data["physics"], data["p1"], "submit"))
    foreign = MembershipFactory(school=other_school, roles=["study_director"]).user
    beta = api(foreign, host="beta.localhost")
    # Le tableau de l'autre école ne montre que ses propres cours ; une période d'ici : 400.
    own = {c["id"] for g in beta.get(VALIDATION).json()["classes"] for c in g["courses"]}
    assert own and str(data["physics"].pk) not in own
    assert beta.get(VALIDATION, term=data["p1"].pk).status_code == 400
    late = {"term": data["p1"].pk, "courses": [data["workshop"].pk]}
    assert beta.post(REMINDERS, late).status_code == 400
    for action in ("validate", "reopen", "submit"):
        assert (
            beta.post(action_url(data["physics"], data["p1"], action), {"reason": "x"}).status_code
            == 404
        )
    assert beta.put(deadline_url(data["p1"]), {"due_on": None}).status_code == 404
    totals = action_url(data["physics"], data["p1"], "totals")
    assert beta.get(sheet_url(data["physics"], data["p1"])).status_code == 404
    assert beta.get(totals).status_code == 404
    assert api(director).get(totals).json()["status"] == "submitted"
