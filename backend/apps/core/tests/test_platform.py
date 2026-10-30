"""Identité de la plateforme (5.1) : lisible partout, contrôlée, et jamais écrite en dur."""

import re
import uuid
from importlib import import_module
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts import totp
from apps.core.models import PlatformSettings
from apps.schools.models import School
from tests.images import image_bytes

INITIAL_NAME = PlatformSettings._meta.get_field("name").default


def png(width: int, height: int) -> SimpleUploadedFile:
    return SimpleUploadedFile("icone.png", image_bytes("PNG", (width, height), "RGBA"))


def test_identity_is_public_at_every_address(client, school):
    school.status = School.Status.SUSPENDED
    school.save()

    for host in ("alpha.localhost", "inconnue.localhost", "localhost"):
        response = client.get("/api/platform/", HTTP_HOST=host)
        assert response.status_code == 200, host
        assert response.json()["name"] == INITIAL_NAME
    # Le reste de l'adresse d'une école suspendue reste fermé.
    assert client.get("/api/school/", HTTP_HOST="alpha.localhost").status_code == 403


def test_a_new_name_is_used_everywhere_without_code(client, school):
    platform = PlatformSettings.load()
    platform.name, platform.short_name = "Lumière", "Lumi"
    platform.save()

    gestion = client.get("/api/platform/manifest/gestion/", HTTP_HOST="alpha.localhost").json()
    assert (gestion["name"], gestion["short_name"], gestion["start_url"]) == (
        "Lumière",
        "Lumi",
        "/app/",
    )
    assert gestion["icons"][0]["src"] == "/app/icons/symbole-192.png"  # pas d'icône : le symbole
    # Notifications : l'icône par défaut de l'application.
    icon = client.get("/api/platform/icon/?app=portail", HTTP_HOST="localhost")
    assert (icon.status_code, icon["Location"]) == (302, "/icons/symbole-192.png")
    portail = client.get("/api/platform/manifest/portail/", HTTP_HOST="localhost").json()
    assert portail["name"] == "Lumière | Parents"
    assert "issuer=Lumi%C3%A8re" in totp.provisioning_uri("SECRET", "+243970000000")
    assert "Administration Lumière" in client.get("/admin/login/").content.decode()
    verification = client.get(f"/v/{uuid.uuid4()}", HTTP_HOST="alpha.localhost")
    assert "Lumière" in verification.content.decode()


def test_unreadable_colours_and_wrong_icon_are_refused(db):
    PlatformSettings().full_clean()  # couleurs de la marque (lot 1) : acceptées
    platform = PlatformSettings.load()
    platform.primary_color = "#F2B632"  # trop clair sous un texte blanc
    platform.icon = png(600, 500)
    with pytest.raises(ValidationError) as refused:
        platform.full_clean()
    assert set(refused.value.message_dict) == {"primary_color", "icon"}
    platform = PlatformSettings.load()
    platform.accent_color = "#3B5BDB"  # bleu sur les barres bleues : illisible
    with pytest.raises(ValidationError) as refused:
        platform.full_clean()
    assert set(refused.value.message_dict) == {"accent_color"}


def test_brand_migration_keeps_a_colour_chosen_in_the_console(db):
    recolour = import_module("apps.core.migrations.0010_marque_bleu_uniforme").recolour
    PlatformSettings.load()
    PlatformSettings.objects.update(primary_color="#0B5FCC", accent_color="#F2B632")
    recolour(django_apps, None)
    platform = PlatformSettings.load()
    assert (platform.primary_color, platform.accent_color) == ("#1A2F80", "#FFA81E")
    PlatformSettings.objects.update(primary_color="#1F3A2E", accent_color="#F2B632")
    recolour(django_apps, None)
    platform = PlatformSettings.load()
    assert (platform.primary_color, platform.accent_color) == ("#1F3A2E", "#FFA81E")


def test_uploaded_icon_and_logo_are_served(client, db):
    platform = PlatformSettings.load()
    platform.icon = png(1024, 1024)
    platform.full_clean()
    platform.save()

    manifest = client.get("/api/platform/manifest/gestion/", HTTP_HOST="localhost").json()
    assert manifest["icons"] == [
        {"src": platform.icon_url, "sizes": "1024x1024", "type": "image/png"}
    ]
    icon = client.get(platform.icon_url, HTTP_HOST="alpha.localhost")
    assert (icon.status_code, icon["Content-Type"]) == (200, "image/png")
    assert client.get("/api/platform/logo/").status_code == 404  # pas de logo : le symbole


def test_platform_name_is_not_written_in_server_texts():
    """Règle 9 : le nom vient des paramètres ; ni traduction ni gabarit ne l'écrit."""
    found = []
    po = Path(settings.BASE_DIR, "locale/fr/LC_MESSAGES/django.po").read_text()
    for entry in po.split("\n\n")[1:]:  # après l'en-tête du fichier
        texts = "".join(re.findall(r'^(?:msgid|msgstr)?\s*"(.*)"$', entry, re.M))
        if INITIAL_NAME in texts:
            found.append(texts[:80])
    for template in Path(settings.BASE_DIR, "apps").glob("*/templates/**/*.html"):
        if INITIAL_NAME in template.read_text():
            found.append(str(template))
    assert found == []


def test_django_admin_only_shows_the_identity(admin_client):
    """Dépannage seulement : l'identité se modifie dans la console, qui la note au journal."""
    change = "/admin/core/platformsettings/1/change/"
    assert admin_client.get("/admin/core/platformsettings/").url == change
    assert admin_client.get(change).status_code == 200
    assert admin_client.get("/admin/core/platformsettings/add/").status_code == 403

    response = admin_client.post(change, {"name": "Lumière", "short_name": "Lumière"})

    assert response.status_code == 403
    assert PlatformSettings.load().name == INITIAL_NAME
