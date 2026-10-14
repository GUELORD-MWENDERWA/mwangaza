"""Compte PostgreSQL de l'application (S.5) : avec lui, l'application encaisse et supprime un
espace d'essai, mais ne peut ni contourner les déclencheurs d'immuabilité, ni vider une table, ni
toucher à la structure de la base."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection, transaction
from psycopg import errors

from apps.core.db_roles import setup_app_role
from apps.core.tenancy import use_all_schools, use_school
from apps.finance.models import Payment
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.schools import deletion
from apps.schools.models import School
from tests.factories import MembershipFactory, SchoolFactory

pytestmark = pytest.mark.django_db

ROLE = "mwangaza_app_test"

# Chaque ligne rendrait les paiements ou le journal modifiables, ou les effacerait d'un coup.
OUT_OF_REACH = (
    "TRUNCATE finance_payment CASCADE",
    "ALTER TABLE finance_payment DISABLE TRIGGER ALL",
    "DROP TRIGGER finance_payment_immutable ON finance_payment",
    "CREATE OR REPLACE FUNCTION finance_payment_immutable() RETURNS trigger AS "
    "'BEGIN RETURN OLD; END' LANGUAGE plpgsql",
    "SET session_replication_role = replica",  # les déclencheurs ne tourneraient plus
    "DROP TABLE audit_auditlog CASCADE",
    "CREATE TABLE cachette (id int)",
    f"ALTER ROLE {ROLE} SUPERUSER",
)


@pytest.fixture
def app_role(migration_account):
    """La suite du test tourne avec le compte de l'application, comme Django en production. Le
    compte, créé dans la transaction du test, disparaît avec elle."""
    setup_app_role(ROLE, "secret-de-test")
    setup_app_role(ROLE, "autre-secret")  # relancé après chaque `migrate` : rejouable
    with connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL ROLE {ROLE}")
    return ROLE


def refusal(statement: str, params=None) -> Exception:
    """L'erreur de PostgreSQL pour `statement`, sans rien changer ni casser la transaction."""
    cursor = connection.cursor()
    with pytest.raises(DatabaseError) as refused, transaction.atomic(), cursor:
        cursor.execute(statement, params)
    return refused.value.__cause__


def test_the_app_role_cannot_get_around_the_immutability_triggers(app_role):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls,"
            " (SELECT count(*) FROM pg_class WHERE relowner = pg_roles.oid)"
            " FROM pg_roles WHERE rolname = current_user"
        )
        assert cursor.fetchone() == (False, 0)

    for statement in OUT_OF_REACH:
        assert isinstance(refusal(statement), errors.InsufficientPrivilege), statement


def test_the_app_role_collects_and_deletes_a_trial_space_but_never_a_payment_of_a_live_one(
    app_role, school, head, cashier
):
    sandbox = SchoolFactory(code="essai", environment="test")
    sandbox_head = MembershipFactory(school=sandbox, roles=["head"]).user
    sandbox_cashier = MembershipFactory(school=sandbox, roles=["cashier"]).user
    kept = pay(school, cashier, school_with_fees(school, head)["enrollment"], 12000, "USD")
    pay(sandbox, sandbox_cashier, school_with_fees(sandbox, sandbox_head)["enrollment"], 500, "USD")
    # Même l'espace réel, marqué « suppression en cours » par erreur.
    School.objects.update(status=School.Status.DELETING)

    # Le compte a le droit d'écrire des lignes : c'est le déclencheur qui refuse.
    with use_school(school):
        for statement in (
            "DELETE FROM finance_payment WHERE id = %s",
            "UPDATE finance_payment SET received_amount_minor = 1 WHERE id = %s",
        ):
            assert isinstance(refusal(statement, [kept.pk]), errors.RestrictViolation), statement
    for space in (school, sandbox):
        deletion.run(str(space.pk))

    assert not School.objects.filter(pk=sandbox.pk).exists()
    with use_all_schools():
        left = Payment.all_schools.values_list("pk", "received_amount_minor")
        assert list(left) == [(kept.pk, 12000)]


def test_the_migration_account_is_never_turned_into_the_app_role(migration_account):
    with pytest.raises(ImproperlyConfigured):
        setup_app_role(connection.settings_dict["USER"], "secret-de-test")
