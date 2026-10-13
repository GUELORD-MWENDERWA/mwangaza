"""Modules d'une école (M.1) : seul le super-admin les donne, un module absent ferme ses droits
(403 côté serveur, même pour le directeur) sans rien supprimer ; l'école voisine reste intacte."""

import pytest

from apps.audit.models import PlatformAuditLog
from apps.schools.models import School
from tests.factories import SchoolFactory

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
STUDENTS = "/api/students/"
FEES = "/api/fee-types/"
ME = "/api/me/"


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
    other = SchoolFactory(code="beta", modules=["students", "finance"])
    other_head = _head_of(other)
    console = api(platform_admin, host=CONSOLE)

    response = console.patch(f"/api/console/schools/{school.pk}/", {"modules": ["finance"]})

    assert response.status_code == 200
    assert response.json()["modules"] == ["finance"]
    school.refresh_from_db()
    other.refresh_from_db()
    assert (school.modules, other.modules) == (["finance"], ["students", "finance"])
    assert api(other_head, host="beta.localhost").get(STUDENTS).status_code == 200
    assert api(head).get(STUDENTS).status_code == 403
    change = PlatformAuditLog.objects.filter(entity_id=str(school.pk)).latest("created_at")
    assert change.after["modules"] == ["finance"]
    assert (
        console.patch(f"/api/console/schools/{school.pk}/", {"modules": ["x"]}).status_code == 400
    )
    assert School._meta.get_field("modules").default() == []


def test_the_school_cannot_give_itself_modules(api, head, school):
    response = api(head).patch(f"/api/console/schools/{school.pk}/", {"modules": ["students"]})

    assert response.status_code in (403, 404)


def _head_of(school):
    from tests.factories import MembershipFactory

    return MembershipFactory(school=school, roles=["head"]).user
