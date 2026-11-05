"""Inscription hors ligne (HL.1) : élève, famille, inscription et frais dus créés sur l'appareil,
encaissables tout de suite ; numéros définitifs à la synchronisation ; doublon signalé, jamais
fusionné."""

from types import SimpleNamespace

import pytest

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.finance.models import InstallmentTemplate, Payment, StudentCharge
from apps.notifications.models import Notification
from apps.students.models import Enrollment, Family, Student
from apps.students.tests.conftest import new_student
from apps.sync.tests.test_devices import remember
from apps.sync.tests.test_sync import PUSH, SNAPSHOT, open_op, payment_op
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

BIRTH = "2011-03-12"


def enroll_op(group, *, charges=(), family=None, distinct_from=(), **student) -> dict:
    """L'élève, sa nouvelle famille (ou `family`) et son inscription, comme l'appareil les crée."""
    payload = {
        "id": str(uuid7()),
        "last_name": "Bisimwa",
        "middle_name": "Mugisho",
        "first_name": "Arsène",
        "sex": "M",
        "birth_date": BIRTH,
        "enrollment_id": str(uuid7()),
        "class_group": str(group.pk),
        "enrolled_on": "2026-10-02",
        "charges": [{"id": str(uuid7()), "installment_template": str(t)} for t in charges],
        "distinct_from": [str(other) for other in distinct_from],
        **student,
    }
    if family is None:
        payload["family_id"] = str(uuid7())
        payload["guardians"] = [
            {"full_name": "Furaha Bisimwa", "relationship": "mother", "phone": "0971234567"}
        ]
    else:
        payload["family"] = str(family)
    return {"op_id": str(uuid7()), "type": "student.enroll", "payload": payload}


@pytest.fixture
def desk(api, school, head):
    """Une secrétaire qui encaisse aussi, sur son appareil enregistré."""
    from apps.finance.tests.test_payments import school_with_fees

    data = school_with_fees(school, head)
    user = MembershipFactory(school=school, roles=["secretary", "cashier"]).user
    client = api(user)
    return SimpleNamespace(data=data, user=user, client=client, device=remember(client).json())


def test_a_student_enrolled_offline_is_created_once_and_paid_at_once(school, desk):
    """Ouverture de caisse, inscription et paiement sur la 1re tranche choisie par l'appareil,
    le lot envoyé deux fois : un élève, une famille, une inscription, des frais dus aux
    identifiants de l'appareil, un paiement ; matricule et code famille donnés au serveur."""
    data, device = desk.data, desk.device
    with use_school(school):
        templates = list(
            InstallmentTemplate.objects.order_by("due_on").values_list("pk", flat=True)
        )
    session_id = uuid7()
    enroll = enroll_op(data["group"], charges=templates)
    first_charge = enroll["payload"]["charges"][1]  # la 1re tranche du minerval (15/10)
    pay = payment_op(
        {"enrollment": SimpleNamespace(pk=enroll["payload"]["enrollment_id"])},
        device,
        SimpleNamespace(pk=session_id),
        12000,
        allocations=[{"student_charge": first_charge["id"], "received_minor": 12000}],
    )
    batch = {"operations": [open_op(data["register"], session_id), enroll, pay]}

    first = desk.client.post(PUSH, batch).json()["results"]
    again = desk.client.post(PUSH, batch).json()["results"]
    assert [r["status"] for r in first + again] == ["applied"] * 3 + ["duplicate"] * 3
    result = first[1]["result"]
    with use_school(school):
        student = Student.objects.get(pk=enroll["payload"]["id"])
        enrollment = Enrollment.objects.get(student=student)
        charges = {str(c.pk) for c in StudentCharge.objects.filter(enrollment=enrollment)}
        payment = Payment.objects.get(enrollment=enrollment)
        assert Family.objects.filter(pk=enroll["payload"]["family_id"]).count() == 1
        assert str(payment.allocations.get().student_charge_id) == first_charge["id"]
        created = AuditLog.objects.filter(
            action=Action.STUDENTS_STUDENT_CREATED, entity_id=student.pk
        )
        enrolled = AuditLog.objects.filter(action=Action.STUDENTS_ENROLLED, entity_id=enrollment.pk)
        assert created.count() == enrolled.count() == 1
        assert created.get().device_id is not None
        code = student.family.code
    assert str(enrollment.pk) == enroll["payload"]["enrollment_id"]
    assert charges == {c["id"] for c in enroll["payload"]["charges"]}
    assert student.matricule and result["matricule"] == student.matricule
    assert len(code) == 8 and result["family_code"] == code
    assert result["possible_duplicates"] == []


