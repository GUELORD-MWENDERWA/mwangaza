"""Suppression d'un espace d'essai ou de démonstration (4.16, A5) : jamais un espace réel ; toutes
les lignes de l'espace partent, paiements compris (seule exception à « paiements immuables »),
aucune d'une autre école ; comptes restés sans école désactivés ; journal de la plateforme.
Réservé au super-admin : `test_console_schools.py`."""

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import Membership, User
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.finance.models import Payment
from apps.schools import deletion
from apps.schools.models import School
from tests.factories import MembershipFactory, SchoolFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
SCHOOLS = "/api/console/schools/"


@pytest.fixture
def sandbox(db):
    return SchoolFactory(code="essai", name="Espace d'essai", environment="test")


def delete(console, school, confirm=None):
    return console.post(f"{SCHOOLS}{school.pk}/delete/", {"confirm": confirm or school.code})


def refused_by_the_database(sql: str, school) -> bool:
    """La base refuse-t-elle `sql` (une ligne de `school`) ? Sans rien changer si elle accepte."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, [school.pk])
            transaction.set_rollback(True)
    except DatabaseError:
        return True
    return False


DELETE_JOURNAL = "DELETE FROM audit_auditlog WHERE school_id = %s"
UPDATE_JOURNAL = "UPDATE audit_auditlog SET action = 'x' WHERE school_id = %s"
DELETE_PAYMENTS = "DELETE FROM finance_payment WHERE school_id = %s"


def rows_per_model(school) -> dict[str, int]:
    return {
        model._meta.label: deletion._rows(model, lookups, school).count()
        for model, lookups in deletion.plan()
    }


def test_a_live_space_is_never_deleted(
    api, platform_admin, school, head, django_capture_on_commit_callbacks
):
    console = api(platform_admin, host=CONSOLE)

    with django_capture_on_commit_callbacks(execute=True):
        refused = delete(console, school)

    assert (refused.status_code, refused.json()["code"]) == (409, "live_space")
    console.patch(f"{SCHOOLS}{school.pk}/", {"name": "École Alpha"})  # une ligne à son journal
    # Même marqué par erreur « suppression en cours » : ni la tâche de fond ni la base n'y touchent.
    School.objects.filter(pk=school.pk).update(status=School.Status.DELETING)
    deletion.run(str(school.pk))
    assert Membership.objects.filter(school=school, user=head).exists()
    assert refused_by_the_database(DELETE_JOURNAL, school)
    assert AuditLog.all_schools.filter(school=school).count() == 1
    head.refresh_from_db()
    assert head.is_active
    assert [log.action for log in PlatformAuditLog.objects.all()] == ["school.updated"]


@pytest.mark.django_db(transaction=True)
def test_a_demo_school_is_deleted_entirely_and_the_other_school_keeps_every_row(
    api, platform_admin, settings, monkeypatch
):
    """Hors transaction de test, comme sur le serveur : chaque paquet est validé à part, la base
    vérifie donc ses liens à chaque étape (ordre de `deletion.plan()`)."""
    # Développement : le super-admin fictif de `make demo` est le compte `platform_admin`.
    settings.DEMO_DATA = settings.DEBUG = True
    call_command("demo")
    platform_admin.refresh_from_db()  # `make demo` remet son mot de passe : session à refaire
    # L'ITIG joue ici l'espace réel, avec ses paiements : rien ne doit en partir.
    School.objects.filter(code="itig").update(environment=School.Environment.LIVE)
    itig, volcans = School.objects.get(code="itig"), School.objects.get(code="volcans")
    kept, gone = rows_per_model(itig), rows_per_model(volcans)
    assert gone["finance.Payment"] and gone["accounts.Membership_roles"]
    users = User.objects.count()
    both = User.objects.filter(memberships__school=itig).filter(memberships__school=volcans)
    only_volcans = User.objects.filter(memberships__school=volcans).exclude(pk__in=both)
    teacher, volcans_head = both.first(), only_volcans.first()
    monkeypatch.setattr(deletion, "BATCH", 50)  # plusieurs paquets par modèle

    assert delete(api(platform_admin, host=CONSOLE), volcans).status_code == 204

    assert not School.objects.filter(pk=volcans.pk).exists()
    assert set(rows_per_model(volcans).values()) == {0}
    assert rows_per_model(itig) == kept
    # Les paiements d'un espace réel ne partent jamais, même marqué « suppression en cours ».
    School.objects.filter(pk=itig.pk).update(status=School.Status.DELETING)
    assert refused_by_the_database(DELETE_PAYMENTS, itig)
    assert Payment.all_schools.filter(school=itig).count() == kept["finance.Payment"]
    # Les comptes restent (auteurs du journal) ; désactivés s'ils n'avaient que cet espace.
    assert User.objects.count() == users
    for user in (teacher, volcans_head, platform_admin):
        user.refresh_from_db()
    assert (teacher.is_active, volcans_head.is_active, platform_admin.is_active) == (
        True,
        False,
        True,
    )
    log = PlatformAuditLog.objects.get(action="school.deleted")
    assert (log.actor, log.entity_id, log.before["code"]) == (
        platform_admin,
        str(volcans.pk),
        "volcans",
    )
    assert log.after == {"accounts_deactivated": User.objects.filter(is_active=False).count()}


def test_a_space_being_deleted_is_closed_and_cannot_be_changed_but_the_deletion_can_be_relaunched(
    api, platform_admin, sandbox, other_school, django_capture_on_commit_callbacks
):
    console = api(platform_admin, host=CONSOLE)
    head = MembershipFactory(school=sandbox, roles=["head"]).user
    teacher = MembershipFactory(school=sandbox, roles=["teacher"]).user
    MembershipFactory(user=teacher, school=other_school, roles=["teacher"])
    other_sandbox = SchoolFactory(code="essai2", environment="test")
    detail = f"{SCHOOLS}{sandbox.pk}/"

    wrong = delete(console, sandbox, confirm="beta")
    assert (wrong.status_code, list(wrong.json()["fields"])) == (400, ["confirm"])
    assert api(head, host="essai.localhost").get("/api/school/").status_code == 200
    # Tant qu'il n'est pas en suppression, son journal est immuable comme celui de toute école.
    console.patch(detail, {"name": "Bac à sable"})
    assert refused_by_the_database(DELETE_JOURNAL, sandbox)

    # Tâche de fond pas encore passée (ou interrompue) : l'espace est déjà fermé à tous.
    assert delete(console, sandbox).status_code == 204
    assert console.get(detail).json()["status"] == "deleting"
    gone = api(teacher, host="essai.localhost").get("/api/school/")
    assert (gone.status_code, gone.json()["code"]) == (404, "school_not_found")
    mine = api(teacher, host="beta.localhost").get("/api/me/").json()["schools"]
    assert [item["code"] for item in mine] == ["beta"]
    for user in (head, teacher):
        user.refresh_from_db()
    assert (head.is_active, teacher.is_active) == (False, True)
    for action, data in (("reactivate/", None), ("stop/", {"reason": "Erreur"})):
        refused = console.post(f"{detail}{action}", data)
        assert (refused.status_code, refused.json()["code"]) == (409, "space_being_deleted")
    assert console.patch(detail, {"name": "Gardé"}).status_code == 409
    # Même en suppression, rien ne se modifie : la base ne laisse que partir les lignes.
    assert refused_by_the_database(UPDATE_JOURNAL, sandbox)
    assert not refused_by_the_database(DELETE_JOURNAL, sandbox)
    # Une suppression à la fois.
    busy = delete(console, other_sandbox)
    assert (busy.status_code, busy.json()["code"]) == (409, "deletion_running")

    with django_capture_on_commit_callbacks(execute=True):
        assert delete(console, sandbox).status_code == 204

    assert console.get(detail).status_code == 404
    assert list(School.objects.order_by("code").values_list("code", flat=True)) == [
        "beta",
        "essai2",
    ]
    log = PlatformAuditLog.objects.get(action="school.deleted")
    assert log.after == {"accounts_deactivated": 1}
