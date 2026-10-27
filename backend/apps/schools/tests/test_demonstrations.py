"""Démonstration depuis la console (4.17.2, A6) : espace créé puis rempli en tâche de fond, dans
son bloc de numéros ; nombre limité, un seul travail à la fois ; fiche d'accès lue dans l'espace
seulement ; comptes partagés protégés ; remise à zéro (même identifiant, nouveau mot de passe)
sans toucher à un autre espace. Réservé au super-admin : `test_console_schools.py`."""

import re
from contextlib import suppress

import pytest
from django.contrib.auth import authenticate

from apps.accounts.models import Membership
from apps.audit.models import PlatformAuditLog
from apps.core import demo
from apps.core.tenancy import use_school
from apps.schools import deletion, demonstrations
from apps.schools.models import Demonstration, School
from apps.students.models import Family, Student

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
SCHOOLS = "/api/console/schools/"
PASSWORD = "/api/auth/password/"


def create(console, code="vitrine", profile="small"):
    return console.post(f"{SCHOOLS}demo/", {"code": code, "name": code.title(), "profile": profile})


def sheet(console, school_id) -> str:
    response = console.get(f"{SCHOOLS}{school_id}/access-sheet/", output="html")
    assert response.status_code == 200
    return response.content.decode()


def rows_per_model(school) -> dict[str, int]:
    return {
        model._meta.label: deletion._rows(model, lookups, school).count()
        for model, lookups in deletion.plan()
    }


@pytest.mark.django_db(transaction=True)
def test_a_demonstration_space_is_filled_shown_on_its_sheet_and_reset_without_the_other_one(
    api, platform_admin, settings
):
    settings.DEMO_SPACES_MAX = 2
    console = api(platform_admin, host=CONSOLE)

    created = create(console)
    other = create(console, code="salon").json()
    full = create(console, code="trop")

    # Tâche de fond passée (Celery immédiat dans les tests) : rempli, chacun dans son bloc.
    assert created.status_code == 201 and created.json()["environment"] == "demo"
    assert (full.status_code, full.json()["code"]) == (409, "demo_limit")
    school_id = created.json()["id"]
    detail = f"{SCHOOLS}{school_id}/"
    state = console.get(detail).json()["demonstration"]
    assert state == {
        "profile": "small",
        "state": "ready",
        "steps_done": len(demo.STEPS),
        "steps_total": len(demo.STEPS),
    }
    vitrine, salon = School.objects.get(pk=school_id), School.objects.get(pk=other["id"])
    assert [d.block for d in Demonstration.objects.order_by("block")] == [40, 41]
    with use_school(vitrine):
        assert Student.objects.count() == 150
        codes = set(Family.objects.values_list("code", flat=True))

    # Fiche d'accès : un mot de passe qui ouvre vraiment ses comptes, et rien de l'autre espace.
    page = sheet(console, school_id)
    password = demonstrations.access_sheet(vitrine)["password"]
    head = authenticate(username="0004002001", password=password)
    assert head is not None and password in page and "0004002001" in page
    assert authenticate(username="0004102001", password=password) is None
    numbers = set(re.findall(r"\b00\d{8}\b", page))
    assert len(numbers) > 4 and all(number.startswith("00040") for number in numbers)
    family_codes = {code.replace("-", "") for code in re.findall(r"[A-Z0-9]{4}-[A-Z0-9]{4}", page)}
    assert len(family_codes) == demonstrations.FAMILIES_TO_ACTIVATE and family_codes <= codes

    # Compte partagé entre visiteurs : son mot de passe ne se change pas.
    visitor = api(head, host="vitrine.localhost")
    refused = visitor.post(
        PASSWORD, {"current_password": password, "new_password": "visiteur-2026"}
    )
    assert (refused.status_code, refused.json()["code"]) == (409, "shared_demo_account")
    assert authenticate(username="0004002001", password=password) == head

    # Remise à zéro : supprimé puis recréé. Ce que le visiteur avait changé n'y est plus.
    kept = rows_per_model(salon)
    School.objects.filter(pk=school_id).update(primary_color="#123456")
    wrong = console.post(f"{detail}reset/", {"confirm": "salon"})
    assert wrong.status_code == 400
    assert console.post(f"{detail}reset/", {"confirm": "vitrine"}).status_code == 200

    again = console.get(detail).json()
    assert (again["code"], again["status"], again["demonstration"]["state"]) == (
        "vitrine",
        "active",
        "ready",
    )
    assert Demonstration.objects.get(school_id=school_id).block == 40
    assert rows_per_model(salon) == kept
    vitrine = School.objects.get(pk=school_id)
    assert vitrine.primary_color == "#7A3E00"
    with use_school(vitrine):
        assert Student.objects.count() == 150
        # Comptes recréés avec l'espace : utilisables, portail compris.
        activated = Family.objects.filter(activated_at__isnull=False)
        assert activated.count() > 10
        assert not activated.filter(primary_user__is_active=False).exists()
    assert not Membership.objects.filter(school=vitrine, user__is_active=False).exists()
    new_password = demonstrations.access_sheet(vitrine)["password"]
    assert new_password != password and new_password in sheet(console, school_id)
    assert authenticate(username="0004002001", password=password) is None
    # Comptes effacés avec l'espace puis recréés : même numéro, autre compte.
    assert authenticate(username="0004002001", password=new_password).phone == head.phone
    journal = PlatformAuditLog.objects.filter(entity_id=school_id).order_by("created_at", "id")
    assert [log.action for log in journal] == ["school.created", "school.deleted", "school.created"]


