"""Frais dus des élèves (2.6) : générés à l'inscription d'après le barème le plus précis,
recalculés au changement de classe et quand un barème change, jamais effacés ; échéancier
particulier ; isolation entre écoles et droits de l'API."""

from datetime import date

import pytest

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import StudentCharge
from apps.finance.services import Installment, Scope
from apps.finance.tests.test_api import THREE_TRANCHES, entries, field_code, setup
from apps.schools import organisation
from apps.students import services as students
from apps.students.models import Enrollment
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

CHARGES = "/api/student-charges/"
Status = StudentCharge.Status


@pytest.fixture
def alpha(school, head):
    return setup(school, head)


@pytest.fixture
def beta(other_school, other_head):
    return setup(other_school, other_head)


def of(enrollment) -> str:
    return f"{CHARGES}?enrollment={enrollment.pk}"


def once(label: str, amount: int, day: str = "2026-09-30") -> list[Installment]:
    return [Installment(label, amount, date.fromisoformat(day))]


def rule(actor, data, name, currency, installments, scope=services.WHOLE_SCHOOL):
    fee_type = services.create_fee_type(actor=actor, name=name, category="custom")
    return services.create_fee_rule(
        actor=actor,
        academic_year=data["year"],
        fee_type=fee_type,
        currency=currency,
        total_amount_minor=sum(item.amount_minor for item in installments),
        schedule_kind="single" if len(installments) == 1 else "installments",
        installments=installments,
        scope=scope,
    )


def charges(enrollment, status=Status.ACTIVE) -> set[tuple]:
    return {
        (charge.fee_type.name, charge.label, charge.amount_minor, charge.currency)
        for charge in StudentCharge.objects.filter(
            enrollment=enrollment, status=status
        ).select_related("fee_type")
    }


MINERVAL_3E = {
    ("Minerval", "1re tranche", 12000, "USD"),
    ("Minerval", "2e tranche", 12000, "USD"),
    ("Minerval", "3e tranche", 12000, "USD"),
}


def test_enrollment_gets_one_charge_per_installment_of_the_most_precise_rule(school, head, alpha):
    with use_school(school):
        group = alpha["group"]
        # Minerval : la classe l'emporte sur le niveau. Atelier : l'option sur toute l'école.
        services.create_fee_rule(
            actor=head,
            academic_year=alpha["year"],
            fee_type=alpha["fee_type"],
            currency="USD",
            total_amount_minor=45000,
            schedule_kind="single",
            installments=once("Paiement unique", 45000),
            scope=Scope(class_group=group),
        )
        workshop = rule(head, alpha, "Atelier", "CDF", once("Atelier (école)", 50000))
        services.create_fee_rule(
            actor=head,
            academic_year=alpha["year"],
            fee_type=workshop.fee_type,
            currency="CDF",
            total_amount_minor=80000,
            schedule_kind="single",
            installments=once("Atelier (option)", 80000),
            scope=Scope(track=alpha["track"]),
        )
        rule(head, alpha, "Exetat", "USD", once("Exetat", 3000), Scope(level=alpha["other_level"]))
    student = enrolled(school, head, group)
    with use_school(school):
        enrollment = student.enrollments.get()
        assert charges(enrollment) == {
            ("Minerval", "Paiement unique", 45000, "USD"),
            ("Atelier", "Atelier (option)", 80000, "CDF"),
        }
        charge = StudentCharge.objects.get(enrollment=enrollment, fee_type=alpha["fee_type"])
        assert (charge.source, charge.due_on) == (StudentCharge.Source.RULE, date(2026, 9, 30))


def test_class_change_moves_the_charges_and_a_return_reuses_the_old_ones(school, head, alpha):
    with use_school(school):
        fourth = organisation.create_class_group(
            actor=head,
            academic_year=alpha["year"],
            level=alpha["other_level"],
            track=alpha["track"],
            section="A",
            capacity=45,
        )
        services.create_fee_rule(
            actor=head,
            academic_year=alpha["year"],
            fee_type=alpha["fee_type"],
            currency="CDF",
            total_amount_minor=900000,
            schedule_kind="single",
            installments=once("Paiement unique", 900000),
            scope=Scope(level=alpha["other_level"]),
        )
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
        students.update_enrollment(enrollment, actor=head, class_group=fourth)
        assert charges(enrollment) == {("Minerval", "Paiement unique", 900000, "CDF")}
        # Les frais de l'ancienne classe restent, retirés : rien n'est effacé.
        assert charges(enrollment, Status.REMOVED) == MINERVAL_3E

        students.update_enrollment(enrollment, actor=head, class_group=alpha["group"])
        assert charges(enrollment) == MINERVAL_3E
        assert StudentCharge.objects.filter(enrollment=enrollment).count() == 4


