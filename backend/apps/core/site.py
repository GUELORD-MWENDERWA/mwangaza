"""Site public de la plateforme (domaine nu, début de WEB.1) : une page de présentation en
français (`/`) et en anglais (`/en/`), lisible sans JavaScript par les moteurs de recherche et les
assistants (IA), et ses fichiers pour les robots (`robots.txt`, `sitemap.xml`, `llms.txt`).

Nom, logo, icône, couleurs et contact viennent de l'identité de la plateforme (règle 9) ; l'auteur
du logiciel, des réglages. Les espaces privés (écoles, portail, console, vérification des reçus)
ne sont jamais indexés (`infra/routes.caddy`). Une seule lecture en base par page, mise en cache
une heure par les navigateurs."""

import json
import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone, translation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from apps.accounts.phone import format_phone
from apps.core.models import PlatformSettings
from apps.core.money import format_amount

PATHS = {"fr": "/", "en": "/en/"}
OG_LOCALES = {"fr": "fr_FR", "en": "en_US"}
# Code d'une école = son sous-domaine (lettres minuscules, chiffres, tirets).
SCHOOL_CODE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
public = cache_control(public=True, max_age=3600)

# Icônes des fonctions (tracés sur 24 px, comme l'application).
ICONS = {
    "students": (
        "M16 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8"
        "M22 20v-1.5a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"
    ),
    "fees": "M3 6h18v12H3zM3 10h18M7 15h3",
    "cash": "M6 2h12v20l-3-2-3 2-3-2-3 2zM9 7h6M9 11h6M9 15h3",
    "offline": "M2 9.5a15 15 0 0 1 20 0M5 13a10 10 0 0 1 14 0M8.5 16.5a5 5 0 0 1 7 0M12 20h.01",
    "unpaid": "M3 3v18h18M7 15l4-4 3 3 5-6",
    "parents": "M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zM11 18h2",
    "security": "M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5zM9 12l2 2 4-4",
    "news": "M3 11l14-6v14L3 13zM7 13v5a2 2 0 0 0 4 0v-3.5",
}


def _site(request: HttpRequest) -> str:
    """Adresse du site (https derrière Caddy, `SECURE_PROXY_SSL_HEADER`)."""
    return request.build_absolute_uri("/").rstrip("/")


