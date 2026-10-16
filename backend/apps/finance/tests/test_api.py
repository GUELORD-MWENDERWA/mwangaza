"""Frais, barèmes et taux de l'année (E1, E2, E5, M5, C1) : isolation entre écoles, droits,
règles de l'argent, journal, taux immuable."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import ExchangeRate, FeeRule, FeeType, ImmutableRateError
from apps.finance.services import Installment, Scope
from apps.schools.models import AcademicYear, ClassGroup
from apps.schools.tests.test_organisation_api import structure
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

TYPES = "/api/fee-types/"
RULES = "/api/fee-rules/"
RATES = "/api/exchange-rates/"
YEARS = "/api/academic-years/"
SETTINGS = "/api/school/settings/"

THREE_TRANCHES = [
    {"label": "1re tranche", "amount_minor": 12000, "due_on": "2026-10-15"},
    {"label": "2e tranche", "amount_minor": 12000, "due_on": "2027-01-15"},
    {"label": "3e tranche", "amount_minor": 12000, "due_on": "2027-04-15"},
]


def setup(school, actor) -> dict:
    """Organisation de `structure`, un type « Minerval » et son barème du niveau 3e en USD."""
    data = structure(school, actor)
    with use_school(school):
        fee_type = services.create_fee_type(actor=actor, name="Minerval", category="tuition")
        rule = services.create_fee_rule(
            actor=actor,
            academic_year=data["year"],
            fee_type=fee_type,
            currency="USD",
            total_amount_minor=36000,
            schedule_kind="installments",
            installments=[
                Installment(i["label"], i["amount_minor"], date.fromisoformat(i["due_on"]))
                for i in THREE_TRANCHES
            ],
            scope=Scope(level=data["level"]),
        )
    return {**data, "fee_type": fee_type, "rule": rule}


@pytest.fixture
def alpha(school, head):
    return setup(school, head)


@pytest.fixture
def beta(other_school, other_head):
    return setup(other_school, other_head)


def entries(school, action: str) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action).order_by("created_at"))


def rule_body(alpha, **changes) -> dict:
    return {
        "academic_year": str(alpha["year"].pk),
        "fee_type": str(alpha["fee_type"].pk),
        "level": str(alpha["other_level"].pk),
        "currency": "USD",
        "total_amount_minor": 36000,
        "schedule_kind": "installments",
        "installments": THREE_TRANCHES,
        **changes,
    }


def field_code(response, field: str) -> str:
    assert response.status_code == 400, response.content
    return response.json()["fields"][field][0]["code"]


# Isolation et droits


def test_a_school_neither_reads_nor_changes_the_fees_of_another(api, alpha, beta, other_head):
    client = api(other_head, host="beta.localhost")

    assert [t["id"] for t in client.get(TYPES).json()] == [str(beta["fee_type"].pk)]
    assert [r["id"] for r in client.get(RULES).json()] == [str(beta["rule"].pk)]
    assert client.get(f"{TYPES}{alpha['fee_type'].pk}/").status_code == 404
    assert client.patch(f"{TYPES}{alpha['fee_type'].pk}/", {"name": "X"}).status_code == 404
    assert client.put(f"{RULES}{alpha['rule'].pk}/", rule_body(alpha)).status_code == 404
    assert client.delete(f"{RULES}{alpha['rule'].pk}/").status_code == 404
    # Ni l'année, ni le type, ni le niveau d'une autre école dans une saisie.
    response = client.post(RULES, rule_body(alpha))
    assert set(response.json()["fields"]) == {"academic_year", "fee_type", "level"}
    assert client.get(RULES, academic_year=alpha["year"].pk).status_code == 400
    response = client.post(RATES, {"academic_year": str(alpha["year"].pk), "rate": "2850"})
    assert response.status_code == 400
    with use_school(alpha["year"].school):
        assert FeeRule.objects.count() == 1
        assert not ExchangeRate.objects.exists()


def test_fees_need_a_finance_permission(api, alpha, cashier, school):
    secretary = MembershipFactory(school=school, roles=["secretary"]).user
    for user in (cashier, secretary):
        client = api(user)
        assert client.get(TYPES).status_code == 403
        assert client.get(RULES).status_code == 403
        assert client.post(TYPES, {"name": "Cantine", "category": "canteen"}).status_code == 403
        rate = {"academic_year": str(alpha["year"].pk), "rate": "2850"}
        assert client.post(RATES, rate).status_code == 403


def test_a_school_role_with_only_the_rate_reads_the_fees_and_sets_the_rate(api, alpha, school):
    with use_school(school):
        role = Role.objects.create(name="Trésorier", permissions=["finance.set_exchange_rate"])
    client = api(MembershipFactory(school=school, roles=[role]).user)

    for url in (TYPES, RULES, YEARS, "/api/levels/", "/api/tracks/", "/api/class-groups/"):
        assert client.get(url).status_code == 200, url
    assert client.post(TYPES, {"name": "Cantine", "category": "canteen"}).status_code == 403
    assert client.delete(f"{RULES}{alpha['rule'].pk}/").status_code == 403
    rate = {"academic_year": str(alpha["year"].pk), "rate": "2850"}
    assert client.post(RATES, rate).status_code == 201


# Types de frais (E1)


def test_fee_type_names_are_unique_and_a_used_type_is_deactivated(api, alpha, head, school):
    client = api(head)

    response = client.post(TYPES, {"name": "Frais d'atelier", "category": "custom"})
    assert response.status_code == 201
    assert client.post(TYPES, {"name": "MINERVAL", "category": "tuition"}).json()["code"] == (
        "fee_type_name_taken"
    )
    assert client.delete(f"{TYPES}{alpha['fee_type'].pk}/").json()["code"] == "fee_type_in_use"
    response = client.patch(f"{TYPES}{alpha['fee_type'].pk}/", {"is_active": False})
    assert response.json()["is_active"] is False
    assert client.delete(f"{TYPES}{response.json()['id']}/").status_code == 409
    [created] = entries(school, "finance.fee_type_created")[1:]
    assert created.after == {
        "name": "Frais d'atelier",
        "category": "custom",
        "funds_teacher_bonus": False,
        "accounting_code": "",
        "is_active": True,
    }
    [updated] = entries(school, "finance.fee_type_updated")
    assert (updated.before, updated.after) == ({"is_active": True}, {"is_active": False})


# Barèmes (E2) : argent


@pytest.mark.parametrize(
    ("changes", "field", "code"),
    [
        # Somme des tranches différente du total : 350,00 $ pour 360,00 $.
        (
            {"installments": [{**THREE_TRANCHES[0], "amount_minor": 11000}, *THREE_TRANCHES[1:]]},
            "installments",
            "installments_total_mismatch",
        ),
        # Montant à virgule : jamais de décimale dans la plus petite unité.
        ({"total_amount_minor": 36000.5}, "total_amount_minor", "invalid"),
        ({"schedule_kind": "single"}, "installments", "single_needs_one"),
        ({"installments": []}, "installments", "no_installment"),
        ({"track": "TRACK"}, "scope", "scopes"),
    ],
)
def test_a_wrong_fee_rule_is_refused_and_nothing_is_written(
    api, alpha, head, school, changes, field, code
):
    if changes.get("track") == "TRACK":
        changes["track"] = str(alpha["track"].pk)

    response = api(head).post(RULES, rule_body(alpha, **changes))

    assert field_code(response, field) == code
    with use_school(school):
        assert FeeRule.objects.count() == 1
    assert len(entries(school, "finance.fee_rule_created")) == 1


def test_the_currency_of_a_fee_rule_is_one_of_the_school(api, alpha, head, school):
    school.enabled_currencies, school.default_currency = ["USD"], "USD"
    school.save()

    response = api(head).post(RULES, rule_body(alpha, currency="CDF", total_amount_minor=1026000))

    assert field_code(response, "currency") == "currency_not_enabled"


def test_a_fee_rule_is_updated_whole_with_stable_installments(api, alpha, head, school):
    client = api(head)
    url = f"{RULES}{alpha['rule'].pk}/"
    first_id = client.get(url).json()["installments"][0]["id"]
    two_tranches = [
        {"label": "1re tranche", "amount_minor": 20000, "due_on": "2026-10-15"},
        {"label": "2e tranche", "amount_minor": 19000, "due_on": "2027-02-15"},
    ]
    body = rule_body(alpha, level=str(alpha["level"].pk), total_amount_minor=39000)

    response = client.put(url, {**body, "installments": two_tranches})

    assert response.status_code == 200, response.content
    installments = response.json()["installments"]
    assert [(i["amount_minor"], i["order"]) for i in installments] == [(20000, 0), (19000, 1)]
    assert installments[0]["id"] == first_id
    [updated] = entries(school, "finance.fee_rule_updated")
    assert updated.before["total_amount_minor"] == 36000
    assert updated.after["total_amount_minor"] == 39000
    assert len(updated.after["installments"]) == 2
    assert updated.actor == head
    # Rien de changé : pas d'entrée de plus.
    client.put(url, {**body, "installments": two_tranches})
    assert len(entries(school, "finance.fee_rule_updated")) == 1


def test_one_fee_rule_per_fee_type_and_scope_in_a_year(api, alpha, head):
    client = api(head)

    assert client.post(RULES, rule_body(alpha)).status_code == 201
    assert client.post(RULES, rule_body(alpha)).json()["code"] == "fee_rule_exists"
    response = client.post(RULES, rule_body(alpha, level=None, class_group=str(alpha["group"].pk)))
    assert response.status_code == 201
    assert response.json()["scope_name"] == "3E ÉLECTRICITÉ A"


# Taux de l'année (E5)


def test_the_rate_is_corrected_with_a_reason_and_keeps_its_history(api, alpha, head, school):
    client = api(head)
    year = str(alpha["year"].pk)

    assert client.post(RATES, {"academic_year": year, "rate": "2850"}).status_code == 201
    response = client.post(RATES, {"academic_year": year, "rate": "2875.5"})
    assert field_code(response, "reason") == "reason_required"
    response = client.post(RATES, {"academic_year": year, "rate": "2850", "reason": "Erreur"})
    assert field_code(response, "rate") == "same_rate"
    body = {"academic_year": year, "rate": "2875.5", "reason": "Taux de la banque centrale"}
    assert client.post(RATES, body).status_code == 201

    history = client.get(RATES).json()
    assert [(r["rate"], r["reason"]) for r in history] == [
        ("2875.500000", "Taux de la banque centrale"),
        ("2850.000000", ""),
    ]
    assert history[0]["set_by"]["id"] == str(head.pk)
    with use_school(school):
        assert services.current_rate(alpha["year"]).rate == Decimal("2875.5")
    first, correction = entries(school, "finance.exchange_rate_set")
    assert (first.before, first.after) == (None, {"rate": "2850"})
    assert correction.before == {"rate": "2850"}
    assert correction.after == {"rate": "2875.5", "reason": "Taux de la banque centrale"}


def test_a_saved_rate_is_never_changed_or_deleted(alpha, head, school):
    with use_school(school):
        rate = services.set_exchange_rate(
            actor=head, academic_year=alpha["year"], rate=Decimal("2850")
        )
        rate.rate = Decimal("1")
        with pytest.raises(ImmutableRateError):
            rate.save()
        with pytest.raises(ImmutableRateError):
            ExchangeRate.objects.update(rate=Decimal("1"))
        with pytest.raises(ImmutableRateError):
            rate.delete()
        # Même en SQL brut, sur les lignes que la base laisse voir (S.6) : le déclencheur refuse.
        for sql in ("UPDATE finance_exchangerate SET rate = 1", "DELETE FROM finance_exchangerate"):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)
        assert ExchangeRate.objects.get(pk=rate.pk).rate == Decimal("2850")


# Devises de l'école (M5)


def test_a_currency_used_by_a_fee_rule_stays_in_the_school(api, alpha, head, school):
    client = api(head)
    cdf = rule_body(alpha, currency="CDF", total_amount_minor=90000, schedule_kind="single")
    single = [{"label": "Motivation", "amount_minor": 90000, "due_on": "2026-10-01"}]
    assert client.post(RULES, {**cdf, "installments": single}).status_code == 201

    response = client.patch(SETTINGS, {"enabled_currencies": ["USD"], "default_currency": "USD"})

    assert field_code(response, "enabled_currencies") == "currency_in_use"
    school.refresh_from_db()
    assert school.enabled_currencies == ["USD", "CDF"]


# Nouvelle année (C1)


def test_a_new_year_copies_the_fee_rules_with_shifted_dates(api, alpha, head, school):
    with use_school(school):
        services.create_fee_rule(
            actor=head,
            academic_year=alpha["year"],
            fee_type=alpha["fee_type"],
            currency="USD",
            total_amount_minor=39000,
            schedule_kind="single",
            installments=[Installment("Minerval", 39000, date(2026, 10, 15))],
            scope=Scope(class_group=alpha["group"]),
        )
    body = {
        "starts_on": "2027-09-01",
        "ends_on": "2028-07-01",
        "copy_classes_from": str(alpha["year"].pk),
        "copy_fees": True,
    }

    response = api(head).post(YEARS, body)

    assert response.status_code == 201, response.content
    with use_school(school):
        year = AcademicYear.objects.get(pk=response.json()["id"])
        rules = {rule.scope_name: rule for rule in year.fee_rules.all()}
        assert set(rules) == {"3e", "3E ÉLECTRICITÉ A"}
        assert rules["3E ÉLECTRICITÉ A"].class_group == ClassGroup.objects.get(academic_year=year)
        dues = [i.due_on for i in rules["3e"].installments.all()]
        assert dues == [date(2027, 10, 15), date(2028, 1, 15), date(2028, 4, 15)]
    [copied] = entries(school, "finance.fee_rules_copied")
    assert copied.after == {"copied_from": "2026-2027", "fee_rule_count": 2}


def test_copying_the_fee_rules_needs_the_fees_permission(api, alpha, school):
    director = MembershipFactory(school=school, roles=["study_director"]).user
    body = {
        "starts_on": "2027-09-01",
        "ends_on": "2028-07-01",
        "copy_classes_from": str(alpha["year"].pk),
    }
    client = api(director)

    assert client.post(YEARS, {**body, "copy_fees": True}).status_code == 403
    with use_school(school):
        assert AcademicYear.objects.count() == 1
    assert client.post(YEARS, body).status_code == 201
    with use_school(school):
        assert FeeType.objects.count() == 1
        assert FeeRule.objects.count() == 1
