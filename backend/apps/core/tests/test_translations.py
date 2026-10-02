"""Textes du serveur en français (I2) : catalogue complet et compilé ; le serveur suit la langue
choisie dans l'interface."""

import ast
import gettext
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import translation

FRENCH = Path(settings.BASE_DIR) / "locale" / "fr" / "LC_MESSAGES"


def french_catalog():
    """Entrées de `django.po` : {"msgid", "msgstr" (ou "msgstr[0]"…), "msgctxt", "fuzzy"…}."""
    entries, current, key = [], {}, None
    for line in [*(FRENCH / "django.po").read_text().splitlines(), ""]:
        if not line.strip():
            if current.get("msgid"):
                entries.append(current)
            current = {}
        elif line.startswith("#,"):
            current["fuzzy"] = "fuzzy" in line
        elif line.startswith("msg"):
            key, text = line.split(" ", 1)
            current[key] = ast.literal_eval(text)
        elif line.startswith('"'):
            current[key] += ast.literal_eval(line)
    return entries


def test_every_server_text_has_a_compiled_french_translation():
    compiled = gettext.GNUTranslations((FRENCH / "django.mo").open("rb"))

    entries = french_catalog()

    assert len(entries) > 800
    assert [entry["msgid"] for entry in entries if entry.get("fuzzy")] == []
    untranslated = [
        entry["msgid"]
        for entry in entries
        if not all(text for key, text in entry.items() if key.startswith("msgstr"))
    ]
    assert untranslated == []
    # `make messages` compile après la traduction : le `.mo` lu par Django a les mêmes textes.
    stale = [
        entry["msgid"]
        for entry in entries
        if "msgstr" in entry
        and "msgctxt" not in entry
        and compiled.gettext(entry["msgid"]) != entry["msgstr"]
    ]
    assert stale == []


@pytest.mark.parametrize(("chosen", "browser"), [("fr", "en"), ("en", "fr")])
def test_server_texts_follow_the_language_chosen_in_the_interface(db, client, chosen, browser):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = chosen

    response = client.get(
        "/api/school/", HTTP_HOST="inconnue.localhost", HTTP_ACCEPT_LANGUAGE=browser
    )

    with translation.override(chosen):
        expected = str(translation.gettext("There is no school at this address."))
    assert response.status_code == 404
    assert response.json()["detail"] == expected
