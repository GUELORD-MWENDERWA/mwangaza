"""Notes saisies hors ligne (8.2.3) : l'opération `grades.save` suit les règles de la saisie en
ligne (cours du compte, date limite, feuille validée), s'applique une seule fois et ne touche
jamais une autre école."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics.models import Evaluation, Grade, GradeDeadline
from apps.academics.tests.test_grades import setup
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup
from apps.sync.models import SyncOperation
from apps.sync.tests.test_devices import remember
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PUSH = "/api/sync/push/"


def grades_op(data, evaluation, *, amani="12", course="physics", term="p1", **extra) -> dict:
    return {
        "op_id": str(uuid7()),
        "type": "grades.save",
        "payload": {
            "course": str(data[course].pk),
            "term": str(data[term].pk),
            "evaluations": [{"id": str(evaluation), "name": "Interro", "max_score": 20}],
            "grades": [
                {"enrollment_id": data["amani"], "evaluation_id": str(evaluation), "score": amani}
            ],
            **extra,
        },
        "created_at": "2026-10-05T09:00:00Z",
    }


@pytest.fixture
def teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


def test_a_sheet_typed_offline_is_saved_once_with_the_ids_of_the_device(api, school, head, teacher):
    data = setup(school, head, teacher=teacher)
    client = api(teacher)
    remember(client)
    evaluation = uuid7()
    op = grades_op(data, evaluation)
    first = client.post(PUSH, {"operations": [op]}).json()["results"][0]
    again = client.post(PUSH, {"operations": [op]}).json()["results"][0]
    assert first["status"] == "applied" and again["status"] == "duplicate"
    with use_school(school):
        assert Evaluation.objects.get().pk == evaluation
        assert str(Grade.objects.get().score) == "12.0"
        assert SyncOperation.objects.count() == 1

    # Plus tard, hors ligne encore : la case est corrigée (dernier envoi gagne).
    fixed = client.post(PUSH, {"operations": [grades_op(data, evaluation, amani="14.5")]})
    assert fixed.json()["results"][0]["status"] == "applied"
    with use_school(school):
        assert str(Grade.objects.get().score) == "14.5"


def test_an_offline_sheet_follows_the_online_rules(api, school, head, teacher):
    data = setup(school, head, teacher=teacher)
    client = api(teacher)
    remember(client)

    # Un cours que le compte ne note pas : refusé, rien n'est écrit.
    other = grades_op(data, uuid7(), course="b_physics")
    assert client.post(PUSH, {"operations": [other]}).json()["results"][0]["error"]["code"] == (
        "permission_denied"
    )

    # Date limite passée : refusée avec la raison, gardée visible ; les suivantes passent.
    with use_school(school):
        GradeDeadline.objects.create(term=data["p1"], due_on=timezone.localdate() - timedelta(1))
    late = client.post(PUSH, {"operations": [grades_op(data, uuid7())]}).json()["results"][0]
    assert late["status"] == "rejected" and late["error"]["code"] == "deadline_passed"
    with use_school(school):
        assert Grade.objects.count() == 0
        assert SyncOperation.objects.filter(status="rejected").count() == 2

    # Sans droit sur les notes : refusé.
    promoter = MembershipFactory(school=school, roles=["promoter"]).user
    clerk = api(promoter)
    remember(clerk)
    refused = clerk.post(PUSH, {"operations": [grades_op(data, uuid7(), term="exam")]})
    assert refused.json()["results"][0]["error"]["code"] == "permission_denied"
    # Le titulaire n'y met qu'un total (NB.7), avec les mêmes règles : date limite passée.
    homeroom = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=homeroom)
    titular = api(homeroom)
    remember(titular)
    refused = titular.post(PUSH, {"operations": [grades_op(data, uuid7())]})
    assert refused.json()["results"][0]["error"]["code"] == "deadline_passed"


def test_a_school_cannot_write_the_grades_of_another_school_offline(
    api, school, other_school, head, other_head, teacher
):
    data = setup(school, head, teacher=teacher)
    stranger = MembershipFactory(school=other_school, roles=["study_director"]).user
    client = api(stranger, "beta.localhost")
    remember(client)
    result = client.post(PUSH, {"operations": [grades_op(data, uuid7())]}).json()["results"][0]
    assert result["status"] == "rejected"
    with use_school(school):
        assert Grade.objects.count() == 0 and Evaluation.objects.count() == 0
