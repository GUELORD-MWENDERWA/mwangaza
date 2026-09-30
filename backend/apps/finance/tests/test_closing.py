"""Clôture de caisse (3.8.2, F8) : isolation entre écoles, seul le caissier de la session la
clôture, attendu par devise (annulés exclus à l'heure de clôture), écart expliqué, plus
d'encaissement ensuite, clôture immuable et au journal. Clôture et encaissements hors ligne :
`apps/sync/tests/test_sync.py`."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import CashClosing, CashSession, ImmutablePaymentError
from apps.finance.tests.test_api import entries, field_code
from apps.finance.tests.test_payments import body, pay, school_with_fees
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SESSIONS = "/api/cash-sessions/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def counted(usd: int, cdf: int, note: str = "") -> dict:
    amounts = [{"currency": "USD", "amount_minor": usd}, {"currency": "CDF", "amount_minor": cdf}]
    return {"counted": amounts, **({"note": note} if note else {})}


def test_a_school_neither_reads_nor_closes_the_sessions_of_another(
    api, school, other_school, cashier, other_head, alpha
):
    session = pay(school, cashier, alpha["enrollment"], 12000, "USD").cash_session
    school_with_fees(other_school, other_head)
    beta_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    other = api(beta_cashier, "beta.localhost")

    assert other.get(f"{SESSIONS}{session.pk}/closing/").status_code == 404
    assert other.post(f"{SESSIONS}{session.pk}/close/", counted(12000, 0)).status_code == 404
    with use_school(school):
        assert CashSession.objects.get().closed_at is None


def test_only_the_cashier_of_the_session_closes_it(api, school, head, cashier, alpha):
    session = pay(school, cashier, alpha["enrollment"], 12000, "USD").cash_session
    other_cashier = MembershipFactory(school=school, roles=["cashier"]).user
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    url = f"{SESSIONS}{session.pk}/close/"

    assert api(secretary).post(url, counted(12000, 0)).status_code == 403
    # Le préfet lit les rapports mais n'encaisse pas : il ne clôture pas.
    assert api(head).post(url, counted(12000, 0)).status_code == 403
    assert api(other_cashier).post(url, counted(12000, 0)).status_code == 404
    assert api(other_cashier).get(f"{SESSIONS}{session.pk}/closing/").status_code == 404
    with use_school(school), pytest.raises(services.BusinessError) as refused:
        services.close_cash_session(session, actor=other_cashier, counted={"USD": 12000})
    assert refused.value.error.code == "not_your_session"


def test_closing_freezes_expected_counted_and_difference_per_currency_and_stops_collecting(
    api, school, head, cashier, alpha
):
    """120,00 $ et 25 000 FC encaissés, 60,00 $ encaissés puis annulés : 120,00 $ et 25 000 FC
    attendus. 115,00 $ comptés : l'écart de - 5,00 $ doit être expliqué."""
    enrollment = alpha["enrollment"]
    pay(school, cashier, enrollment, 12000, "USD")
    pay(school, cashier, enrollment, 25000, "CDF")
    wrong = pay(school, cashier, enrollment, 6000, "USD")
    with use_school(school):
        request, _new = services.request_cancellation(wrong, actor=cashier, reason="Homonyme")
        services.approve_cancellation(request, actor=head)
        session = CashSession.objects.get()
    as_cashier = api(cashier)
    url = f"{SESSIONS}{session.pk}/close/"

    summary = as_cashier.get(f"{SESSIONS}{session.pk}/closing/").json()
    expected = {(c["currency"], c["expected_minor"], c["count"]) for c in summary["currencies"]}
    assert expected == {("USD", 12000, 1), ("CDF", 25000, 1)}
    fees = {(f["fee_type"], f["currency"], f["amount_minor"]) for f in summary["fee_types"]}
    assert fees == {("Minerval", "USD", 12000), ("Fonctionnement", "CDF", 25000)}
    assert (summary["payments_count"], summary["cancelled"][0]["amount_minor"]) == (3, 6000)
    assert summary["closing"] is None

    assert field_code(as_cashier.post(url, counted(11500, 25000)), "note") == "note_required"
    only_usd = {"counted": [{"currency": "USD", "amount_minor": 12000}]}
    assert field_code(as_cashier.post(url, only_usd), "counted") == "counted_currencies"
    closed = as_cashier.post(url, counted(11500, 25000, "Billet de 5 $ déchiré rendu au parent"))

    assert closed.status_code == 200, closed.content
    lines = {
        (line["currency"], line["expected_minor"], line["counted_minor"], line["difference_minor"])
        for line in closed.json()["closing"]["lines"]
    }
    assert lines == {("USD", 12000, 11500, -500), ("CDF", 25000, 25000, 0)}
    assert as_cashier.get(f"{SESSIONS}current/").json()["session"] is None
    refused = as_cashier.post("/api/payments/", body(enrollment, 1000, "USD"))
    assert refused.json()["code"] == "no_open_session"
    assert as_cashier.post(url, counted(11500, 25000, "Encore")).json()["code"] == "session_closed"
    [audited] = entries(school, Action.FINANCE_CASH_SESSION_CLOSED)
    assert audited.after["amounts"][0] == {
        "currency": "USD",
        "expected_minor": 12000,
        "counted_minor": 11500,
        "difference_minor": -500,
    }
    assert audited.after["note"] == "Billet de 5 $ déchiré rendu au parent"


def test_a_closing_is_never_changed_or_deleted(api, school, cashier, alpha):
    session = pay(school, cashier, alpha["enrollment"], 12000, "USD").cash_session
    assert api(cashier).post(f"{SESSIONS}{session.pk}/close/", counted(12000, 0)).status_code == 200
    with use_school(school):
        closing = CashClosing.objects.get(currency="USD")
        with pytest.raises(ImmutablePaymentError):
            closing.save()
        with pytest.raises(ImmutablePaymentError):
            CashClosing.objects.update(counted_minor=0)
    for sql in (
        "UPDATE finance_cashclosing SET counted_minor = 0",
        "DELETE FROM finance_cashclosing",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql)
    assert CashClosing.all_schools.get(pk=closing.pk).counted_minor == 12000
