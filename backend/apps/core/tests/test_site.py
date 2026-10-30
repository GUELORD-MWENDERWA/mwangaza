"""Site public de la plateforme (`apps/core/site.py`) : identité lue dans les paramètres, auteur,
chaque page dans les deux langues, chiffres de la plateforme, fichiers pour les robots, accès à
l'espace d'une école ; visibilité (WEB.1c) : données structurées, image de partage."""

import json
import re
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from PIL import Image

from apps.core import site
from apps.core.models import PlatformSettings


def structured_data(html: str) -> dict:
    """Nœuds par type ; « Organization » : la plateforme, « Publisher » : son éditeur."""
    found = re.search(r'<script type="application/ld\+json">(.*?)</script>', html)
    graph = json.loads(found.group(1))["@graph"]
    nodes = {node["@type"]: node for node in graph if node["@type"] != "Organization"}
    nodes["Organization"], nodes["Publisher"] = [n for n in graph if n["@type"] == "Organization"]
    return nodes


def test_home_page_uses_the_platform_identity_and_names_the_author(client, db):
    platform = PlatformSettings.load()
    platform.name, platform.site_name = "Lumière", "Lumière École"
    platform.support_phone = "+243970000001"
    platform.save()

    french = client.get("/").content.decode()
    # Le nom pour la recherche dans le titre ; la marque : le nom en gras, la suite à côté.
    assert "<title>Lumière École — logiciel de gestion scolaire à Goma" in french
    assert "<b>Lumière</b><span>École</span>" in french
    assert '<link rel="canonical" href="http://testserver/">' in french
    assert 'hreflang="en" href="http://testserver/en/"' in french
    assert 'href="https://wa.me/243970000001"' in french
    data = structured_data(french)
    assert data["Organization"]["name"] == data["SoftwareApplication"]["name"] == "Lumière École"
    assert data["WebSite"]["alternateName"] == "Lumière"
    assert data["Organization"]["contactPoint"]["telephone"] == "+243970000001"
    assert data["Person"]["name"] == settings.SOFTWARE_AUTHOR
    assert data["Person"]["sameAs"] == settings.SOFTWARE_AUTHOR_SAME_AS
    # L'éditeur (titulaire des droits) publie le site et le logiciel.
    publisher = data["Publisher"]
    assert (publisher["name"], publisher["url"]) == (
        settings.SOFTWARE_COPYRIGHT,
        settings.SOFTWARE_COPYRIGHT_URL,
    )
    assert data["SoftwareApplication"]["publisher"] == {"@id": publisher["@id"]}
    assert data["SoftwareApplication"]["applicationCategory"] == "EducationalApplication"
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
    assert "<title>Lumière École — school management software in Goma, DRC</title>" in english
    assert structured_data(english)["WebPage"]["inLanguage"] == "en"


def test_every_page_answers_in_both_languages_and_points_to_the_other(client, db):
    for key, paths in site.PAGES.items():
        for lang, other in (("fr", "en"), ("en", "fr")):
            response = client.get(paths[lang])
            html = response.content.decode()
            assert response.status_code == 200, (key, lang)
            # La page Démonstration porte le jeton CSRF de son formulaire : jamais gardée.
            cached = "no-store" if key == "contact" else "public, max-age=3600"
            assert cached in response["Cache-Control"], key
            assert f'<html lang="{lang}">' in html
            assert f'hreflang="{other}" href="http://testserver{paths[other]}"' in html
            assert "{%" not in html and "{{" not in html  # gabarit mal fermé
            # Données structurées sur chaque page ; fil d'Ariane jusqu'à la page (sauf l'accueil).
            data = structured_data(html)
            url = f"http://testserver{paths[lang]}"
            assert (data["WebPage"]["@id"], data["WebPage"]["inLanguage"]) == (url, lang)
            crumbs = data.get("BreadcrumbList", {}).get("itemListElement", [])
            assert [crumb["item"] for crumb in crumbs] == (
                [] if key == "home" else [f"http://testserver{site.PAGES['home'][lang]}", url]
            )
            assert re.search(
                rf'<meta property="og:image" content="http://testserver/partage/{key}-{lang}\.jpg\?v=\d+">',
                html,
            )
    # Questions fréquentes : l'accueil et les parents, dans la page et ses données.
    assert (
        len(structured_data(client.get("/parents/").content.decode())["FAQPage"]["mainEntity"]) == 4
    )
    assert client.get("/confidentialite/")["Location"] == "/mentions-legales/#confidentialite"
    sitemap = client.get("/sitemap.xml").content.decode()
    for key, paths in site.PAGES.items():
        assert f"<loc>http://testserver{paths['fr']}</loc>" in sitemap
        assert f"<loc>http://testserver{paths['en']}</loc>" in sitemap
        # Images de chaque page : des fichiers qui existent (une capture renommée se verrait).
        for image in site.PAGE_IMAGES[key]:
            assert (site.STATIC_SITE / image).is_file(), image
            assert f"<image:loc>http://testserver/static/core/site/{image}</image:loc>" in sitemap


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


def test_share_image_of_each_page_follows_the_identity(client, db):
    cache.clear()
    response = client.get("/partage/parents-fr.jpg")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    image = Image.open(BytesIO(response.content))
    assert image.size == (1200, 630)
    assert len(response.content) < 300_000  # aperçu de WhatsApp
    # Dessinée une fois, puis lue en cache ; l'identité change : nouvelle adresse, nouvelle image.
    before = site._version(PlatformSettings.load())
    assert cache.get(f"site:share:parents:fr:testserver:{before}") == response.content
    platform = PlatformSettings.load()
    platform.accent_color = "#FFD166"
    platform.save()
    assert site._version(PlatformSettings.load()) != before
    assert client.get("/partage/parents-fr.jpg").content != response.content
    # Pas de page inconnue ni d'autre langue.
    for path in ["/partage/evil-fr.jpg", "/partage/home-de.jpg"]:
        assert client.get(path).status_code == 404
    cache.clear()
