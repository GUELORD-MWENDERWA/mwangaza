"""Dépenses (FIN.1) : isolation entre écoles, droits (saisir, valider jamais la sienne, annuler),
seuil de validation par devise, montants entiers, annulation sans effacement, justificatif privé,
audit, idempotence."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import expenses as services
from apps.finance.models import Expense, ExpenseCancellation, ImmutablePaymentError
from apps.finance.tests.test_api import entries
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

EXPENSES = "/api/expenses/"
CATEGORIES = "/api/expense-categories/"
SETTINGS = "/api/expense-settings/"


@pytest.fixture
def accountant(school):
    return MembershipFactory(school=school, roles=["accountant"]).user


@pytest.fixture
def category(school, head):
    with use_school(school):
        return services.create_category(actor=head, name="Atelier mécanique")


def body(category, **over):
    return {
        "category": str(category.pk),
        "beneficiary": "Quincaillerie Mapendo",
        "reason": "Pièces du banc d'essai",
        "amount_minor": 18500,
        "currency": "USD",
        "spent_on": "2026-10-19",
        "account": "bank",
        **over,
    }


def send(client, data):
    """Créer une dépense en formulaire (comme l'écran, qui envoie le justificatif)."""
    return client.client.post(EXPENSES, data, HTTP_HOST=client.host)


def photo(size=(40, 30)):
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, "JPEG")
    return SimpleUploadedFile("facture.jpg", out.getvalue(), content_type="image/jpeg")


def test_a_school_neither_reads_nor_touches_the_expenses_of_another(
    api, school, other_school, accountant, head, category, other_head
):
    expense = send(api(accountant), body(category, voucher=photo())).json()
    other = api(other_head, "beta.localhost")

    assert other.get(EXPENSES).json()["results"] == []
    assert other.get(f"{EXPENSES}summary/").json() == {"by_currency": [], "cancelled": []}
    assert other.get(CATEGORIES).json() == []
    for action in ["", "voucher/"]:
        assert other.get(f"{EXPENSES}{expense['id']}/{action}").status_code == 404
    for action in ["approve/", "reject/", "cancel/"]:
        assert other.post(f"{EXPENSES}{expense['id']}/{action}", {"reason": "x"}).status_code == 404
    # La catégorie d'une autre école est introuvable.
    beta = MembershipFactory(school=other_school, roles=["accountant"]).user
    refused = api(beta, "beta.localhost").post(EXPENSES, body(category))
    assert refused.status_code == 404
    with use_school(school):
        assert Expense.objects.count() == 1


def test_rights_record_approve_cancel(api, school, head, accountant, cashier, category):
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    assert api(cashier).post(EXPENSES, body(category)).status_code == 403
    assert api(secretary).get(EXPENSES).status_code == 403
    assert api(accountant).get(EXPENSES).status_code == 200
    assert api(head).post(EXPENSES, body(category)).status_code == 403  # lire, pas saisir

    big = api(accountant).post(EXPENSES, body(category, amount_minor=42000)).json()
    assert big["status"] == "pending"
    # Le comptable ne valide ni ne rejette ni n'annule : ce n'est pas son droit.
    for action in ["approve/", "reject/", "cancel/"]:
        assert (
            api(accountant).post(f"{EXPENSES}{big['id']}/{action}", {"reason": "x"}).status_code
            == 403
        )
    # Sans le droit de valider, il ne se valide pas lui-même ; avec, jamais la sienne.
    with use_school(school):
        boss = MembershipFactory(school=school, roles=["head"]).user
    approved = api(boss).post(f"{EXPENSES}{big['id']}/approve/")
    assert approved.status_code == 200 and approved.json()["status"] == "paid"
    assert api(boss).post(f"{EXPENSES}{big['id']}/approve/").json()["code"] == "expense_decided"


def test_nobody_approves_their_own_expense(api, school, category):
    """Quelqu'un qui peut saisir et valider ne valide pas ce qu'il a saisi."""
    both = MembershipFactory(school=school, roles=["head", "accountant"]).user
    pending = api(both).post(EXPENSES, body(category, amount_minor=42000)).json()
    refused = api(both).post(f"{EXPENSES}{pending['id']}/approve/")
    assert refused.status_code == 403 and refused.json()["code"] == "own_expense"


