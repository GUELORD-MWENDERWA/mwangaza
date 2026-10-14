"""Site public de la plateforme (`apps/core/site.py`) : identité lue dans les paramètres, auteur,
fichiers pour les robots, accès à l'espace d'une école."""

import json
import re

from django.conf import settings

from apps.core.models import PlatformSettings


def structured_data(html: str) -> dict:
    found = re.search(r'<script type="application/ld\+json">(.*?)</script>', html)
    graph = json.loads(found.group(1))
    return {node["@type"]: node for node in graph["@graph"]}


def test_home_page_uses_the_platform_identity_and_names_the_author(client, db):
    platform = PlatformSettings.load()
    platform.name, platform.support_phone = "Lumière", "+243970000001"
    platform.save()

    french = client.get("/").content.decode()
    assert "<title>Lumière — logiciel de gestion scolaire" in french
    assert '<link rel="canonical" href="http://testserver/">' in french
    assert 'hreflang="en" href="http://testserver/en/"' in french
    assert 'href="https://wa.me/243970000001"' in french
    data = structured_data(french)
    assert data["Organization"]["name"] == data["SoftwareApplication"]["name"] == "Lumière"
    assert data["Organization"]["contactPoint"]["telephone"] == "+243970000001"
    assert data["Person"]["name"] == settings.SOFTWARE_AUTHOR
    # L'auteur dans la balise meta seulement ; le pied de page porte le titulaire des droits.
    assert f'<meta name="author" content="{settings.SOFTWARE_AUTHOR}">' in french
    assert f"{settings.SOFTWARE_COPYRIGHT}. Tous droits réservés." in french
    assert "Conçu et développé" not in french
    assert len(data["FAQPage"]["mainEntity"]) == 6

    english = client.get("/en/").content.decode()
    assert '<html lang="en">' in english
    assert "<title>Lumière — school management software" in english
    assert structured_data(english)["WebPage"]["inLanguage"] == "en"


def test_files_for_search_engines_and_assistants(client, db):
    robots = client.get("/robots.txt").content.decode()
    assert "Sitemap: http://testserver/sitemap.xml" in robots
    sitemap = client.get("/sitemap.xml").content.decode()
    assert "<loc>http://testserver/</loc>" in sitemap
    assert "<loc>http://testserver/en/</loc>" in sitemap
    llms = client.get("/llms.txt")
    assert llms["Content-Type"].startswith("text/markdown")
    assert settings.SOFTWARE_AUTHOR in llms.content.decode()


def test_school_space_leads_to_the_school_address_only(client, db):
    response = client.get("/ecole/", {"code": " Itig "})
    assert response["Location"] == settings.SCHOOL_URL.format(code="itig") + "/app/"
    # Code mal formé (ou adresse d'un autre site) : retour au formulaire.
    for code in ["", "evil.com/x", "-itig", "a b"]:
        assert client.get("/ecole/", {"code": code})["Location"] == "/#ecole"
