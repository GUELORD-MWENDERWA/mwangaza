"""Site public de la plateforme (`apps/core/site.py`) : identité lue dans les paramètres, auteur,
chaque page dans les deux langues, chiffres de la plateforme, fichiers pour les robots, accès à
l'espace d'une école."""

import json
import re

from django.conf import settings
from django.core.cache import cache

from apps.core import site
from apps.core.models import PlatformSettings
from apps.schools.models import School
from tests.factories import SchoolFactory


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
    copyright = f'<a href="{settings.SOFTWARE_COPYRIGHT_URL}">{settings.SOFTWARE_COPYRIGHT}</a>'
    assert f"{copyright}. Tous droits réservés." in french
    assert "Conçu et développé" not in french
    assert len(data["FAQPage"]["mainEntity"]) == 7
    # Jamais de citation inventée : sans les vrais mots d'une école, pas de bloc de citation.
    assert "<blockquote>" not in french

    english = client.get("/en/").content.decode()
    assert '<html lang="en">' in english
    assert "<title>Lumière — school management software" in english
    assert structured_data(english)["WebPage"]["inLanguage"] == "en"


def test_every_page_answers_in_both_languages_and_points_to_the_other(client, db):
    for key, paths in site.PAGES.items():
        for lang, other in (("fr", "en"), ("en", "fr")):
            response = client.get(paths[lang])
            html = response.content.decode()
            assert response.status_code == 200, (key, lang)
            assert response["Cache-Control"] == "public, max-age=3600"
            assert f'<html lang="{lang}">' in html
            assert f'hreflang="{other}" href="http://testserver{paths[other]}"' in html
            assert "{%" not in html and "{{" not in html  # gabarit mal fermé
    assert client.get("/confidentialite/")["Location"] == "/mentions-legales/#confidentialite"
    sitemap = client.get("/sitemap.xml").content.decode()
    for paths in site.PAGES.values():
        assert f"<loc>http://testserver{paths['fr']}</loc>" in sitemap
        assert f"<loc>http://testserver{paths['en']}</loc>" in sitemap


def test_platform_figures_count_live_schools_only_and_stay_hidden_below_five(client, db):
    cache.delete(site.STATS_CACHE)
    for _ in range(4):
        SchoolFactory(environment=School.Environment.LIVE)
    # Essai, démonstration et espace arrêté ne comptent pas (A7).
    SchoolFactory(environment=School.Environment.TEST)
    SchoolFactory(environment=School.Environment.DEMO)
    SchoolFactory(environment=School.Environment.LIVE, status=School.Status.STOPPED)
    assert site.platform_stats() == []
    assert 'class="nums' not in client.get("/").content.decode()

    cache.delete(site.STATS_CACHE)
    SchoolFactory(environment=School.Environment.LIVE)
    figures = site.platform_stats()
    assert figures[0][1] == 5
    assert [number for _value, number, _label in figures[1:]] == [0, 0, 0]
    assert 'data-count="5"' in client.get("/").content.decode()
    cache.delete(site.STATS_CACHE)


def test_files_for_search_engines_and_assistants(client, db):
    robots = client.get("/robots.txt").content.decode()
    assert "Sitemap: http://testserver/sitemap.xml" in robots
    llms = client.get("/llms.txt")
    assert llms["Content-Type"].startswith("text/markdown")
    assert settings.SOFTWARE_AUTHOR in llms.content.decode()


def test_find_my_school_leads_to_the_school_address_only(client, db):
    expected = settings.SCHOOL_URL.format(code="itig") + "/app/"
    assert client.get("/trouver-mon-ecole/", {"code": " Itig "})["Location"] == expected
    # Ancienne adresse du formulaire : même règle.
    assert client.get("/ecole/", {"code": "itig"})["Location"] == expected
    # Code mal formé (ou adresse d'un autre site) : la même page, l'erreur, rien d'indexé.
    for code in ["", "evil.com/x", "-itig", "a b"]:
        response = client.get("/en/find-my-school/", {"code": code})
        html = response.content.decode()
        assert response.status_code == 200
        assert 'aria-invalid="true"' in html
        assert '<meta name="robots" content="noindex, follow">' in html
