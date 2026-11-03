# ruff: noqa: F811, F401
"""Bulletin retenu pour frais impayés et dérogations du préfet (8.4.6) : un frais échu impayé
retient le PDF si l'école l'a choisi ; dérogation d'un élève ou d'une famille, jusqu'à sa date,
levée ; droit dédié, isolation entre écoles, audit ; résultats proclamés et notes validées
notifient une fois."""

import pytest

from apps.academics import waivers
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.finance.tests.test_balance import at
from apps.finance.tests.test_payments import school_with_fees
from apps.finance.tests.test_unpaid import alpha, late
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

WAIVERS = "/api/fee-waivers/"


def require_payment(school, value=True):
    school.settings = {**school.settings, "portal": {"report_requires_payment": value}}
    school.save()


def withheld(school, late) -> set[str]:
    """Qui est retenu parmi Kasereka (rien payé), Amani (reste dû) et Paluku (tout payé)."""
    with use_school(school):
        names = {"kasereka": "Kasereka", "amani": "Amani", "paluku": "Paluku"}
        rows = [
            late[key].__class__.objects.select_related("student").get(pk=late[key].pk)
            for key in names
        ]
        ids = waivers.withheld_ids(rows)
        return {names[key] for key in names if late[key].pk in ids}


def test_a_late_fee_withholds_the_report_card_only_if_the_school_asks_for_it(school, late):
    assert withheld(school, late) == set()
    require_payment(school)
    assert withheld(school, late) == {"Kasereka", "Amani"}
    require_payment(school, False)
    assert withheld(school, late) == set()


def test_a_waiver_frees_a_student_or_a_family_until_its_date_unless_lifted(
    monkeypatch, school, head, late
):
    require_payment(school)
    kasereka, amani = late["kasereka"], late["amani"]
    with use_school(school):
        student_waiver = waivers.grant(
            actor=head,
            reason="Père en voyage, paie vendredi",
            until=waivers.finance.today().replace(day=30),
            family=None,
            student=kasereka.student,
        )
        waivers.grant(
            actor=head,
            reason="Famille de la paroisse",
            until=waivers.finance.today().replace(day=30),
            family=amani.student.family,
            student=None,
        )
    assert withheld(school, late) == set()

    with use_school(school):
        waivers.lift(student_waiver, actor=head)
    assert withheld(school, late) == {"Kasereka"}

    at(monkeypatch, "2026-11-02")  # la dérogation de la famille a expiré
    assert withheld(school, late) == {"Kasereka", "Amani"}


def test_only_the_head_can_grant_a_waiver_and_every_step_is_audited(
    api, school, head, cashier, late
):
    student = str(late["kasereka"].student_id)
    body = {"student": student, "reason": "Accord du préfet", "until": "2026-10-30"}

    assert api(cashier).post(WAIVERS, body).status_code == 403
    assert api(head).post(WAIVERS, {**body, "reason": " "}).status_code == 400
    assert api(head).post(WAIVERS, {**body, "until": "2026-10-01"}).status_code == 400
    created = api(head).post(WAIVERS, body)
    assert created.status_code == 201
    assert created.json()["target_name"] == late["kasereka"].student.full_name

    lifted = api(head).post(f"{WAIVERS}{created.json()['id']}/lift/")
    assert lifted.status_code == 200 and lifted.json()["active"] is False
    assert api(head).post(f"{WAIVERS}{created.json()['id']}/lift/").status_code == 409
    assert api(cashier).post(f"{WAIVERS}{created.json()['id']}/lift/").status_code == 403
    assert api(head).get(f"{WAIVERS}?active=1").json()["results"] == []

    with use_school(school):
        actions = list(
            AuditLog.objects.filter(action__startswith="fee_waiver").values_list(
                "action", flat=True
            )
        )
    assert sorted(actions) == [Action.FEE_WAIVER_GRANTED, Action.FEE_WAIVER_LIFTED]


def test_another_school_cannot_read_lift_or_waive_these_students(
    api, school, other_school, head, late
):
    outsider = MembershipFactory(school=other_school, roles=["head"]).user
    own = (
        api(head)
        .post(
            WAIVERS,
            {
                "student": str(late["kasereka"].student_id),
                "reason": "Accord",
                "until": "2026-10-30",
            },
        )
        .json()
    )

    foreign = api(outsider, host="beta.localhost")
    assert foreign.get(WAIVERS).json()["results"] == []
    assert foreign.post(f"{WAIVERS}{own['id']}/lift/").status_code == 404
    body = {
        "student": str(late["kasereka"].student_id),
        "reason": "Piraterie",
        "until": "2026-10-30",
    }
    assert foreign.post(WAIVERS, body).status_code == 404
    beta = school_with_fees(other_school, outsider)
    student = enrolled(other_school, outsider, beta["group"], last_name="Autre")
    assert (
        api(head)
        .post(WAIVERS, {"student": str(student.pk), "reason": "Accord", "until": "2026-10-30"})
        .status_code
        == 404
    )
