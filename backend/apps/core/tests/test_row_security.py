"""Row Level Security (S.6) : même si un `filter` est oublié, ou en SQL brut, PostgreSQL ne
montre et ne laisse écrire que les lignes des écoles de la portée de la connexion. Les tests
tournent avec un compte soumis aux règles (`conftest.py`), comme Django en production."""

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import RequestFactory
from psycopg import errors

from apps.core import row_security
from apps.core.middleware import RowSecurityMiddleware
from apps.core.tenancy import CrossSchoolError, use_all_schools, use_school, use_schools
from apps.finance.models import FeeRule, FeeType
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.students.models import Family
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def fee_type(school, name):
    with use_school(school):
        return FeeType.objects.create(name=name, category=FeeType.Category.TUITION)


def visible() -> list[str]:
    """Ce qu'un `filter` oublié laisserait voir : toutes les lignes que la base montre."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM finance_feetype ORDER BY name")
        sql = [name for (name,) in cursor.fetchall()]
    assert sorted(FeeType.all_schools.values_list("name", flat=True)) == sql
    return sql


def test_a_forgotten_filter_only_sees_the_schools_of_the_scope(school, other_school):
    fee_type(school, "Minerval A")
    fee_type(other_school, "Minerval B")

    assert visible() == []
    with use_school(school):
        assert visible() == ["Minerval A"]
        with use_all_schools():
            assert visible() == ["Minerval A", "Minerval B"]
            with use_school(other_school):
                assert visible() == ["Minerval B"]
        assert visible() == ["Minerval A"]
    with use_schools([other_school.pk]):
        assert visible() == ["Minerval B"]
    assert visible() == []


def test_the_database_refuses_to_write_or_change_a_row_of_another_school(school, other_school):
    theirs = fee_type(other_school, "Minerval B")
    with use_school(school), connection.cursor() as cursor:
        cursor.execute("UPDATE finance_feetype SET name = 'pris' WHERE id = %s", [theirs.pk])
        assert cursor.rowcount == 0
        cursor.execute("DELETE FROM finance_feetype WHERE id = %s", [theirs.pk])
        assert cursor.rowcount == 0
        with pytest.raises(DatabaseError) as refused, transaction.atomic():
            cursor.execute(
                "INSERT INTO finance_feetype (id, school_id, name, category, funds_teacher_bonus,"
                " accounting_code, is_active, created_at, updated_at)"
                " VALUES (gen_random_uuid(), %s, 'intrus', 'tuition', false, '', true, now(),"
                " now())",
                [other_school.pk],
            )
    assert isinstance(refused.value.__cause__, errors.InsufficientPrivilege)
    with use_school(other_school):
        assert FeeType.objects.get().name == "Minerval B"


def test_a_link_to_a_row_hidden_by_the_database_is_refused(school, other_school):
    """La clé étrangère, vérifiée par PostgreSQL sans les règles, accepterait le lien."""
    year = school_with_fees(school, MembershipFactory(school=school, roles=["head"]).user)["year"]
    theirs = fee_type(other_school, "Minerval B")
    with use_school(school), pytest.raises(CrossSchoolError, match="introuvable"):
        FeeRule.objects.create(academic_year=year, fee_type_id=theirs.pk)


def test_a_failed_transaction_inside_a_scope_keeps_its_error_and_the_outer_scope(
    school, other_school
):
    fee_type(school, "Minerval A")
    with use_school(school):
        with pytest.raises(IntegrityError), transaction.atomic(), use_school(other_school):
            fee_type(other_school, "Minerval B")
            fee_type(other_school, "minerval b")  # même nom : refusé, transaction en échec
        assert visible() == ["Minerval A"]


def test_requests_without_a_school_get_the_scope_of_their_user(
    school, other_school, head, platform_admin
):
    fee_type(school, "Minerval A")
    fee_type(other_school, "Minerval B")
    parent = MembershipFactory(school=school, roles=["head"]).user
    with use_school(other_school):
        Family.objects.create(code="FAM00001", primary_user=parent)

    def seen(user, host="localhost", path="/api/portal/children/"):
        request = RequestFactory().get(path, HTTP_HOST=host)
        request.user, request.school = user, None
        return RowSecurityMiddleware(lambda request: visible())(request)

    assert seen(parent) == ["Minerval B"]
    assert seen(head) == []  # sans famille reliée
    assert seen(parent, path="/api/me/") == []
    assert seen(platform_admin, host="admin.localhost", path="/api/console/schools/") == [
        "Minerval A",
        "Minerval B",
    ]
    assert seen(platform_admin, path="/admin/") == ["Minerval A", "Minerval B"]
    assert seen(head, host="admin.localhost", path="/api/console/schools/") == []


def test_every_table_of_a_school_in_scope_has_its_rule_installed_once():
    row_security.install(connection.alias)  # rejouable
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid"
            " WHERE c.relrowsecurity AND p.polname = %s",
            [row_security.POLICY],
        )
        installed = sorted(name for (name,) in cursor.fetchall())
    assert installed == row_security.tables()
    assert "finance_payment" in installed and "finance_cashclosing" in installed


def test_a_payment_of_another_school_is_neither_seen_nor_counted(
    school, other_school, head, cashier, other_head
):
    other_cashier = MembershipFactory(school=other_school, roles=["cashier"]).user
    pay(school, cashier, school_with_fees(school, head)["enrollment"], 12000, "USD")
    pay(
        other_school,
        other_cashier,
        school_with_fees(other_school, other_head)["enrollment"],
        500,
        "USD",
    )
    with use_school(school), connection.cursor() as cursor:
        cursor.execute("SELECT sum(received_amount_minor) FROM finance_payment")
        assert cursor.fetchone() == (12000,)
