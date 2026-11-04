"""Centre d'aide (AIDE.1) : textes du dépôt complets dans les deux langues ; Markdown sans HTML de
l'auteur (captures et liens inconnus ignorés) ; recherche sans accents, titre d'abord ; site sans
la console ; API publique du panneau « Aide » ; aide de la console réservée à son équipe."""

import pytest
from django.core.cache import cache
from PIL import Image

from apps.core import help_center, markdown
from tests.factories import UserFactory

FILES = {
    "fr/gestion/take-payment.md": (
        "title: Encaisser un paiement\nslug: encaisser-un-paiement\n"
        "summary: Recevoir l'argent d'un parent et remettre le reçu.\n"
        "groups: cash\nroles: cashier, accountant\norder: 10\nupdated: 2026-11-04\n\n"
        "## Étapes\n\n1. Ouvrez **Caisse**.\n2. Cliquez sur <b>Encaisser</b>.\n\n"
        "![Légende <script>](capture:caisse)\n![Rien](capture:absente)\n\n"
        "> **À savoir.** Erreur ? [Demandez l'annulation](aide:cancel-payment), "
        "[ou ceci](aide:inconnu).\n\n---\n\n## Questions fréquentes\n\nInternet coupé ?\n"
    ),
    "en/gestion/take-payment.md": (
        "title: Take a payment\nslug: take-a-payment\nsummary: Receive money.\ngroups: cash\n\n"
        "1. Open **Cash desk**.\n"
    ),
    "fr/gestion/cancel-payment.md": (
        "title: Demander une annulation\nsummary: Corriger une erreur de caisse.\ngroups: cash\n\n"
        "Le reçu reste au registre.\n"
    ),
    "fr/gestion/sign-in.md": (
        "title: Se connecter\nsummary: Ouvrir la Gestion.\ngroups: start, direction\n\nBienvenue.\n"
    ),
    "fr/portail/receipts.md": (
        "title: Voir les reçus\nsummary: Chaque paiement de votre enfant.\ngroups: parents\n\n"
        "Ouvrez la fiche.\n"
    ),
    "fr/console/schools.md": (
        "title: Ouvrir une école\nsummary: Pour l'équipe.\ngroups: console\n\nConfidentiel.\n"
    ),
    "fr/whats-new/2026-10-30.md": "Nouvelle apparence.\n\n[gestion]\n- Plus lisible.\n",
    "fr/whats-new/2026-11-04.md": (
        "Un bouton « Aide ».\n\n[gestion]\n- Un bouton « Aide » partout.\n\n[portail]\n- Aide.\n"
    ),
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Textes et une capture d'essai à la place de ceux du dépôt."""
    for name, text in FILES.items():
        (tmp_path / "help" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "help" / name).write_text(text)
    (tmp_path / "aide" / "fr").mkdir(parents=True)
    Image.new("RGB", (40, 30), "white").save(tmp_path / "aide" / "fr" / "caisse.webp")
    monkeypatch.setattr(help_center, "HELP_DIR", tmp_path / "help")
    monkeypatch.setattr(help_center, "CAPTURES_DIR", tmp_path / "aide")
    cache.clear()
    return tmp_path / "help"


def test_repository_texts_complete_in_both_languages():
    """Chaque article du dépôt se lit (en-tête, rubriques, rôles, adresses uniques) et existe en
    français et en anglais, dans la même application et la même rubrique."""
    lib = help_center.library()
    fr, en = lib.articles["fr"], lib.articles["en"]
    assert fr, "aucun article"
    assert set(fr) == set(en)
    for key, article in fr.items():
        assert (en[key].app, en[key].groups) == (article.app, article.groups), key
    assert [e.day for e in lib.entries["fr"]] == [e.day for e in lib.entries["en"]]


def test_header_errors_are_refused(tmp_path):
    bad = tmp_path / "fr" / "gestion" / "x.md"
    bad.parent.mkdir(parents=True)
    for header in ("title: X\nsummary: Y\ngroups: inconnue", "title: X\ngroups: cash", "nom X"):
        bad.write_text(f"{header}\n\nTexte.\n")
        help_center._load.cache_clear()
        with pytest.raises(ValueError):
            help_center._load(tmp_path)


def test_markdown_of_an_article_writes_no_author_html(library):
    found = help_center.article("fr", "take-payment")
    html = help_center.render(found, help_center.site_links("fr"))
    assert "<ol><li>Ouvrez <strong>Caisse</strong>.</li>" in html
    assert "&lt;b&gt;Encaisser&lt;/b&gt;" in html and "<b>" not in html
    assert 'alt="Légende &lt;script&gt;" width="40" height="30"' in html
    assert "<script" not in html and "absente" not in html  # capture inconnue : rien
    assert '<div class="tip"><strong>À savoir.</strong>' in html
    assert '<a href="/aide/cancel-payment/" data-help="cancel-payment">' in html
    assert "ou ceci" in html and "inconnu" not in html  # article inconnu : texte sans lien
    assert "Questions fréquentes" in html
    guide = help_center.render(found, {}, questions=False)
    assert "Questions fréquentes" not in guide and "<a " not in guide


def test_search_without_accents_title_first_and_escaped(library):
    rows = help_center.search("fr", "RECU")
    # Le titre d'abord, puis le résumé, puis le texte.
    assert [r["article"].key for r in rows] == ["receipts", "take-payment", "cancel-payment"]
    assert rows[0]["title"] == "Voir les <mark>reçus</mark>"
    assert help_center.search("fr", "reçu caisse")[0]["article"].key == "take-payment"
    assert help_center.search("fr", "confidentiel") == []  # la console n'est pas sur le site
    assert help_center.highlight("<i>reçu</i>", ["recu"]) == "&lt;i&gt;<mark>reçu</mark>&lt;/i&gt;"


@pytest.mark.django_db
def test_site_pages_sitemap_and_console_kept_out(client, library):
    home = client.get("/aide/").content.decode()
    assert "/aide/encaisser-un-paiement/" in home and "/aide/receipts/" in home
    assert "Ouvrir une école" not in home and "Un bouton « Aide »." in home
    page = client.get("/aide/encaisser-un-paiement/").content.decode()
    assert 'hreflang="en" href="http://testserver/en/help/take-a-payment/"' in page
    assert 'aria-current="page">Encaisser un paiement' in page and "Caissier" in page
    assert client.get("/aide/schools/").status_code == 404
    assert client.get("/en/help/take-a-payment/").status_code == 200
    found = client.get("/aide/recherche/", {"q": "reçu"}).content.decode()
    assert "noindex" in found and "Voir les <mark>reçus</mark>" in found
    assert client.get("/aide/recherche/", {"q": "x"}).status_code == 302
    news = client.get("/aide/nouveautes/").content.decode()
    assert news.index("partout") < news.index("Plus lisible")  # la plus récente d'abord
    sitemap = client.get("/sitemap.xml").content.decode()
    assert "/aide/encaisser-un-paiement/</loc>" in sitemap and "/en/help/</loc>" in sitemap
    assert "/aide/schools/" not in sitemap
    assert "/aide/receipts/" in client.get("/llms.txt").content.decode()


@pytest.mark.django_db
def test_public_api_of_the_help_panel(client, library):
    rows = client.get("/api/help/gestion/", {"search": "reçu", "lang": "fr"}).json()["articles"]
    assert [r["key"] for r in rows] == ["take-payment", "cancel-payment"]
    assert "<mark>reçu</mark>" in rows[0]["excerpt_html"]
    data = client.get("/api/help/gestion/take-payment/", {"lang": "fr"})
    assert data["Cache-Control"] == "public, max-age=3600"
    data = data.json()
    assert data["roles"] == ["Caissier", "Comptable"] and data["minutes"] == 1
    assert 'href="http://localhost:8000/aide/cancel-payment/"' in data["html"]
    assert [r["key"] for r in data["related"]] == ["cancel-payment"]
    assert client.get("/api/help/portail/take-payment/").status_code == 404
    assert client.get("/api/help/console/").status_code == 404
    latest = client.get("/api/help/whats-new/", {"app": "portail", "lang": "fr"}).json()
    assert latest["day"] == "2026-11-04" and "<li>Aide.</li>" in latest["html"]
    assert client.get("/api/help/whats-new/", {"app": "console"}).status_code == 404


@pytest.mark.django_db
def test_console_help_only_for_the_platform_team(api, library, cashier):
    team = UserFactory(is_platform_admin=True, platform_roles=["support"])
    assert api(team, host="admin.localhost").get("/api/console/help/schools/").status_code == 200
    assert api(team, host="admin.localhost", mfa=False).get("/api/console/help/").status_code == 403
    assert api(cashier, host="admin.localhost").get("/api/console/help/").status_code == 403
    assert api(team).get("/api/console/help/").status_code == 404  # pas l'adresse de la console


def test_markdown_lists_and_tips_keep_news_format():
    html = markdown.render("- un\n- deux\n1. trois\n> note\nfin")
    assert html == (
        "<ul><li>un</li><li>deux</li></ul>\n<ol><li>trois</li></ol>\n"
        '<div class="tip">note</div>\n<p>fin</p>'
    )


@pytest.mark.django_db
def test_pdf_guide_from_the_same_articles(library):
    """Le guide de la Gestion : sans questions fréquentes ni article d'une autre application, les
    liens entre articles du guide renvoient à leur page, la capture est dans le fichier."""
    from io import BytesIO

    from pypdf import PdfReader

    from apps.core import printing
    from apps.core.management.commands.help_guides import guide_html

    html = guide_html("gestion", "fr")
    assert 'href="#cancel-payment" data-help="cancel-payment"' in html
    assert "data:image/webp;base64," in html
    assert "Questions fréquentes" not in html and "Voir les reçus" not in html
    assert guide_html("portail", "en") is None
    pages = PdfReader(BytesIO(printing.to_pdf(html))).pages
    assert len(pages) == 4  # couverture, sommaire, « Premiers pas », « Caisse »
    assert "(page 4)" in pages[3].extract_text()
