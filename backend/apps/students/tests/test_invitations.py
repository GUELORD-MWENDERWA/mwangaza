"""Invitation des familles au portail (H7) : état du portail de chaque famille, familles activées
par classe, lettres et message avec le code famille, notés dans le journal ; jamais dans une
autre école."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.students.documents import HIDDEN_CODE
from apps.students.models import Enrollment, Family, Guardian
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

FAMILIES = "/api/families/"


def _families(school, head, group):
    """Cinq familles de la classe : une à inviter, une activée, une sans numéro, une avec un
    nouveau code périmé, une dont l'enfant a quitté l'école."""
    names = ("Amani", "Bahati", "Kambale", "Masika", "Paluku")
    students = {name: enrolled(school, head, group, last_name=name) for name in names}
    family = {name: student.family_id for name, student in students.items()}
    with use_school(school):
        Family.objects.filter(pk=family["Bahati"]).update(
            primary_user=UserFactory(), activated_at=timezone.now()
        )
        Guardian.objects.filter(family=family["Kambale"]).update(phone="")
        Family.objects.filter(pk=family["Masika"]).update(
            code_expires_at=timezone.now() - timedelta(days=1)
        )
        Enrollment.objects.filter(student=students["Paluku"]).update(
            status=Enrollment.Status.TRANSFERRED
        )
    return students, family


def test_portal_status_of_each_family_and_activation_by_class(api, school, head, alpha):
    _students, family = _families(school, head, alpha["group"])
    client = api(head)

    summary = client.get(f"{FAMILIES}activation/").json()
    [group] = [row for row in summary["classes"] if row["id"] == str(alpha["group"].pk)]
    # L'élève parti ne compte plus ; seule la famille « pas encore activé » reçoit une lettre.
    assert (group["families"], group["activated"], group["invitable"]) == (4, 1, 1)
    assert (summary["families"], summary["activated"]) == (4, 1)

    listed = client.get(FAMILIES, class_group=alpha["group"].pk).json()["results"]
    assert {row["id"]: row["portal_status"] for row in listed} == {
        str(family["Amani"]): "pending",
        str(family["Bahati"]): "activated",
        str(family["Kambale"]): "no_phone",
        str(family["Masika"]): "code_expired",
    }
    pending = client.get(FAMILIES, class_group=alpha["group"].pk, portal="not_activated").json()
    assert len(pending["results"]) == 3


def test_letters_and_message_give_the_code_only_to_invitable_families_and_log_it(
    api, school, head, cashier, other_head, alpha, beta
):
    students, family = _families(school, head, alpha["group"])
    with use_school(school):
        code = Family.objects.get(pk=family["Amani"]).code
    printed = f"{code[:4]}-{code[4:]}"
    letters = f"{FAMILIES}letters/"
    client = api(head)

    preview = client.get(letters, class_group=alpha["group"].pk, output="html").content.decode()
    assert HIDDEN_CODE in preview and printed not in preview
    assert students["Amani"].last_name.upper() in preview.upper()
    assert all(students[name].full_name not in preview for name in ("Bahati", "Kambale", "Masika"))
    pdf = client.get(letters, class_group=alpha["group"].pk)
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    refused = client.get(f"{FAMILIES}{family['Bahati']}/letter/", output="html")
    assert refused.json()["code"] == "not_invitable"

    message = client.post(f"{FAMILIES}{family['Amani']}/invitation-message/").json()
    assert f"/activate#{code}" in message["text"] and printed in message["text"]
    assert message["phone"] == "+243971234567"
    with use_school(school):
        logged = sorted(
            AuditLog.objects.filter(entity_id=family["Amani"]).values_list("action", flat=True)
        )
    # Aperçu : rien ; PDF et message : une entrée chacun.
    assert logged[-2:] == sorted(
        [Action.STUDENTS_FAMILY_INVITATION_PRINTED, Action.STUDENTS_FAMILY_INVITATION_SHARED]
    )

    # Caissier (`students.view` sans `students.edit`) : voit l'état, ne reçoit aucun code.
    assert api(cashier).get(f"{FAMILIES}activation/").status_code == 200
    assert api(cashier).get(letters, class_group=alpha["group"].pk).status_code == 403
    assert api(cashier).get(f"{FAMILIES}{family['Amani']}/letter/").status_code == 403
    assert api(cashier).post(f"{FAMILIES}{family['Amani']}/invitation-message/").status_code == 403
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get(f"{FAMILIES}activation/").status_code == 403

    # Autre école : ni la classe, ni la famille, ni ses chiffres.
    other = api(other_head, host="beta.localhost")
    assert other.get(letters, class_group=alpha["group"].pk).status_code == 400
    assert other.get(FAMILIES, class_group=alpha["group"].pk).status_code == 400
    assert other.get(f"{FAMILIES}{family['Amani']}/letter/").status_code == 404
    assert other.post(f"{FAMILIES}{family['Amani']}/invitation-message/").status_code == 404
    other_summary = other.get(f"{FAMILIES}activation/").json()
    assert other_summary["families"] == 0
    assert str(alpha["group"].pk) not in {row["id"] for row in other_summary["classes"]}
