"""Réductions (2.5.2, E3) : réparties au prorata des frais dus, cumulées sans dépasser le frais,
elles suivent un échéancier particulier ; retrait noté, jamais effacé ; refus ; audit ;
isolation entre écoles et droits de l'API."""

import pytest

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance.tests.test_api import entries, field_code, setup
from apps.finance.tests.test_charges import of, once, reschedule_body, rule
from apps.students import services as students
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

DISCOUNTS = "/api/discounts/"


@pytest.fixture
def alpha(school, head):
    return setup(school, head)


@pytest.fixture
def beta(other_school, other_head):
    return setup(other_school, other_head)


def body(enrollment, fee_type=None, **changes) -> dict:
    return {
        "enrollment": str(enrollment.pk),
        "fee_type": str(fee_type.pk) if fee_type else None,
        "kind": "percent",
        "percent": 25,
        "reason_code": "scholarship",
        "reason": "Bourse de la paroisse, lettre du 12/10/2026",
        **changes,
    }


def shares(client, enrollment) -> dict[str, list[int]]:
    """Part des réductions de chaque frais dû actif, par type de frais."""
    result: dict[str, list[int]] = {}
    for row in client.get(of(enrollment)).json():
        if row["status"] == "active":
            result.setdefault(row["fee_type_name"], []).append(row["discount_minor"])
    return result


def test_discounts_spread_over_the_charges_add_up_and_follow_a_custom_schedule(
    api, school, head, alpha
):
    with use_school(school):
        rule(head, alpha, "Fonctionnement", "CDF", once("Fonctionnement", 25000))
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    client, minerval = api(head), alpha["fee_type"]

    # 25 % du minerval (trois tranches de 120,00 $) : 30,00 $ sur chaque tranche.
    response = client.post(DISCOUNTS, body(enrollment, minerval))
    assert response.status_code == 201, response.content
    percent = response.json()
    assert (percent["granted_by"]["id"], percent["revoked_at"]) == (str(head.pk), None)
    assert shares(client, enrollment) == {"Minerval": [3000] * 3, "Fonctionnement": [0]}

    # Plus 50,00 $ : 140,00 $ au prorata, l'écart d'arrondi sur la dernière tranche.
    amount = {"kind": "amount", "amount_minor": 5000, "reason_code": "sibling"}
    assert client.post(DISCOUNTS, body(enrollment, minerval, **amount)).status_code == 201
    assert shares(client, enrollment)["Minerval"] == [4667, 4667, 4666]

    # 10 % sur tous les frais, chacun dans sa devise (3 600 $ cents ; 2 500 FC).
    everything = client.post(DISCOUNTS, body(enrollment, percent=10, reason_code="waiver"))
    assert everything.status_code == 201, everything.content
    assert shares(client, enrollment) == {
        "Minerval": [5867, 5867, 5866],
        "Fonctionnement": [2500],
    }
    # Cumulées, les réductions ne dépassent jamais le frais.
    full = {"kind": "amount", "amount_minor": 36000, "reason_code": "other"}
    assert client.post(DISCOUNTS, body(enrollment, minerval, **full)).status_code == 201
    assert shares(client, enrollment)["Minerval"] == [12000] * 3

    # Retirée : noté (qui, quand, motif), rien d'effacé ; une seconde fois : refusé.
    revoke = f"{DISCOUNTS}{everything.json()['id']}/revoke/"
    assert client.post(revoke, {"reason": " "}).status_code == 400
    response = client.post(revoke, {"reason": "Erreur de saisie"})
    assert response.status_code == 200, response.content
    assert response.json()["revoke_reason"] == "Erreur de saisie"
    assert client.post(revoke, {"reason": "Encore"}).json()["code"] == "discount_revoked"
    full_id = client.get(f"{DISCOUNTS}?enrollment={enrollment.pk}").json()[-1]["id"]
    client.post(f"{DISCOUNTS}{full_id}/revoke/", {"reason": "Bourse retirée"})
    assert len(client.get(f"{DISCOUNTS}?enrollment={enrollment.pk}").json()) == 4
    assert shares(client, enrollment) == {"Minerval": [4667, 4667, 4666], "Fonctionnement": [0]}

    # Un échéancier particulier : la réduction se répartit sur les nouveaux versements.
    schedule = reschedule_body(enrollment, minerval, [18000, 18000])
    assert client.post("/api/student-charges/reschedule/", schedule).status_code == 200
    assert shares(client, enrollment)["Minerval"] == [7000, 7000]

    [granted, *_others] = entries(school, Action.FINANCE_DISCOUNT_GRANTED)
    assert (granted.entity_id, granted.actor_id) == (enrollment.pk, head.pk)
    assert granted.after == {
        "fee_type": "Minerval",
        "reason_code": "scholarship",
        "reason": "Bourse de la paroisse, lettre du 12/10/2026",
        "percent": 25,
    }
    revoked = entries(school, Action.FINANCE_DISCOUNT_REVOKED)
    assert [log.after for log in revoked] == [
        {"revoke_reason": "Erreur de saisie"},
        {"revoke_reason": "Bourse retirée"},
    ]
    assert revoked[0].before["percent"] == 10 and revoked[0].before["fee_type"] is None