def test_a_possible_duplicate_is_kept_and_signalled_never_merged(school, head, desk):
    """Même élève inscrit en ligne et sur l'appareil : l'inscription de l'appareil est gardée
    (l'élève a pu payer), le secrétariat est prévenu ; pas de nouvel avis pour un élève que
    l'appareil a déjà dit différent (« Ce sont deux élèves »)."""
    other = new_student(
        school,
        head,
        last_name="BISIMWA",
        middle_name="Mugisho",
        first_name="arsène",
        birth_date=BIRTH,
    )
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    ops = [enroll_op(desk.data["group"]), enroll_op(desk.data["group"], distinct_from=[other.pk])]

    results = desk.client.post(PUSH, {"operations": ops}).json()["results"]
    assert [r["status"] for r in results] == ["applied", "applied"]
    assert results[0]["result"]["possible_duplicates"] == [str(other.pk)]
    with use_school(school):
        assert Student.objects.filter(birth_date=BIRTH).count() == 3
        notices = Notification.objects.filter(
            kind=Notification.Kind.POSSIBLE_DUPLICATE, user=secretary
        )
        # Le second élève n'est signalé que pour le premier, inscrit par le même envoi ; l'auteur
        # de l'inscription n'est pas prévenu.
        assert sorted(notices.values_list("url", flat=True)) == sorted(
            f"/students/{op['payload']['id']}" for op in ops
        )
        assert not Notification.objects.filter(user=desk.user).exists()


def test_offline_enrollment_needs_the_right_and_stays_in_its_school(
    api, school, other_school, head, desk
):
    """Sans `students.edit` : refusée. Famille, classe ou identifiant d'élève d'une autre école :
    refusée, rien n'est écrit chez elle. Identifiant de frais déjà pris ailleurs : ignoré."""
    from apps.finance.tests.test_payments import school_with_fees

    beta = school_with_fees(other_school, head)
    stranger = new_student(other_school, head)
    with use_school(other_school):
        taken_charge = StudentCharge.objects.first()
        beta_family = stranger.family_id
    with use_school(school):
        template = InstallmentTemplate.objects.order_by("due_on").first()

    cashier = api(MembershipFactory(school=school, roles=["cashier"]).user)
    remember(cashier)
    denied = cashier.post(PUSH, {"operations": [enroll_op(desk.data["group"])]}).json()
    assert denied["results"][0]["error"]["code"] == "permission_denied"

    group = desk.data["group"]
    ops = [
        enroll_op(group, family=beta_family),
        enroll_op(beta["group"]),
        enroll_op(group, id=str(stranger.pk)),
        enroll_op(group, charges=[template.pk]),
    ]
    ops[3]["payload"]["charges"][0]["id"] = str(taken_charge.pk)
    results = desk.client.post(PUSH, {"operations": ops}).json()["results"]
    assert [r["status"] for r in results] == ["rejected"] * 3 + ["applied"]
    assert results[2]["error"]["code"] == "id_taken"
    with use_school(other_school):
        assert Student.objects.count() == 2  # l'élève de `school_with_fees` et l'étranger
        assert StudentCharge.objects.filter(pk=taken_charge.pk).count() == 1
    with use_school(school):
        mine = StudentCharge.objects.get(
            installment_template=template, enrollment__student_id=ops[3]["payload"]["id"]
        )
    assert mine.pk != taken_charge.pk


def test_the_device_gets_the_fee_rules_of_each_class_only_with_finance_rights(api, school, desk):
    """Barèmes de l'année avec les classes où chacun s'applique : l'appareil calcule les frais
    d'un élève inscrit sans réseau. Sans droit sur les finances : rien."""
    config = desk.client.get(SNAPSHOT).json()["config"]
    group = str(desk.data["group"].pk)
    rules = {
        rule["fee_type"]: rule for rule in config["fee_rules"] if group in rule["class_groups"]
    }
    assert sorted(len(rule["installments"]) for rule in rules.values()) == [1, 3]
    assert {i["amount_minor"] for r in rules.values() for i in r["installments"]} == {12000, 25000}

    secretary = api(MembershipFactory(school=school, roles=["secretary"]).user)
    remember(secretary)
    assert secretary.get(SNAPSHOT).json()["config"]["fee_rules"] is None
