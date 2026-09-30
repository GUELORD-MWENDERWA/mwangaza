"""Clôture de caisse (3.8.2, F8) : isolation entre écoles, seul le caissier de la session la
clôture, attendu par devise (annulés exclus à l'heure de clôture), écart expliqué, plus
d'encaissement ensuite, clôture immuable et au journal ; clôtures vues par le comptable (3.8.3,
M16). Clôture et encaissements hors ligne, paiement arrivé après la clôture :
`apps/sync/tests/test_sync.py`."""

import io
from datetime import UTC, datetime

import openpyxl
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
CLOSINGS = "/api/cash-closings/"


@pytest.fixture
def alpha(school, head):
    return school_with_fees(school, head)


def counted(usd: int, cdf: int, note: str = "") -> dict:
    amounts = [{"currency": "USD", "amount_minor": usd}, {"currency": "CDF", "amount_minor": cdf}]
    return {"counted": amounts, **({"note": note} if note else {})}


def sheet(content: bytes) -> list[tuple]:
    return list(openpyxl.load_workbook(io.BytesIO(content)).active.iter_rows(values_only=True))


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
    # Le comptable de l'autre école : ni dans la liste, ni les chiffres, ni l'export.
    accountant = api(other_head, "beta.localhost")
    assert accountant.get(f"{CLOSINGS}{session.pk}/").status_code == 404
    assert accountant.get(CLOSINGS).json()["results"] == []
    summary = accountant.get(f"{CLOSINGS}summary/").json()
    assert (summary["sessions"], summary["unclosed"]) == (0, [])
    assert len(sheet(accountant.get(f"{CLOSINGS}export/").content)) == 1


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


def test_the_accountant_sees_each_session_its_difference_and_those_left_open(
    api, school, head, cashier, alpha, django_assert_max_num_queries
):
    """Caisse 1 : 120,00 $ et 25 000 FC attendus, 115,00 $ comptés (écart), puis rouverte
    aujourd'hui. Caisse 2 : ouverte en janvier 2025 par une autre caissière, jamais clôturée.
    Le comptable (`finance.view_reports`) lit tout, le caissier rien."""
    enrollment = alpha["enrollment"]
    pay(school, cashier, enrollment, 12000, "USD")
    first = pay(school, cashier, enrollment, 25000, "CDF").cash_session
    close = api(cashier).post(f"{SESSIONS}{first.pk}/close/", counted(11500, 25000, "Billet"))
    assert close.status_code == 200
    today = pay(school, cashier, enrollment, 1000, "USD").cash_session
    other = MembershipFactory(school=school, roles=["cashier"]).user
    with use_school(school):
        c2 = services.create_cash_register(actor=head, name="Caisse 2", code="C2")
    forgotten = pay(school, other, enrollment, 6000, "USD", code="C2").cash_session
    with use_school(school):
        january = datetime(2025, 1, 15, 7, 30, tzinfo=UTC)
        CashSession.objects.filter(pk=forgotten.pk).update(opened_at=january)
    accountant = api(head)

    for url in (CLOSINGS, f"{CLOSINGS}summary/", f"{CLOSINGS}{first.pk}/", f"{CLOSINGS}export/"):
        assert api(cashier).get(url).status_code == 403
    with django_assert_max_num_queries(12):
        rows = {row["id"]: row for row in accountant.get(CLOSINGS).json()["results"]}
    assert set(rows) == {str(first.pk), str(today.pk)}
    closed = rows[str(first.pk)]
    assert (closed["state"], closed["payments_count"], closed["late"]) == ("difference", 2, [])
    assert [tuple(line.values()) for line in closed["lines"]] == [
        ("USD", 12000, 11500, -500),
        ("CDF", 25000, 25000, 0),
    ]
    assert rows[str(today.pk)]["state"] == "open"
    assert rows[str(today.pk)]["lines"][0] == {
        "currency": "USD",
        "expected_minor": 1000,
        "counted_minor": None,
        "difference_minor": None,
    }
    old = accountant.get(f"{CLOSINGS}?month=2025-01").json()["results"]
    assert [(row["id"], row["state"]) for row in old] == [(str(forgotten.pk), "unclosed")]
    assert accountant.get(f"{CLOSINGS}?cash_register={c2.pk}").json()["results"] == []

    summary = accountant.get(f"{CLOSINGS}summary/").json()
    assert (summary["sessions"], summary["cash_registers"]) == (2, 1)
    assert summary["differences"] == [
        {"currency": "USD", "difference_minor": -500, "sessions": 1},
        {"currency": "CDF", "difference_minor": 0, "sessions": 0},
    ]
    assert [(item["id"], item["cash_register"]["code"]) for item in summary["unclosed"]] == [
        (str(forgotten.pk), "C2")
    ]
    detail = accountant.get(f"{CLOSINGS}{first.pk}/").json()
    assert (detail["state"], detail["closing"]["note"], detail["late_payments"]) == (
        "difference",
        "Billet",
        [],
    )
    _header, *lines = sheet(accountant.get(f"{CLOSINGS}export/").content)
    assert len(lines) == 2
    # Montants en nombres (5,00 $ d'écart), dans l'ordre de l'écran : le plus récent d'abord.
    assert -5 in lines[1] and 115 in lines[1] and 25000 in lines[1] and "Billet" in lines[1]