def test_fee_rule_changes_follow_active_students_and_spare_those_who_left(school, head, alpha):
    staying = enrolled(school, head, alpha["group"], first_name="Josué")
    leaving = enrolled(school, head, alpha["group"], first_name="Neema")
    with use_school(school):
        stays, left = (s.enrollments.get() for s in (staying, leaving))
        students.update_enrollment(left, actor=head, status=Enrollment.Status.DROPPED)

        services.update_fee_rule(
            alpha["rule"],
            actor=head,
            currency="USD",
            total_amount_minor=26000,
            schedule_kind="installments",
            installments=[
                Installment("1re tranche", 13000, date(2026, 10, 15)),
                Installment("2e tranche", 13000, date(2027, 1, 15)),
            ],
            scope=Scope(level=alpha["level"]),
        )
        assert charges(stays) == {
            ("Minerval", "1re tranche", 13000, "USD"),
            ("Minerval", "2e tranche", 13000, "USD"),
        }
        assert charges(stays, Status.REMOVED) == {("Minerval", "3e tranche", 12000, "USD")}
        # Un élève parti garde ses dettes telles qu'elles étaient.
        assert charges(left) == MINERVAL_3E
        [log] = entries(school, Action.FINANCE_FEE_RULE_UPDATED)
        assert log.after["students_updated"] == 1

        services.delete_fee_rule(alpha["rule"], actor=head)
        assert charges(stays) == set()
        assert StudentCharge.objects.filter(enrollment=stays).count() == 3
        assert charges(left) == MINERVAL_3E

        # Le retour dans l'année recalcule d'après les barèmes du moment.
        rule(head, alpha, "Fonctionnement", "USD", once("Fonctionnement", 2500))
        students.update_enrollment(left, actor=head, status=Enrollment.Status.ACTIVE)
        assert charges(left) == {("Fonctionnement", "Fonctionnement", 2500, "USD")}


