"""`AuditLog` [T] [I] : propre à une école, ni modifiable ni effaçable, même en SQL direct."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.actions import Action
from apps.audit.models import AuditLog, ImmutableError
from apps.core.tenancy import SchoolNotSetError, use_all_schools, use_school

pytestmark = pytest.mark.django_db

LABEL = "Chef d'atelier"


def entry(school) -> AuditLog:
    with use_school(school):
        return AuditLog.objects.create(
            action=Action.ROLES_CREATED, entity_type="accounts.role", entity_label=LABEL
        )


def test_an_entry_cannot_be_changed(school):
    log = entry(school)
    log.entity_label = "Autre chose"

    with use_school(school), pytest.raises(ImmutableError):
        log.save()

    with use_all_schools():
        assert AuditLog.all_schools.get(pk=log.pk).entity_label == LABEL


def test_an_entry_cannot_be_deleted(school):
    log = entry(school)

    with use_school(school), pytest.raises(ImmutableError):
        log.delete()

    with use_all_schools():
        assert AuditLog.all_schools.filter(pk=log.pk).exists()


def test_entries_cannot_be_changed_or_deleted_in_bulk(school):
    entry(school)

    with use_school(school):
        with pytest.raises(ImmutableError):
            AuditLog.objects.update(entity_label="Autre chose")
        with pytest.raises(ImmutableError):
            AuditLog.objects.all().delete()
    with pytest.raises(ImmutableError):
        AuditLog.all_schools.filter(school=school).update(entity_label="Autre chose")
    with pytest.raises(ImmutableError):
        AuditLog.all_schools.filter(school=school).delete()

    with use_all_schools():
        assert AuditLog.all_schools.get().entity_label == LABEL


@pytest.mark.parametrize(
    "sql",
    ["UPDATE audit_auditlog SET entity_label = 'Autre chose'", "DELETE FROM audit_auditlog"],
)
def test_the_database_refuses_changes_even_in_sql(school, sql):
    log = entry(school)

    # Dans la portée de l'école : sinon la base ne montre aucune ligne à changer (S.6).
    with (
        use_school(school),
        pytest.raises(DatabaseError),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(sql)

    with use_all_schools():
        assert AuditLog.all_schools.get(pk=log.pk).entity_label == LABEL


def test_each_school_reads_only_its_own_entries(school, other_school):
    mine, theirs = entry(school), entry(other_school)

    with use_school(school):
        assert list(AuditLog.objects.all()) == [mine]
    with use_school(other_school):
        assert list(AuditLog.objects.all()) == [theirs]
    with pytest.raises(SchoolNotSetError):
        list(AuditLog.objects.all())


def test_an_entry_needs_a_school(db):
    with pytest.raises(SchoolNotSetError):
        AuditLog.objects.create(action=Action.ROLES_CREATED)


def test_newest_entries_come_first(school):
    first, second = entry(school), entry(school)

    with use_school(school):
        assert list(AuditLog.objects.all()) == [second, first]