def _texts(name: str) -> dict:
    """Textes de la page dans la langue active ; les mêmes servent aux données structurées et à
    `llms.txt` (une seule source)."""
    values = {"name": name}
    return {
        "title": _("%(name)s — school management software for schools in the DRC") % values,
        "description": _(
            "Students, school fees, cash desk and receipts, unpaid fees and a parent portal: one "
            "app that works even without internet. Made in Goma for schools in the DRC."
        ),
        "eyebrow": _("For schools in the DRC · made in Goma"),
        "headline": _("The school management software that works even without internet"),
        "lead": _(
            "%(name)s brings students, school fees, the cash desk and receipts, unpaid fees and "
            "the parent portal together in one app. The cash desk keeps working when the internet "
            "is down; everything syncs as soon as the network is back."
        )
        % values,
        "features": [
            (
                ICONS["students"],
                _("Students and enrolment"),
                _(
                    "Excel import with an error report, registration form with the family code, "
                    "families and siblings, class lists in PDF and Excel."
                ),
            ),
            (
                ICONS["fees"],
                _("Fees in dollars and francs"),
                _(
                    "Fee scales by level, option or class, in USD or FC, split into instalments; "
                    "discounts with a reason; the exchange rate of the school year."
                ),
            ),
            (
                ICONS["cash"],
                _("Cash desk and receipts"),
                _(
                    "Full or partial payments, a receipt printed at once (58 or 80 mm thermal, or "
                    "A4) with a verification QR code, and a daily cash count with its difference."
                ),
            ),
            (
                ICONS["offline"],
                _("Even without internet"),
                _(
                    "The cash desk and student search work offline; payments sync by themselves "
                    "when the network is back, never twice."
                ),
            ),
            (
                ICONS["unpaid"],
                _("Unpaid fees and dashboard"),
                _(
                    "Late payments by class, fee and instalment, printable statements, today's "
                    "takings and the collection rate of each class."
                ),
            ),
            (
                ICONS["parents"],
                _("Parent portal"),
                _(
                    "On their phone, parents follow the payments, receipts, due dates, notices and "
                    "summons of each child, even in different schools."
                ),
            ),
            (
                ICONS["security"],
                _("Roles, security and audit"),
                _(
                    "School roles and custom roles, two-factor sign-in for money, an audit log; "
                    "a payment is never deleted, only cancelled with a reason."
                ),
            ),
            (
                ICONS["news"],
                _("School communication"),
                _(
                    "Notices to families and staff, the school calendar, parent summons and "
                    "notifications on the phone screen."
                ),
            ),
        ],
        "roles": [
            (_("Promoters and heads"), _("follow takings, unpaid fees and cash desks live.")),
            (_("Accountants"), _("set fee scales, discounts, cancellations and cash counts.")),
            (_("Cashiers"), _("take a payment and print the receipt in seconds.")),
            (_("Secretaries"), _("enrol students, manage families, print forms and lists.")),
            (_("Parents"), _("see payments, receipts and school news on their phone.")),
        ],
        "local": [
            _("Two currencies, the US dollar and the Congolese franc, with the year's rate."),
            _("Weak or no internet: the app stays usable and light."),
            _("A phone, a tablet or an old computer is enough; no app store needed."),
            _("Each school has its own address, logo, fees, receipts and roles."),
            _("Each school's data is kept apart; encrypted backups every night."),
            _("In French and English."),
        ],
        "faq": [
            (
                _("Does %(name)s work without internet?") % values,
                _(
                    "Yes. On a device already signed in, the cash desk, student search and "
                    "receipt printing keep working without a network. Payments sync "
                    "automatically when the connection is back, never twice."
                ),
            ),
            (
                _("Is there anything to install?"),
                _(
                    "No. %(name)s opens in the browser (Chrome, Edge, Safari) and can be added to "
                    "the home screen of a phone or computer like an app, without an app store."
                )
                % values,
            ),
            (
                _("Can parents follow payments?"),
                _(
                    "Yes. With the family code printed on the registration form, parents activate "
                    "their account and see the payments, receipts, due dates and notices of each "
                    "child's school."
                ),
            ),
            (
                _("Are fees in US dollars and Congolese francs supported?"),
                _(
                    "Yes. Each fee has its currency (USD or FC), the school sets the exchange rate "
                    "for the year, and each payment keeps the rate it used."
                ),
            ),
            (
                _("Is my school's data protected?"),
                _(
                    "Each school only sees its own data. Accounts that handle money use two-factor "
                    "sign-in, every sensitive action is written to a log, and the database is "
                    "backed up, encrypted, every night."
                ),
            ),
            (
                _("How can my school try %(name)s?") % values,
                _(
                    "Contact us: we open a trial space for your school, with your classes and "
                    "fees, and help you get started."
                ),
            ),
        ],
    }