def test_charges_of_a_student_are_read_with_a_finance_right_in_their_school_only(
    api, school, head, alpha, other_school, other_head, beta
):
    student = enrolled(school, head, alpha["group"])
    other = enrolled(other_school, other_head, beta["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    with use_school(other_school):
        other_enrollment = other.enrollments.get()

    response = api(head).get(of(enrollment))
    assert response.status_code == 200
    rows = response.json()
    assert [(row["label"], row["amount_minor"], row["fee_type_name"]) for row in rows] == [
        (item["label"], item["amount_minor"], "Minerval") for item in THREE_TRANCHES
    ]
    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    assert api(cashier).get(of(enrollment)).status_code == 200

    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get(of(enrollment)).status_code == 403

    beta_client = api(other_head, host="beta.localhost")
    response = beta_client.get(of(enrollment))
    assert response.status_code == 200 and response.json() == []
    response = beta_client.get(of(other_enrollment))
    assert len(response.json()) == 3
    assert api(head).get(CHARGES).status_code == 400


# Échéancier particulier (2.6.2, E4)

RESCHEDULE = f"{CHARGES}reschedule/"
MONTHS = ["2026-11-15", "2026-12-15", "2027-01-15", "2027-02-15", "2027-03-15", "2027-04-15"]


def versements(amounts: list[int]) -> list[dict]:
    return [
        {"label": f"Versement {n}", "amount_minor": amount, "due_on": day}
        for n, (amount, day) in enumerate(zip(amounts, MONTHS, strict=False), start=1)
    ]


def reschedule_body(enrollment, fee_type, amounts: list[int], **changes) -> dict:
    return {
        "enrollment": str(enrollment.pk),
        "fee_type": str(fee_type.pk),
        "reason": "Arrangement avec le père (perte d'emploi en septembre)",
        "parent_signed": True,
        "installments": versements(amounts),
        **changes,
    }


def test_custom_schedule_replaces_the_unpaid_charges_and_no_longer_follows_the_rules(
    api, school, head, alpha
):
    with use_school(school):
        rule(head, alpha, "Fonctionnement", "USD", once("Fonctionnement", 2500))
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    client, minerval = api(head), alpha["fee_type"]

    # Le total doit égaler le reste à réorganiser, au centime près ; le motif est obligatoire.
    wrong = client.post(RESCHEDULE, reschedule_body(enrollment, minerval, [6000] * 5 + [5999]))
    assert field_code(wrong, "installments") == "schedule_total_mismatch"
    blank = client.post(RESCHEDULE, reschedule_body(enrollment, minerval, [6000] * 6, reason=" "))
    assert field_code(blank, "reason") == "blank"

    response = client.post(RESCHEDULE, reschedule_body(enrollment, minerval, [6000] * 6))
    assert response.status_code == 200, response.content
    assert len(response.json()) == 10
    with use_school(school):
        six = {("Minerval", f"Versement {n}", 6000, "USD") for n in range(1, 7)}
        running = {("Fonctionnement", "Fonctionnement", 2500, "USD")}
        assert charges(enrollment) == six | running
        # Les tranches remplacées restent, pour l'histoire ; elles ne sont plus dues.
        assert charges(enrollment, Status.REPLACED) == MINERVAL_3E
        custom = StudentCharge.objects.filter(enrollment=enrollment, source="custom")
        assert custom.count() == 6 and not custom.filter(installment_template__isnull=False)
        [log] = entries(school, Action.FINANCE_CHARGES_RESCHEDULED)
        assert log.entity_id == enrollment.pk
        assert (log.after["reason"], log.after["parent_signed"]) == (
            "Arrangement avec le père (perte d'emploi en septembre)",
            True,
        )
        assert [i["amount_minor"] for i in log.before["charges"]] == [12000] * 3
        assert len(log.after["installments"]) == 6

        # Un barème modifié ne touche plus l'arrangement (ni un changement de classe : même calcul).
        services.update_fee_rule(
            alpha["rule"],
            actor=head,
            currency="USD",
            total_amount_minor=26000,
            schedule_kind="single",
            installments=once("Paiement unique", 26000),
            scope=Scope(level=alpha["level"]),
        )
        assert charges(enrollment) == six | running
        assert StudentCharge.objects.filter(enrollment=enrollment, fee_type=minerval).count() == 9

    # Un nouvel arrangement remplace les versements pas encore payés du premier.
    response = client.post(RESCHEDULE, reschedule_body(enrollment, minerval, [18000, 18000]))
    assert response.status_code == 200, response.content
    with use_school(school):
        assert charges(enrollment, Status.REPLACED) == MINERVAL_3E | six
        students.update_enrollment(enrollment, actor=head, status=Enrollment.Status.DROPPED)
    gone = client.post(RESCHEDULE, reschedule_body(enrollment, minerval, [36000]))
    assert field_code(gone, "enrollment") == "enrollment_not_active"


def test_custom_schedule_needs_the_discount_right_in_the_students_school(
    api, school, head, alpha, other_school, other_head, beta
):
    student = enrolled(school, head, alpha["group"])
    other = enrolled(other_school, other_head, beta["group"])
    with use_school(school):
        enrollment = student.enrollments.get()
    with use_school(other_school):
        other_enrollment = other.enrollments.get()
    body = reschedule_body(enrollment, alpha["fee_type"], [6000] * 6)

    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    assert api(cashier).post(RESCHEDULE, body).status_code == 403
    beta_client = api(other_head, host="beta.localhost")
    assert field_code(beta_client.post(RESCHEDULE, body), "enrollment") == "does_not_exist"
    foreign_fee = reschedule_body(other_enrollment, alpha["fee_type"], [6000] * 6)
    assert field_code(beta_client.post(RESCHEDULE, foreign_fee), "fee_type") == "does_not_exist"
    with use_school(school):
        assert charges(enrollment) == MINERVAL_3E
        assert not entries(school, Action.FINANCE_CHARGES_RESCHEDULED)
