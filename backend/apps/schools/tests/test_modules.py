"""Modules d'une école (M.1) : seul le super-admin les donne, un module absent ferme ses droits
(403 côté serveur, même pour le directeur) sans rien supprimer ; l'école voisine reste intacte."""

from io import BytesIO

import pytest
from openpyxl import load_workbook

from apps.accounts.models import Role
from apps.accounts.modules import ALL_MODULES
from apps.audit.actions import Action
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.core.ids import uuid7
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import School
from apps.students import imports
from apps.students.models import Student
from apps.students.tests.conftest import GUARDIAN
from tests.factories import SchoolFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
STUDENTS = "/api/students/"
FEES = "/api/fee-types/"
ME = "/api/me/"
LOADS = "/api/teaching-loads/"
SETTINGS = "/api/school/settings/"
TEMPLATE = "/api/student-imports/template/"
# Forfaits de départ (MOD.1), une matrice et non une pile de tests. « Élèves seuls » tient la
# place de « Présences seules » jusqu'au lot 16, qui ajoute `attendance` et « Sonnerie seule ».
FORFAITS = {
    "students_only": ["students"],
    "students_and_cash": ["students", "finance"],
    "complete": ALL_MODULES,
}


def permissions(api, user) -> set[str]:
    return set(api(user).get(ME).json()["school"]["permissions"])


def test_a_module_missing_closes_its_permissions_without_deleting_anything(api, school, head):
    assert api(head).get(FEES).status_code == 200
    school.modules = ["students"]
    school.save()

    assert api(head).get(STUDENTS).status_code == 200
    assert api(head).get(FEES).status_code == 403
    # Le socle reste ouvert ; les droits du rôle restent enregistrés pour le retour du module.
    assert api(head).get("/api/roles/").status_code == 200
    assert not {code for code in permissions(api, head) if code.startswith("finance.")}
    school.modules = ["students", "finance"]
    school.save()
    assert api(head).get(FEES).status_code == 200


def test_a_new_school_has_no_module_and_the_platform_gives_them(api, platform_admin, head, school):
    school.modules = []
    school.save()
    other = SchoolFactory(code="beta", modules=["students", "finance"])
    other_head = _head_of(other)
    console = api(platform_admin, host=CONSOLE)

    response = console.patch(f"/api/console/schools/{school.pk}/", {"modules": ["finance"]})

    assert response.status_code == 200
    # Le module dont `finance` dépend est donné avec lui.
    assert response.json()["modules"] == ["students", "finance"]
    school.refresh_from_db()
    other.refresh_from_db()
    assert (school.modules, other.modules) == (["students", "finance"], ["students", "finance"])
    assert api(other_head, host="beta.localhost").get(STUDENTS).status_code == 200
    assert api(head).get(STUDENTS).status_code == 200
    change = PlatformAuditLog.objects.filter(entity_id=str(school.pk)).latest("created_at")
    assert change.after["modules"] == ["students", "finance"]
    assert (
        console.patch(f"/api/console/schools/{school.pk}/", {"modules": ["x"]}).status_code == 400
    )
    assert School._meta.get_field("modules").default() == []


def test_a_module_cannot_be_removed_while_another_active_module_needs_it(
    api, platform_admin, school
):
    school.modules = ["students", "finance", "portal"]
    school.save()
    console = api(platform_admin, host=CONSOLE)
    url = f"/api/console/schools/{school.pk}/"

    refused = console.patch(url, {"modules": ["finance", "portal"]})

    assert refused.status_code == 400 and "modules" in str(refused.json())
    school.refresh_from_db()
    assert school.modules == ["students", "finance", "portal"]
    # Les deux qui en dépendent partent avec lui ; l'école garde ses données (rien n'est effacé).
    assert console.patch(url, {"modules": ["communication"]}).json()["modules"] == ["communication"]


def test_a_school_without_the_offline_module_has_no_snapshot_and_no_device(api, school, head):
    school.modules = ["students", "finance"]
    school.save()

    assert api(head).get("/api/sync/snapshot/").status_code == 403
    assert api(head).post("/api/me/devices/", {"label": "PC", "public_key": "x"}).status_code == 403


def test_the_scheduler_skips_a_school_without_notifications_and_serves_the_others(
    monkeypatch, school, other_school, head, other_head
):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from apps.finance.tests.test_payments import school_with_fees
    from apps.notifications import scheduled
    from apps.notifications.models import ScheduledRun
    from apps.notifications.tests.test_events import parent_of

    for item, owner in ((school, head), (other_school, other_head)):
        data = school_with_fees(item, owner)
        parent_of(item, data["enrollment"])
        item.settings = {**item.settings, "reminders": {"enabled": True}}
    school.modules = ["students", "finance", "portal"]
    school.save()
    other_school.save()
    now = datetime(2026, 10, 12, 9, 0, tzinfo=ZoneInfo("Africa/Lubumbashi"))

    scheduled.tick(now)

    with use_all_schools():
        assert set(ScheduledRun.all_schools.values_list("school__code", flat=True)) == {
            other_school.code
        }


