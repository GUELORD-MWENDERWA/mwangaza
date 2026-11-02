"""Offres, contrats, conditions (CTR.1, ABO.1) : droits de la console, contrat immuable une fois
signé, avenant, modules donnés par le contrat, conditions acceptées une fois par version, isolation
entre écoles, journaux."""

import datetime

import pytest

from apps.accounts.models import User
from apps.audit.actions import Action, PlatformAction
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.billing import services
from apps.billing.models import Contract, LegalDocument
from apps.core.errors import BusinessError
from apps.core.tenancy import use_all_schools, use_school
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db
CONSOLE = "admin.localhost"
START, END = datetime.date(2026, 11, 1), datetime.date(2027, 7, 31)


def member(role: str) -> User:
    return UserFactory(is_platform_admin=True, platform_roles=[role])


@pytest.fixture
def finance():
    return member("finance")


@pytest.fixture
def essential(finance):
    return services.save_plan(
        actor=finance,
        code="essentiel",
        name="Essentiel",
        modules=["finance"],
        price_per_student=150,
        currency="USD",
        period="year",
    )


def test_plan_is_priced_in_whole_units_and_brings_its_dependencies(essential):
    assert essential.modules == ["students", "finance"]  # finance a besoin des élèves
    assert PlatformAuditLog.objects.filter(action=PlatformAction.PLAN_SAVED).count() == 1


def test_only_billing_roles_touch_plans(api, essential):
    body = {"code": "x", "name": "X", "price_per_student": 1, "currency": "USD", "period": "year"}
    support = api(member("support"), host=CONSOLE)
    assert support.post("/api/console/billing/plans/", body).status_code == 403
    assert (
        api(member("commercial"), host=CONSOLE)
        .post("/api/console/billing/plans/", body)
        .status_code
        == 403
    )
    assert (
        api(member("finance"), host=CONSOLE).post("/api/console/billing/plans/", body).status_code
        == 201
    )


def test_signing_makes_the_contract_final_and_gives_the_modules(finance, essential, school):
    draft = services.draft_contract(
        actor=finance, school=school, plan=essential, start_date=START, end_date=END
    )
    assert draft.number.startswith("CT-2026-") and draft.status == Contract.Status.DRAFT
    # Le prix est copié : changer l'offre ne réécrit pas le contrat.
    services.save_plan(actor=finance, plan=essential, price_per_student=999)
    with use_all_schools():
        draft.refresh_from_db()
    assert draft.price_per_student == 150

    with pytest.raises(BusinessError):  # signature sans signataire
        services.activate_contract(draft, actor=finance, signature="online")
    services.activate_contract(
        draft, actor=finance, signature="online", signer_name="Abbé Jean Mukendi"
    )
    school.refresh_from_db()
    assert school.modules == ["students", "finance"]
    with pytest.raises(BusinessError) as err:  # déjà signé : immuable
        services.activate_contract(draft, actor=finance, signature="online", signer_name="X")
    assert err.value.error.code == "contract_not_draft"
    with use_school(school):
        assert AuditLog.objects.filter(action=Action.CONTRACT_ACTIVATED).count() == 1
    assert PlatformAuditLog.objects.filter(action=PlatformAction.CONTRACT_ACTIVATED).exists()


def test_amendment_ends_the_previous_contract(finance, essential, school):
    first = services.draft_contract(
        actor=finance, school=school, plan=essential, start_date=START, end_date=END
    )
    services.activate_contract(first, actor=finance, signature="online", signer_name="A")
    other = services.draft_contract(
        actor=finance, school=school, plan=essential, start_date=START, end_date=END
    )
    with pytest.raises(BusinessError) as err:  # un seul contrat actif
        services.activate_contract(other, actor=finance, signature="online", signer_name="A")
    assert err.value.error.code == "contract_active_exists"

    with use_all_schools():
        first.refresh_from_db()
    amendment = services.amend_contract(first, actor=finance, price_per_student=120)
    services.activate_contract(amendment, actor=finance, signature="online", signer_name="A")
    with use_all_schools():
        first.refresh_from_db()
    assert first.status == Contract.Status.ENDED
    assert amendment.price_per_student == 120 and amendment.replaces_id == first.pk


def test_contracts_of_a_school_are_invisible_to_another(
    api, finance, essential, school, other_school
):
    services.draft_contract(
        actor=finance, school=school, plan=essential, start_date=START, end_date=END
    )
    services.draft_contract(
        actor=finance, school=other_school, plan=essential, start_date=START, end_date=END
    )
    with use_school(other_school):
        assert [c.school_id for c in Contract.objects.all()] == [other_school.pk]
    rows = api(finance, host=CONSOLE).get("/api/console/billing/contracts/?school=alpha").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert {r["school"] for r in rows} == {"alpha"}


def test_terms_are_accepted_once_per_version_by_the_school_head(
    api, finance, school, other_school, head, cashier, other_head
):
    v1 = services.publish_legal(
        actor=finance, kind="terms", title_fr="CGU", title_en="Terms", body_fr="a", body_en="a"
    )
    services.publish_legal(
        actor=finance, kind="register", title_fr="R", title_en="R", body_fr="a", body_en="a"
    )
    with use_school(school):
        assert [d.pk for d in services.pending_for(school)] == [v1.pk]

    assert api(cashier).post("/api/legal/accept/", {"document": str(v1.pk)}).status_code == 403
    admin = api(head)
    assert admin.get("/api/legal/pending/").json()[0]["version"] == 1
    for _ in range(2):  # rejouer ne double rien
        assert admin.post("/api/legal/accept/", {"document": str(v1.pk)}).status_code == 204
    with use_school(school):
        assert services.pending_for(school) == []
        assert AuditLog.objects.filter(action=Action.LEGAL_ACCEPTED).count() == 1
    # L'autre école n'a rien accepté.
    with use_school(other_school):
        assert [d.pk for d in services.pending_for(other_school)] == [v1.pk]

    v2 = services.publish_legal(
        actor=finance, kind="terms", title_fr="CGU", title_en="T", body_fr="b", body_en="b"
    )
    with use_school(school):
        assert [d.pk for d in services.pending_for(school)] == [v2.pk]
    assert v2.version == 2
    assert LegalDocument.objects.filter(kind="terms").count() == 2