def _json_ld(data: dict) -> str:
    """Données structurées (schema.org) sûres dans une balise `<script>`."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        text = text.replace(char, escaped)
    return mark_safe(text)  # échappé ci-dessus


def _structured_data(site: str, url: str, lang: str, platform, texts: dict, image: str) -> str:
    author = {
        "@type": "Person",
        "@id": f"{site}/#author",
        "name": settings.SOFTWARE_AUTHOR,
        "url": settings.SOFTWARE_AUTHOR_URL,
        "sameAs": [settings.SOFTWARE_AUTHOR_URL],
    }
    organization = {
        "@type": "Organization",
        "@id": f"{site}/#organization",
        "name": platform.name,
        "url": f"{site}/",
        "logo": {"@type": "ImageObject", "url": image},
        "founder": {"@id": f"{site}/#author"},
        "areaServed": {"@type": "Country", "name": "Democratic Republic of the Congo"},
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Goma",
            "addressRegion": "Nord-Kivu",
            "addressCountry": "CD",
        },
    }
    contact = {"@type": "ContactPoint", "contactType": "customer support"}
    if platform.support_phone:
        contact["telephone"] = str(platform.support_phone)
    if platform.support_email:
        contact["email"] = platform.support_email
    if len(contact) > 2:
        contact["availableLanguage"] = ["fr", "en"]
        organization["contactPoint"] = contact
    graph = [
        organization,
        author,
        {
            "@type": "WebSite",
            "@id": f"{site}/#website",
            "url": f"{site}/",
            "name": platform.name,
            "inLanguage": ["fr", "en"],
            "publisher": {"@id": f"{site}/#organization"},
        },
        {
            "@type": "WebPage",
            "@id": url,
            "url": url,
            "name": texts["title"],
            "description": texts["description"],
            "inLanguage": lang,
            "isPartOf": {"@id": f"{site}/#website"},
            "about": {"@id": f"{site}/#software"},
            "author": {"@id": f"{site}/#author"},
        },
        {
            "@type": "SoftwareApplication",
            "@id": f"{site}/#software",
            "name": platform.name,
            "url": f"{site}/",
            "image": image,
            "description": texts["description"],
            "applicationCategory": "BusinessApplication",
            "applicationSubCategory": _("School management"),
            "operatingSystem": "Web, Android, iOS, Windows, macOS, Linux",
            "inLanguage": ["fr", "en"],
            "featureList": [title for _icon, title, _text in texts["features"]],
            "author": {"@id": f"{site}/#author"},
            "publisher": {"@id": f"{site}/#organization"},
        },
        {
            "@type": "FAQPage",
            "@id": f"{url}#faq",
            "inLanguage": lang,
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
                for question, answer in texts["faq"]
            ],
        },
    ]
    return _json_ld({"@context": "https://schema.org", "@graph": graph})


def _whatsapp(platform) -> str | None:
    if not platform.support_phone:
        return None
    return "https://wa.me/" + str(platform.support_phone).lstrip("+")


@require_GET
@public
def home(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    platform = PlatformSettings.load()
    site = _site(request)
    url = site + PATHS[lang]
    image = request.build_absolute_uri(platform.icon_url or static("core/site/icon-512.png"))
    with translation.override(lang):
        texts = _texts(platform.name)
        context = {
            "lang": lang,
            "other_lang": "en" if lang == "fr" else "fr",
            "platform": platform,
            "site": site,
            "url": url,
            "paths": PATHS,
            "og_locale": OG_LOCALES[lang],
            "og_alternate": OG_LOCALES["en" if lang == "fr" else "fr"],
            "image": image,
            "texts": texts,
            "json_ld": _structured_data(site, url, lang, platform, texts, image),
            "portal_url": settings.PORTAL_URL,
            # Fin de l'adresse d'une école (`.mwangazaschool.com`), après le code saisi.
            "school_suffix": settings.SCHOOL_URL.split("{code}", 1)[-1],
            "whatsapp": _whatsapp(platform),
            "phone": format_phone(str(platform.support_phone)) if platform.support_phone else "",
            "author": settings.SOFTWARE_AUTHOR,
            "copyright": settings.SOFTWARE_COPYRIGHT,
            "sample_amount": format_amount(15000, "USD"),
            "year": timezone.localdate().year,
        }
        return render(request, "core/site/home.html", context)


@require_GET
def school_space(request: HttpRequest) -> HttpResponse:
    """« Espace de mon école » : le code saisi mène à l'adresse de l'école ; un code mal formé
    ramène au formulaire (rien n'est révélé sur l'existence d'une école)."""
    code = request.GET.get("code", "").strip().lower()
    if not SCHOOL_CODE.match(code):
        back = PATHS["en"] if request.GET.get("lang") == "en" else PATHS["fr"]
        return redirect(f"{back}#ecole")
    return redirect(settings.SCHOOL_URL.format(code=code) + "/app/")


@require_GET
@public
def robots_txt(request: HttpRequest) -> HttpResponse:
    body = f"User-agent: *\nAllow: /\nDisallow: /ecole/\n\nSitemap: {_site(request)}/sitemap.xml\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_GET
@public
def sitemap_xml(request: HttpRequest) -> HttpResponse:
    platform = PlatformSettings.load()
    return render(
        request,
        "core/site/sitemap.xml",
        {
            "site": _site(request),
            "paths": PATHS,
            "lastmod": platform.updated_at.date().isoformat(),
        },
        content_type="application/xml; charset=utf-8",
    )


@require_GET
@public
def llms_txt(request: HttpRequest) -> HttpResponse:
    """Résumé en Markdown pour les assistants (IA), selon la convention `llms.txt`."""
    platform = PlatformSettings.load()
    with translation.override("fr"):
        texts = _texts(platform.name)
        return render(
            request,
            "core/site/llms.txt",
            {
                "platform": platform,
                "site": _site(request),
                "paths": PATHS,
                "texts": texts,
                "portal_url": settings.PORTAL_URL,
                "author": settings.SOFTWARE_AUTHOR,
                "author_url": settings.SOFTWARE_AUTHOR_URL,
                "copyright": settings.SOFTWARE_COPYRIGHT,
            },
            content_type="text/markdown; charset=utf-8",
        )


@require_GET
@public
def favicon(request: HttpRequest) -> HttpResponse:
    """`/favicon.ico`, demandé d'office par les navigateurs : l'icône de la plateforme."""
    platform = PlatformSettings.load()
    return redirect(platform.icon_url or static("core/site/icon-192.png"))