def test_only_a_ready_console_demonstration_has_a_sheet_and_a_reset(
    api, platform_admin, school, monkeypatch, django_capture_on_commit_callbacks
):
    console = api(platform_admin, host=CONSOLE)
    # Ni un espace réel, ni un espace de `make demo` (sans ligne `Demonstration`).
    for action in (console.get(f"{SCHOOLS}{school.pk}/access-sheet/", output="html"),):
        assert (action.status_code, action.json()["code"]) == (409, "not_a_console_demo")
    refused = console.post(f"{SCHOOLS}{school.pk}/reset/", {"confirm": "alpha"})
    assert (refused.status_code, refused.json()["code"]) == (409, "not_a_console_demo")
    empty = console.post(SCHOOLS, {"code": "vide", "name": "Vide", "environment": "demo"})
    assert (empty.status_code, "environment" in empty.json()["fields"]) == (400, True)

    # Tâche de fond pas encore passée : espace ouvert, vide, sans fiche ; rien d'autre ne démarre.
    created = create(console).json()
    assert created["demonstration"]["state"] == "filling"
    not_ready = console.get(f"{SCHOOLS}{created['id']}/access-sheet/", output="pdf")
    assert (not_ready.status_code, not_ready.json()["code"]) == (409, "demo_not_ready")
    busy = create(console, code="salon")
    assert (busy.status_code, busy.json()["code"]) == (409, "space_busy")

    # Une étape échoue : « en échec », à remettre à zéro ou à supprimer.
    def broken(spaces):
        raise RuntimeError("panne")

    monkeypatch.setattr(demo, "STEPS", [lambda spaces: None, broken])
    # Une tâche par étape : la seconde échoue dans sa propre tâche.
    with suppress(RuntimeError):
        demonstrations.fill(created["id"])
    failed = console.get(f"{SCHOOLS}{created['id']}/").json()["demonstration"]
    assert (failed["state"], failed["steps_done"], failed["steps_total"]) == ("failed", 1, 2)

    # Reprise là où on en était (tâche perdue, travailleur arrêté) : seule l'étape 2 se refait.
    ran = []
    monkeypatch.setattr(demo, "STEPS", [lambda spaces: ran.append(1), lambda s: ran.append(2)])
    Demonstration.objects.update(state="filling")
    demonstrations.fill(created["id"])
    resumed = console.get(f"{SCHOOLS}{created['id']}/").json()["demonstration"]
    assert ran == [2] and (resumed["state"], resumed["steps_done"]) == ("ready", 2)

    # Supprimé pendant qu'il se remplit : le remplissage s'arrête, puis l'espace part.
    Demonstration.objects.update(state="filling", steps_done=0)

    def deleted_meanwhile(spaces):
        School.objects.filter(pk=created["id"]).update(status=School.Status.DELETING)

    monkeypatch.setattr(demo, "STEPS", [deleted_meanwhile, broken])
    demonstrations.fill(created["id"])
    assert not School.objects.filter(pk=created["id"]).exists()
    assert not Demonstration.objects.exists()
