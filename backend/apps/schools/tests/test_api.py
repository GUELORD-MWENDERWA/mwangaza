"""GET /api/school/ : l'école du sous-domaine (écran de connexion de la Gestion)."""

import pytest

pytestmark = pytest.mark.django_db


def test_each_school_sees_its_own_name(client, school, other_school):
    alpha = client.get("/api/school/", HTTP_HOST="alpha.localhost:5173")
    beta = client.get("/api/school/", HTTP_HOST="beta.localhost:5173")

    assert alpha.status_code == 200
    assert alpha.json() == {
        "code": "alpha",
        "name": "École Alpha (fictive)",
        "primary_color": "#0E5C6B",
        "text_color": "#FFFFFF",
        "logo": None,
    }
    assert beta.json()["name"] == "École Beta (fictive)"


def test_colour_and_readable_text(client, school):
    school.primary_color = "#F2C94C"
    school.save()

    body = client.get("/api/school/", HTTP_HOST="alpha.localhost").json()

    assert (body["primary_color"], body["text_color"]) == ("#F2C94C", "#1A2233")


def test_is_public(client, school):
    # Pas de connexion : l'écran de connexion affiche le nom de l'école.
    assert client.get("/api/school/", HTTP_HOST="alpha.localhost").status_code == 200


def test_without_school_returns_404(client, school):
    response = client.get("/api/school/", HTTP_HOST="localhost:8000")

    assert response.status_code == 404
    assert response.json()["code"] == "school_not_found"


def test_unknown_school_returns_404(client, school):
    response = client.get("/api/school/", HTTP_HOST="inconnue.localhost")

    assert response.status_code == 404
    assert response.json()["code"] == "school_not_found"
    assert "Alpha" not in response.content.decode()


def test_only_get_is_allowed(client, school):
    response = client.post("/api/school/", {"name": "Piratée"}, HTTP_HOST="alpha.localhost")

    assert response.status_code == 405
    school.refresh_from_db()
    assert school.name == "École Alpha (fictive)"
