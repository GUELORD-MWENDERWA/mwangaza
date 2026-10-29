"""Identité de la plateforme dans la console (5.2.2) : réservée au super-admin à l'adresse de la
console ; chaque changement va dans le journal de la plateforme, qui ne se modifie pas."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction

from apps.audit.models import ImmutableError, PlatformAuditLog
from apps.core.models import PlatformSettings
from apps.core.tests.test_platform import INITIAL_NAME, png

pytestmark = pytest.mark.django_db

CONSOLE = "admin.localhost"
IDENTITY = "/api/console/platform/"
ICON = "/api/console/platform/icon/"
LOGO = "/api/console/platform/logo/"
SVG = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>'


def upload(client, url: str, field: str, file: SimpleUploadedFile):
    return client.client.post(url, {field: file}, HTTP_HOST=client.host)


def test_only_the_platform_admin_changes_the_identity_at_the_console(api, platform_admin, head):
    rename = {"name": "Lumière"}
    assert api(None, host=CONSOLE).patch(IDENTITY, rename).status_code == 403
    assert api(head, host=CONSOLE).patch(IDENTITY, rename).status_code == 403
    assert api(platform_admin, host=CONSOLE, mfa=False).patch(IDENTITY, rename).status_code == 403
    assert upload(api(head, host=CONSOLE), ICON, "icon", png(512, 512)).status_code == 403
    assert api(head, host=CONSOLE).delete(LOGO).status_code == 403
    # Ailleurs qu'à l'adresse de la console, ces points d'API n'existent pas.
    for host in ("alpha.localhost", "parents.localhost", "localhost"):
        assert api(platform_admin, host=host).patch(IDENTITY, rename).status_code == 404
    assert PlatformSettings.load().name == INITIAL_NAME
    assert not PlatformAuditLog.objects.exists()

    assert api(platform_admin, host=CONSOLE).get(IDENTITY).status_code == 200


def test_each_change_is_journaled_once_with_only_what_changed(api, platform_admin, client):
    console = api(platform_admin, host=CONSOLE)
    changes = {
        "name": "Lumière",
        "site_name": "Lumière École",
        "primary_color": "#1e3a8a",
        "support_phone": "0970000000",
    }

    data = console.patch(IDENTITY, changes).json()

    assert (data["name"], data["primary_color"], data["support_phone"]) == (
        "Lumière",
        "#1E3A8A",
        "+243970000000",
    )
    public = client.get("/api/platform/", HTTP_HOST="alpha.localhost").json()
    assert (public["name"], public["site_name"]) == ("Lumière", "Lumière École")
    log = PlatformAuditLog.objects.get()
    assert (log.action, log.actor, log.entity_label) == (
        "platform.updated",
        platform_admin,
        "Lumière",
    )
    assert log.before == {
        "name": INITIAL_NAME,
        "site_name": "Mwangaza School",
        "primary_color": "#1A2F80",
        "support_phone": "",
    }
    assert log.after == {
        "name": "Lumière",
        "site_name": "Lumière École",
        "primary_color": "#1E3A8A",
        "support_phone": "+243970000000",
    }
    assert [entry["action"] for entry in data["history"]] == ["platform.updated"]
    # Les mêmes valeurs encore : rien de nouveau au journal.
    console.patch(IDENTITY, changes)
    assert PlatformAuditLog.objects.count() == 1


def test_unreadable_colour_and_wrong_files_are_refused_without_change(api, platform_admin):
    console = api(platform_admin, host=CONSOLE)

    refused = console.patch(IDENTITY, {"name": "Lumière", "accent_color": "#0E5C6B"})
    assert refused.status_code == 400
    assert set(refused.json()["fields"]) == {"accent_color"}
    assert upload(console, ICON, "icon", png(600, 500)).status_code == 400
    assert upload(console, ICON, "icon", png(4096, 4096)).status_code == 400
    # SVG : permis au super-admin seulement, et jamais avec de quoi exécuter du code.
    for svg in (
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        b'<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"/></svg>',
    ):
        refused = upload(console, LOGO, "logo", SimpleUploadedFile("logo.svg", svg))
        assert refused.status_code == 400
        assert refused.json()["fields"]["logo"][0]["code"] == "logo_type"

    platform = PlatformSettings.load()
    assert (platform.name, platform.icon.name, platform.logo.name) == (INITIAL_NAME, "", "")
    assert not PlatformAuditLog.objects.exists()


def test_new_icon_and_logo_replace_the_old_files(
    api, platform_admin, django_capture_on_commit_callbacks
):
    console = api(platform_admin, host=CONSOLE)
    with django_capture_on_commit_callbacks(execute=True):
        first = upload(console, ICON, "icon", png(512, 512)).json()["icon"]
    first_file = PlatformSettings.load().icon
    with django_capture_on_commit_callbacks(execute=True):
        second = upload(console, ICON, "icon", png(1024, 1024)).json()["icon"]
        logo = upload(console, LOGO, "logo", SimpleUploadedFile("logo.svg", SVG)).json()["logo"]

    assert first != second and logo.startswith("/api/platform/logo/?v=")
    assert not first_file.storage.exists(first_file.name)  # l'ancienne icône est effacée
    with django_capture_on_commit_callbacks(execute=True):
        data = console.delete(ICON).json()
    assert data["icon"] is None and data["logo"] == logo
    assert [entry["action"] for entry in data["history"]] == [
        "platform.icon_changed",
        "platform.logo_changed",
        "platform.icon_changed",
        "platform.icon_changed",
    ]
    assert data["history"][0]["after"] == {"icon": False}


def test_the_platform_log_cannot_be_changed_even_in_sql(api, platform_admin):
    api(platform_admin, host=CONSOLE).patch(IDENTITY, {"short_name": "Lumi"})
    log = PlatformAuditLog.objects.get()

    with pytest.raises(ImmutableError):
        log.save()
    with pytest.raises(ImmutableError):
        PlatformAuditLog.objects.update(entity_label="Autre")
    for sql in (
        "UPDATE audit_platformauditlog SET entity_label = 'Autre'",
        "DELETE FROM audit_platformauditlog",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql)
    assert PlatformAuditLog.objects.get().after == {"short_name": "Lumi"}