def test_the_school_cannot_give_itself_modules(api, head, school):
    response = api(head).patch(f"/api/console/schools/{school.pk}/", {"modules": ["students"]})

    assert response.status_code in (403, 404)


def _head_of(school):
    from tests.factories import MembershipFactory

    return MembershipFactory(school=school, roles=["head"]).user


def test_me_gives_the_modules_and_the_setup_list_follows_them(api, school, head):
    assert set(api(head).get(ME).json()["school"]["modules"]) == set(school.modules)
    school.modules = ["students"]
    school.save()

    assert api(head).get(ME).json()["school"]["modules"] == ["students"]
    steps = api(head).get("/api/school/setup/").json()["steps"]
    # Sans `finance` ni `portal` : ni frais, ni caisse, ni reprise, ni invitations.
    assert [step["key"] for step in steps] == ["year", "classes", "students"]
    # Sans module, rien à mettre en route : années et classes ne servent qu'aux élèves (MOD.1).
    school.modules = []
    school.save()
    assert api(head).get("/api/school/setup/").json()["steps"] == []


@pytest.mark.parametrize("forfait", FORFAITS)
def test_each_forfait_asks_and_writes_only_what_its_modules_need(
    api, school, other_school, head, other_head, forfait
):
    school.modules = FORFAITS[forfait]
    school.save()
    client = api(head)
    academics, finance = "academics" in school.modules, "finance" in school.modules

    me = client.get(ME).json()["school"]
    assert me["modules"] == FORFAITS[forfait]
    assert ("student.permanent_number" in me["features"]) is academics
    assert ("settings.currencies" in me["features"]) is finance
    # Élève avec le minimum : le N° permanent n'est ni exigé, ni écrit sans les bulletins.
    body = {"id": str(uuid7()), "last_name": "Kasereka", "sex": "M", "guardians": [GUARDIAN]}
    created = client.post(STUDENTS, {**body, "permanent_number": "2-1234567890"})
    assert created.status_code == 201, created.json()
    with use_school(school):
        written = Student.objects.get(pk=body["id"]).permanent_number
    assert written == ("2-1234567890" if academics else "")
    # Points d'API des autres modules fermés.
    assert client.get(FEES).status_code == (200 if finance else 403)
    assert client.get(LOADS).status_code == (200 if academics else 403)
    # Modèle d'import sans les colonnes du bulletin (N° ID, N° permanent, lieu de naissance).
    titles = next(load_workbook(BytesIO(client.get(TEMPLATE).content)).active.values)
    assert len(titles) == len(imports.FIELDS) - (0 if academics else 3)
    # Réglages du reçu jamais écrits sans la caisse ; rien de perdu, ils restent lisibles.
    assert client.patch(SETTINGS, {"receipt": {"printer": "sheet"}}).status_code == 200
    assert (client.get(SETTINGS).json()["receipt"]["printer"] == "sheet") is finance
    # L'école voisine (Gestion complète) garde tout.
    beta = api(other_head, host="beta.localhost").get(ME).json()["school"]
    assert "student.permanent_number" in beta["features"]


def test_a_school_created_with_a_forfait_gets_its_roles_then_those_of_a_new_module(
    api, platform_admin
):
    console = api(platform_admin, host=CONSOLE)
    head = {"phone": "0100003001", "last_name": "Kasereka", "first_name": "Dieudonné"}
    # « Élèves seuls » : ni devises demandées (pas de caisse), ni caissier ni enseignant.
    response = console.post(
        "/api/console/schools/",
        {"code": "gamma", "name": "Gamma", "modules": ["students"], "head": head},
    )
    assert response.status_code == 201, response.json()
    gamma = School.objects.get(code="gamma")
    with use_school(gamma):
        names = set(Role.objects.values_list("name", flat=True))
    assert "Directeur" in names and not names & {"Caissier", "Comptable", "Enseignant"}

    console.patch(f"/api/console/schools/{gamma.pk}/", {"modules": ["students", "finance"]})

    with use_school(gamma):
        added = AuditLog.objects.filter(action=Action.ROLES_CREATED)
        assert set(added.values_list("entity_label", flat=True)) == {"Caissier", "Comptable"}
    # Retiré puis rendu : un rôle que l'école a gardé n'est pas recopié.
    console.patch(f"/api/console/schools/{gamma.pk}/", {"modules": ["students"]})
    console.patch(f"/api/console/schools/{gamma.pk}/", {"modules": ["students", "finance"]})
    with use_school(gamma):
        assert Role.objects.filter(name="Caissier").count() == 1
