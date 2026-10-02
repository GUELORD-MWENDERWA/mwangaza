"""Accueil du portail (H2) : les familles reliées au compte, une par école, avec la situation de
chaque enfant ; « Ajouter un enfant d'une autre école » ; « Suspendre l'accès » de la fiche
famille."""

from apps.core.tenancy import use_school
from apps.finance.tests.test_balance import at
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.portal.tests.test_access import (
    actions,
    activate,
    new_family,
    portal,
    post,
    reloaded,
)
from apps.schools.models import School
from apps.students import services as students
from apps.students.models import Family
from tests.factories import MembershipFactory, UserFactory

FAMILIES = "/api/portal/families/"


def family_of(school, enrollment) -> Family:
    with use_school(school):
        return enrollment.student.family


def link(client, code):
    return post(client, "families/link/", code=code)


def test_the_portal_shows_the_accounts_families_only_each_with_its_schools_balance(
    school, other_school, head, other_head, cashier, monkeypatch
):
    alpha = school_with_fees(school, head)
    # Le même tuteur (même numéro) a un enfant dans l'autre école : rien sans son code.
    beta = school_with_fees(other_school, other_head)
    client = portal()
    activate(client, family_of(school, alpha["enrollment"]).code)
    stranger = portal()
    activate(stranger, new_family(school, head, phone="+243990000001").code, phone="0990000001")
    at(monkeypatch, "2026-10-20")
    pay(school, cashier, alpha["enrollment"], 5000, "USD")

    [family] = client.get(FAMILIES).json()

    assert family["school_name"] == school.name and family["status"] == "active"
    [child] = family["children"]
    assert child["full_name"] == "Kasereka Jean" and child["class_name"] == "3e Électricité A"
    # Minerval 3 x 120,00 $ (1re tranche au 15/10), fonctionnement 25 000 FC au 30/09 : par
    # devise, jamais additionnés.
    assert [
        (c["currency"], c["total_minor"], c["paid_minor"], c["overdue_minor"])
        for c in child["balance"]["currencies"]
    ] == [("USD", 36000, 5000, 7000), ("CDF", 25000, 0, 25000)]
    assert child["balance"]["situation"] == "partial"
    assert child["first_overdue"] == "Fonctionnement"
    last = child["last_payment"]
    assert (last["received_amount_minor"], last["received_currency"]) == (5000, "USD")
    assert [f["children"] for f in stranger.get(FAMILIES).json()] == [[]]

    assert link(client, family_of(other_school, beta["enrollment"]).code).status_code == 200
    assert [f["school_name"] for f in client.get(FAMILIES).json()] == [
        school.name,
        other_school.name,
    ]
    assert portal().get(FAMILIES).status_code == 403
    assert portal("alpha.localhost").get(FAMILIES).status_code == 404


def test_adding_another_school_needs_its_code_and_the_accounts_phone(
    school, other_school, head, other_head
):
    client = portal()
    account = activate(client, new_family(school, head).code).json()
    other_phone = new_family(other_school, other_head, phone="+243990000001")
    taken = new_family(other_school, other_head)
    Family.all_schools.filter(pk=taken.pk).update(primary_user=UserFactory())

    refused = [link(client, code) for code in ("ABCD-EFGH", other_phone.code, taken.code)]

    # Code inconnu, autre numéro, famille d'un autre compte : même réponse, rien à deviner.
    assert {(r.status_code, r.json()["code"]) for r in refused} == {(400, "invalid_link_code")}
    assert reloaded(other_phone).primary_user is None
    assert reloaded(taken).primary_user.phone != account["phone"]

    added = new_family(other_school, other_head)
    assert link(client, added.code).status_code == 200
    assert link(client, added.code).status_code == 200
    assert str(reloaded(added).primary_user.pk) == account["id"]
    [entry] = actions(other_school, "portal.activated")
    assert entry.entity_id == added.pk


def test_suspending_portal_access_needs_students_edit_stays_in_its_school_and_is_audited(
    api, school, head, other_head
):
    family = new_family(school, head)
    path = f"/api/families/{family.pk}/portal-access/"
    teacher = MembershipFactory(school=school, roles=["teacher"]).user

    assert api(teacher).post(path, {"suspended": True}).status_code == 403
    assert api(other_head, host="beta.localhost").post(path, {"suspended": True}).status_code == 404
    assert reloaded(family).portal_suspended_at is None

    assert api(head).post(path, {"suspended": True}).json()["portal_suspended_at"] is not None
    assert api(head).post(path, {"suspended": False}).json()["portal_suspended_at"] is None
    [suspended] = actions(school, "students.portal_suspended")
    [restored] = actions(school, "students.portal_restored")
    assert suspended.actor == restored.actor == head and suspended.entity_id == family.pk


def test_a_suspended_family_or_school_shows_no_child_data_and_its_code_opens_nothing(
    school, other_school, head, other_head
):
    alpha = school_with_fees(school, head)
    beta = school_with_fees(other_school, other_head)
    mine = family_of(school, alpha["enrollment"])
    client = portal()
    activate(client, mine.code)
    link(client, family_of(other_school, beta["enrollment"]).code)
    with use_school(school):
        students.set_portal_access(mine, actor=head, suspended=True)
        waiting = new_family(school, head, phone="+243990000001")
        students.set_portal_access(waiting, actor=head, suspended=True)
    School.objects.filter(pk=other_school.pk).update(status=School.Status.SUSPENDED)

    assert [(f["status"], f["children"]) for f in client.get(FAMILIES).json()] == [
        ("suspended", []),
        ("school_unavailable", []),
    ]
    refused = activate(portal(), waiting.code, phone="0990000001")
    assert (refused.status_code, refused.json()["code"]) == (403, "portal_suspended")
    assert reloaded(waiting).primary_user is None