def test_threshold_is_per_currency_and_in_whole_minor_units(
    api, school, cashier, accountant, category
):
    client = api(accountant)
    # 200,00 $ exactement : sous le seuil (« au-dessus » seulement) ; 200,01 $ : validation.
    assert send(client, body(category, amount_minor=20000)).json()["status"] == "paid"
    assert send(client, body(category, amount_minor=20001)).json()["status"] == "pending"
    # Les francs ont leur propre seuil, jamais converti : 500 000 FC.
    assert (
        send(client, body(category, currency="CDF", amount_minor=500000)).json()["status"] == "paid"
    )
    assert (
        send(client, body(category, currency="CDF", amount_minor=500001)).json()["status"]
        == "pending"
    )
    # Montant décimal ou nul : refusé.
    assert send(client, body(category, amount_minor="10.5")).status_code == 400
    assert send(client, body(category, amount_minor=0)).status_code == 400
    # Le seuil se règle avec le droit des frais (pas la caissière), avec une entrée d'audit.
    assert (
        api(cashier).put(SETTINGS, {"usd_threshold_minor": 1, "cdf_threshold_minor": 1}).status_code
        == 403
    )
    changed = client.put(SETTINGS, {"usd_threshold_minor": 100, "cdf_threshold_minor": 500000})
    assert changed.json() == {"usd_threshold_minor": 100, "cdf_threshold_minor": 500000}
    assert client.post(EXPENSES, body(category, amount_minor=101)).json()["status"] == "pending"
    assert len(entries(school, Action.FINANCE_EXPENSE_SETTINGS_UPDATED)) == 1


def test_cash_waits_for_the_cash_desk_and_other_accounts_are_paid_at_once(
    api, accountant, category
):
    client = api(accountant)
    assert send(client, body(category, account="cash")).json()["status"] == "approved"
    paid = send(client, body(category, account="mobile_money")).json()
    assert paid["status"] == "paid" and paid["paid_at"]


def test_cancelling_adds_a_linked_record_and_never_erases(api, school, accountant, category):
    with use_school(school):
        boss = MembershipFactory(school=school, roles=["head"]).user
    expense = api(accountant).post(EXPENSES, body(category)).json()
    assert (
        api(boss).post(f"{EXPENSES}{expense['id']}/cancel/", {}).status_code == 400
    )  # motif requis
    done = api(boss).post(f"{EXPENSES}{expense['id']}/cancel/", {"reason": "Saisie en double"})
    assert done.json()["cancelled"] is True
    assert (
        api(boss).post(f"{EXPENSES}{expense['id']}/cancel/", {"reason": "encore"}).json()["code"]
        == "expense_cancelled"
    )

    summary = api(accountant).get(f"{EXPENSES}summary/").json()
    assert summary["by_currency"] == []  # une dépense annulée ne compte plus
    assert summary["cancelled"] == [{"currency": "USD", "total": 18500, "count": 1}]
    with use_school(school):
        item = Expense.objects.get()
        with pytest.raises(ImmutablePaymentError):
            item.delete()
        cancellation = ExpenseCancellation.objects.get()
        cancellation.reason = "autre"
        with pytest.raises(ImmutablePaymentError):
            cancellation.save()
        with pytest.raises(ImmutablePaymentError):
            ExpenseCancellation.objects.all().delete()
        assert len(entries(school, Action.FINANCE_EXPENSE_CANCELLED)) == 1


def test_replaying_the_same_expense_gives_the_same_one_and_audits_once(
    api, school, accountant, category
):
    sent = body(category, id="0197c1b2-0000-7000-8000-000000000001")
    first = api(accountant).post(EXPENSES, sent)
    again = api(accountant).post(EXPENSES, sent)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    with use_school(school):
        assert Expense.objects.count() == 1
        assert len(entries(school, Action.FINANCE_EXPENSE_RECORDED)) == 1


def test_voucher_is_a_clean_image_or_a_pdf_and_only_staff_read_it(
    api, school, accountant, category
):
    client = api(accountant)
    made = send(client, body(category, voucher=photo())).json()
    assert made["has_voucher"] is True
    served = client.get(f"{EXPENSES}{made['id']}/voucher/")
    assert served.status_code == 200 and served["Cache-Control"].startswith("private")
    assert served["Content-Type"] == "image/jpeg"

    pdf = SimpleUploadedFile("facture.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    assert send(client, body(category, voucher=pdf)).status_code == 201
    fake = SimpleUploadedFile(
        "facture.pdf", b"<script>alert(1)</script>", content_type="application/pdf"
    )
    assert send(client, body(category, voucher=fake)).status_code == 400
    assert api(accountant).get(f"{EXPENSES}{made['id']}/voucher/").status_code == 200
    # Pas de justificatif : 404, pas d'erreur serveur.
    nothing = send(client, body(category)).json()
    assert client.get(f"{EXPENSES}{nothing['id']}/voucher/").status_code == 404


def test_numbers_follow_each_other_and_categories_are_unique(
    api, school, head, accountant, category
):
    client = api(accountant)
    numbers = [send(client, body(category)).json()["number"] for _ in range(2)]
    assert numbers == ["DEP-26-0001", "DEP-26-0002"]
    with use_school(school):
        accountant_with_fees = MembershipFactory(school=school, roles=["accountant"]).user
    assert (
        api(accountant_with_fees).post(CATEGORIES, {"name": "atelier MÉCANIQUE"}).json()["code"]
        == "expense_category_name_taken"
    )
    # Une catégorie mise de côté n'accepte plus de dépense.
    assert (
        api(accountant_with_fees)
        .patch(f"{CATEGORIES}{category.pk}/", {"is_active": False})
        .status_code
        == 200
    )
    assert send(client, body(category)).json()["code"] == "expense_category_inactive"
