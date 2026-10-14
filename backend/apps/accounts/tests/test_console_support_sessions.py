"""Sessions support dans la console (5.4.2) : reconstituées depuis le journal des écoles
(ouverture, fermeture et actions de la session), super-admin seulement."""

from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.utils import timezone

from apps.accounts import support
from apps.accounts.models import Role
from apps.core.tenancy import use_all_schools, use_school

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
SESSIONS = "/api/console/support-sessions/"


def open_session(client, reason: str) -> None:
    response = client.post("/api/support/", {"reason": reason})
    assert response.status_code == 201, response.content


def rename_teacher_role(client, school, name: str) -> None:
    # Le rôle sans aucune permission du modèle de départ, quel que soit son nom du moment.
    with use_school(school):
        role = Role.objects.filter(permissions=[]).earliest("id")
    assert client.patch(f"/api/roles/{role.id}/", {"name": name}).status_code == 200


def test_only_the_platform_admin_sees_support_sessions(api, platform_admin, head):
    assert api(head, host=CONSOLE).get(SESSIONS).status_code == 403
    assert api(platform_admin, host=CONSOLE, mfa=False).get(SESSIONS).status_code == 403
    assert api(platform_admin).get(SESSIONS).status_code == 404
    assert api(head).get(SESSIONS).status_code == 404


def test_sessions_of_every_school_with_their_own_actions(
    api, platform_admin, school, other_school, django_assert_max_num_queries
):
    alpha = api(platform_admin)
    beta = api(platform_admin, host="beta.localhost")
    open_session(alpha, "Le directeur ne trouve plus le rôle de la caissière")
    open_session(beta, "Import des élèves bloqué")
    rename_teacher_role(alpha, school, "Professeur")
    rename_teacher_role(beta, other_school, "Enseignant titulaire")
    rename_teacher_role(beta, other_school, "Enseignant")
    console = api(platform_admin, host=CONSOLE)

    with django_assert_max_num_queries(5):
        listed = console.get(SESSIONS).json()
    rows = {row["school"]["code"]: row for row in listed["results"]}
    # Chaque session ne compte que les actions faites dans son école.
    assert (rows["alpha"]["state"], rows["alpha"]["actions"]) == ("open", 1)
    assert (rows["beta"]["state"], rows["beta"]["actions"]) == ("open", 2)
    assert rows["beta"]["reason"] == "Import des élèves bloqué"
    assert rows["alpha"]["admin"]["id"] == str(platform_admin.pk)
    assert rows["alpha"]["ended_at"] is None

    assert alpha.delete("/api/support/").status_code == 204

    closed = console.get(f"{SESSIONS}?{urlencode({'search': school.name})}").json()["results"]
    assert [(row["state"], row["actions"]) for row in closed] == [("ended", 1)]
    assert closed[0]["ended_at"] is not None


def test_reopening_and_expiry(api, platform_admin, school):
    client = api(platform_admin)
    open_session(client, "Première demande")
    open_session(client, "Seconde demande")  # ferme la première

    now = timezone.now()
    with use_all_schools():  # comme la console
        sessions = support.sessions(now=now).order_by("created_at")
        assert [(s.after["reason"], s.state) for s in sessions] == [
            ("Première demande", "ended"),
            ("Seconde demande", "open"),
        ]
        later = support.sessions(now=now + timedelta(seconds=support.SUPPORT_DURATION + 1))
        assert sorted(s.state for s in later) == ["ended", "expired"]
