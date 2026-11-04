"""Guides PDF du centre d'aide (AIDE.1) : un par application et par langue, A4, tirés des mêmes
articles que le site (`help_center.py`), sans les questions fréquentes. Couverture à l'identité
de la plateforme (nom, logo, couleur), sommaire avec les pages, une rubrique par chapitre ; un lien
vers un article du guide devient « (page N) ». `make guide` les écrit dans `docs/guide/`."""

import base64
import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.core import help_center, printing
from apps.core.models import PlatformSettings


def _data_uri(path: Path, data: bytes | None = None) -> str:
    kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    raw = data if data is not None else path.read_bytes()
    return f"data:{kind};base64,{base64.b64encode(raw).decode()}"


def _logo(platform) -> str | None:
    """Le logo de la plateforme en `data:` (le PDF ne charge aucun fichier)."""
    if not platform.logo:
        return None
    with platform.logo.open("rb") as file:
        return _data_uri(Path(platform.logo.name), file.read())


def guide_html(app: str, lang: str) -> str | None:
    """Le guide en HTML pour WeasyPrint ; aucun article pour cette application : rien."""
    rows = help_center.articles(lang, (app,))
    if not rows:
        return None
    platform = PlatformSettings.load()
    links = {a.key: f"#{a.key}" for a in rows}
    shots = {
        name: {**shot, "url": _data_uri(help_center.CAPTURES_DIR / lang / f"{name}.webp")}
        for name, shot in help_center.captures(lang).items()
    }
    with translation.override(lang):
        chapters = [
            {
                "key": key,
                "label": label,
                "articles": [
                    {"article": a, "html": help_center.render(a, links, shots, questions=False)}
                    for a in rows
                    if a.group == key
                ],
            }
            for key, (label, _text) in help_center.GROUPS.items()
            if any(a.group == key for a in rows)
        ]
        return render_to_string(
            "core/help/guide.html",
            {
                "lang": lang,
                "platform": platform,
                "logo": _logo(platform),
                "title": _("User guide: %(app)s") % {"app": help_center.APPS[app]},
                "chapters": chapters,
                "help_url": help_center.site_url() + help_center.HOME[lang],
                "today": timezone.localdate(),
            },
        )


class Command(BaseCommand):
    help = "Guides PDF du centre d'aide, un par application et par langue (docs/guide/)."

    def add_arguments(self, parser):
        parser.add_argument("--app", action="append", choices=list(help_center.APPS))
        parser.add_argument("--lang", action="append", choices=list(help_center.LANGS))
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR).parent / "docs" / "guide"))

    def handle(self, *args, **options):
        # WeasyPrint et fontTools racontent chaque étape : seulement les avertissements.
        for name in ("weasyprint", "fontTools"):
            logging.getLogger(name).setLevel(logging.WARNING)
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        for app in options["app"] or help_center.APPS:
            for lang in options["lang"] or help_center.LANGS:
                html = guide_html(app, lang)
                if html is None:
                    self.stdout.write(f"{app} ({lang}) : aucun article, pas de guide")
                    continue
                target = out / f"guide-{app}-{lang}.pdf"
                target.write_bytes(printing.to_pdf(html))
                self.stdout.write(f"{target} ({target.stat().st_size // 1024} Kio)")