def test_a_discount_is_refused_when_it_does_not_fit_what_the_student_owes(api, school, head, alpha):
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    client, minerval = api(head), alpha["fee_type"]
    amount = {"kind": "amount", "amount_minor": 36001}

    assert field_code(client.post(DISCOUNTS, body(enrollment, reason=" ")), "reason") == "blank"
    assert field_code(client.post(DISCOUNTS, body(enrollment, percent=101)), "percent")
    assert field_code(client.post(DISCOUNTS, body(enrollment, kind="amount")), "amount_minor")
    no_fee = client.post(DISCOUNTS, body(enrollment, **amount))
    assert field_code(no_fee, "fee_type") == "fee_required"
    too_much = client.post(DISCOUNTS, body(enrollment, minerval, **amount))
    assert field_code(too_much, "amount_minor") == "discount_exceeds_fee"
    with use_school(school):
        other_type = rule(head, alpha, "Cantine", "USD", once("Cantine", 2000)).fee_type
        other_type.charges.all().update(status="removed")
    nothing = client.post(DISCOUNTS, body(enrollment, other_type))
    assert field_code(nothing, "fee_type") == "nothing_to_discount"
    with use_school(school):
        students.update_enrollment(enrollment, actor=head, status=Enrollment.Status.DROPPED)
    gone = client.post(DISCOUNTS, body(enrollment, minerval))
    assert field_code(gone, "enrollment") == "enrollment_not_active"
    assert not entries(school, Action.FINANCE_DISCOUNT_GRANTED)


def test_discounts_need_the_right_and_stay_in_the_students_school(
    api, school, head, alpha, other_school, other_head, beta
):
    student = enrolled(school, head, alpha["group"])
    other = enrolled(other_school, other_head, beta["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    with use_school(other_school):
        other_enrollment = other.enrollments.get()
    granted = api(head).post(DISCOUNTS, body(enrollment, alpha["fee_type"]))
    revoke = f"{DISCOUNTS}{granted.json()['id']}/revoke/"
    listing = f"{DISCOUNTS}?enrollment={enrollment.pk}"

    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    assert len(api(cashier).get(listing).json()) == 1
    assert api(cashier).post(DISCOUNTS, body(enrollment)).status_code == 403
    assert api(cashier).post(revoke, {"reason": "Non"}).status_code == 403
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get(listing).status_code == 403

    beta_client = api(other_head, host="beta.localhost")
    assert beta_client.get(listing).json() == []
    assert beta_client.post(revoke, {"reason": "Non"}).status_code == 404
    assert field_code(beta_client.post(DISCOUNTS, body(enrollment)), "enrollment") == (
        "does_not_exist"
    )
    foreign_fee = body(other_enrollment, alpha["fee_type"])
    assert field_code(beta_client.post(DISCOUNTS, foreign_fee), "fee_type") == "does_not_exist"
    assert shares(beta_client, other_enrollment) == {"Minerval": [0] * 3}
    assert shares(api(head), enrollment) == {"Minerval": [3000] * 3}
    assert len(entries(school, Action.FINANCE_DISCOUNT_GRANTED)) == 1
    assert not entries(school, Action.FINANCE_DISCOUNT_REVOKED)
    assert not entries(other_school, Action.FINANCE_DISCOUNT_GRANTED)
