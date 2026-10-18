"""Site public de la plateforme (domaine nu, WEB.1b) : sept pages en français et en anglais
(accueil, écoles, parents, modules, démonstration et contact, « Trouver mon école », mentions et
confidentialité), lisibles sans JavaScript par les moteurs de recherche et les assistants (IA),
et leurs fichiers pour les robots (`robots.txt`, `sitemap.xml`, `llms.txt`).

Nom, logo, icône, couleurs et contact viennent de l'identité de la plateforme (règle 9) ; l'auteur
du logiciel, des réglages ; ce qui change souvent, de `site_content.py`. Les espaces privés
(écoles, portail, console, vérification des reçus) ne sont jamais indexés (`infra/routes.caddy`).
Une lecture en base par page (plus les chiffres de la plateforme, en cache une heure), pages
gardées une heure par les navigateurs."""

import json
import re
from datetime import date
from urllib.parse import urlsplit

import segno
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone, translation
from django.utils.formats import number_format
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from apps.accounts.modules import DEPENDENCIES, MODULES
from apps.accounts.phone import format_phone
from apps.core import site_content
from apps.core.models import PlatformSettings
from apps.core.money import format_amount

# Adresse de chaque page dans chaque langue ; `config/urls.py` en fait les routes.
PAGES = {
    "home": {"fr": "/", "en": "/en/"},
    "schools": {"fr": "/ecoles/", "en": "/en/schools/"},
    "parents": {"fr": "/parents/", "en": "/en/parents/"},
    "modules": {"fr": "/modules/", "en": "/en/modules/"},
    "contact": {"fr": "/demonstration/", "en": "/en/demo/"},
    "find": {"fr": "/trouver-mon-ecole/", "en": "/en/find-my-school/"},
    "legal": {"fr": "/mentions-legales/", "en": "/en/legal/"},
}
# Adresse courte de la confidentialité : mène à sa section de la page des mentions.
PRIVACY = {"fr": "/confidentialite/", "en": "/en/privacy/"}
PATHS = PAGES["home"]
OG_LOCALES = {"fr": "fr_FR", "en": "en_US"}
# Code d'une école = son sous-domaine (lettres minuscules, chiffres, tirets).
SCHOOL_CODE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
# Espace de démonstration montré par les captures (`make captures-site`).
EXAMPLE_SCHOOL = "itig"
# Bande de chiffres de l'accueil : seulement à partir de ce nombre d'écoles réelles.
STATS_MIN_SCHOOLS = 5
STATS_CACHE = "site:stats"
LEGAL_UPDATED = date(2026, 10, 18)
# Vue de chaque page (`config/urls.py`).
VIEWS = {
    "home": "home",
    "schools": "schools",
    "parents": "parents",
    "modules": "modules",
    "contact": "contact",
    "find": "find_school",
    "legal": "legal",
}
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
        "headline": _("The whole school in one app, even without internet"),
        "lead": _(
            "Students, fees in dollars and francs, cash desk and receipts, unpaid fees, marks and "
            "report cards, and a space for parents. The cash desk keeps going when the internet "
            "is down; everything goes out as soon as the network is back."
        ),
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
                _("Does %(name)s make the report cards?") % values,
                _(
                    "Yes. The teacher enters the marks; %(name)s works out the totals, "
                    "percentages, ranks and conduct, then prints the report card in the school's "
                    "format. Its QR code lets anyone check that it is genuine."
                )
                % values,
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


def _meta(key: str, name: str) -> tuple[str, str]:
    """Titre et description de chaque page (sauf l'accueil, dans `_texts`)."""
    values = {"name": name}
    return {
        "schools": (
            _("%(name)s for schools: fees, cash desk, marks and parents") % values,
            _(
                "Management, accountant, cashier and teacher each work on their own screen, with "
                "the same figures, up to date. Start even in the middle of the year."
            ),
        ),
        "parents": (
            _("Parent space — %(name)s") % values,
            _(
                "Follow your children's school on your phone: payments, receipts, what is left "
                "to pay, notices and summons. Activate your account with the family code."
            ),
        ),
        "modules": (
            _("Modules — %(name)s") % values,
            _(
                "Each school chooses its modules: students, fees and cash desk, marks and report "
                "cards, parent space, notices, notifications, work without internet."
            ),
        ),
        "contact": (
            _("Request a demo — %(name)s") % values,
            _(
                "See %(name)s with your school's classes and fees, online or at your school in "
                "Goma. Contact us on WhatsApp, by phone or by email."
            )
            % values,
        ),
        "find": (
            _("Find my school — %(name)s") % values,
            _("School staff: type your school's code to open its space."),
        ),
        "legal": (
            _("Legal notice and privacy — %(name)s") % values,
            _("Who publishes %(name)s, where the data is kept and what we do with it.") % values,
        ),
    }[key]


def _render(request: HttpRequest, key: str, lang: str, build=None) -> HttpResponse:
    """Page `key` dans la langue `lang` : contexte commun (identité, liens, contact), plus celui
    de `build(platform)`, calculé dans la langue de la page."""
    platform = PlatformSettings.load()
    site = _site(request)
    other = "en" if lang == "fr" else "fr"
    with translation.override(lang):
        context = {
            "lang": lang,
            "other_lang": other,
            "other_lang_name": "English" if other == "en" else "Français",
            "page": key,
            "platform": platform,
            "site": site,
            "url": site + PAGES[key][lang],
            "alternates": PAGES[key],
            "other_url": PAGES[key][other],
            "links": {name: paths[lang] for name, paths in PAGES.items()},
            "og_locale": OG_LOCALES[lang],
            "og_alternate": OG_LOCALES[other],
            "image": request.build_absolute_uri(
                platform.icon_url or static("core/site/icon-512.png")
            ),
            "portal_url": settings.PORTAL_URL,
            "portal_host": urlsplit(settings.PORTAL_URL).netloc,
            "demo_address": urlsplit(settings.SCHOOL_URL.format(code=EXAMPLE_SCHOOL)).netloc
            + "/app/",
            "whatsapp": _whatsapp(platform),
            "phone": format_phone(str(platform.support_phone)) if platform.support_phone else "",
            "author": settings.SOFTWARE_AUTHOR,
            "copyright": settings.SOFTWARE_COPYRIGHT,
            "copyright_url": settings.SOFTWARE_COPYRIGHT_URL,
            "year": timezone.localdate().year,
        }
        if key != "home":
            context["title"], context["description"] = _meta(key, platform.name)
        if build:
            context.update(build(platform, context))
        return render(request, f"core/site/{key}.html", context)


def _rounded(value: int) -> int:
    """Chiffre arrondi vers le bas (9 437 → 9 400) : un ordre de grandeur, pas un compteur."""
    step = 100 if value >= 1000 else 10 if value >= 100 else 1
    return value - value % step


def _count_stats() -> tuple[int, ...]:
    """Écoles, élèves inscrits cette année, reçus de l'année civile, familles sur l'espace
    parents : espaces réels seulement, ni essai ni démonstration (A7). Rien sous 5 écoles."""
    from apps.finance.models import Payment
    from apps.schools.models import School
    from apps.students.models import Enrollment, Family

    live = School.objects.filter(environment=School.Environment.LIVE).exclude(
        status__in=School.CLOSED_STATUSES
    )
    schools = live.count()
    if schools < STATS_MIN_SCHOOLS:
        return ()
    year = timezone.localdate().year
    return (
        schools,
        Enrollment.all_schools.filter(
            school__in=live, status="active", academic_year__is_current=True
        ).count(),
        Payment.all_schools.filter(
            school__in=live, origin=Payment.Origin.CASH, paid_at__year=year
        ).count(),
        Family.all_schools.filter(
            school__in=live, activated_at__isnull=False, portal_suspended_at__isnull=True
        ).count(),
    )


def platform_stats() -> list[tuple[str, int, str]]:
    """Chiffres de la bande de l'accueil (valeur affichée, nombre, libellé), en cache une heure ;
    vide sous 5 écoles réelles."""
    values = cache.get_or_set(STATS_CACHE, _count_stats, 3600)
    labels = (
        _("schools"),
        _("students followed"),
        _("receipts this year"),
        _("families on the parent space"),
    )
    return [
        (number_format(_rounded(value), force_grouping=True), _rounded(value), label)
        for value, label in zip(values, labels, strict=False)
    ]


def _ordinal(n: int) -> str:
    """Place sur le bulletin d'exemple : « 2e », « 2nd »."""
    if translation.get_language().startswith("fr"):
        return f"{n}er" if n == 1 else f"{n}e"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n, 'th') }"


def _home(platform, context: dict) -> dict:
    texts = _texts(platform.name)
    return {
        "texts": texts,
        "title": texts["title"],
        "description": texts["description"],
        "json_ld": _structured_data(
            context["site"], context["url"], context["lang"], platform, texts, context["image"]
        ),
        "stats": platform_stats(),
        "references": site_content.REFERENCES,
        "sample": {
            "usd": format_amount(2000, "USD"),
            "cdf": format_amount(30000, "CDF"),
            "one_usd": format_amount(100, "USD"),
            "rate": format_amount(2800, "CDF"),
            "paid": format_amount(15000, "USD"),
            # Bulletin d'exemple (premier semestre) : 87 / 110, 91 / 110, 92 / 120, 270 / 340.
            "p1": number_format(79.1, 1),
            "p2": number_format(82.7, 1),
            "exam": number_format(76.7, 1),
            "percent": number_format(79.4, 1),
            **{f"place{n}": f"{_ordinal(n)}/42" for n in (2, 3, 4, 5)},
            "qr": segno.make(context["url"] + "#bulletin", error="m").svg_data_uri(border=0),
        },
    }


def _modules(platform, context: dict) -> dict:
    return {
        "modules": [
            {
                "name": label,
                "icon": site_content.MODULE_ICONS.get(code, "settings"),
                "features": site_content.MODULE_FEATURES.get(code, ()),
                "needs": [MODULES[other][0] for other in DEPENDENCIES.get(code, ())],
            }
            for code, (label, _permissions) in MODULES.items()
        ],
        "upcoming": site_content.UPCOMING,
    }


def _legal(platform, context: dict) -> dict:
    return {"updated": LEGAL_UPDATED, "editor": settings.SOFTWARE_COPYRIGHT}


@require_GET
@public
def home(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return _render(request, "home", lang, _home)


@require_GET
@public
def schools(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return _render(request, "schools", lang)


@require_GET
@public
def parents(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return _render(request, "parents", lang)


@require_GET
@public
def modules(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return _render(request, "modules", lang, _modules)


@require_GET
@public
def contact(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return _render(request, "contact", lang)


@require_GET
@public
def legal(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return _render(request, "legal", lang, _legal)


@require_GET
@public
def privacy(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    return redirect(PAGES["legal"][lang] + "#confidentialite", permanent=True)


@require_GET
@public
def find_school(request: HttpRequest, lang: str = "fr") -> HttpResponse:
    """« Trouver mon école » : le code saisi mène à l'adresse de l'école, sans rien chercher en
    base (ni liste des écoles, ni moyen de deviner lesquelles existent). Code mal formé : la
    même page, avec l'erreur."""
    code = request.GET.get("code")
    if code is not None:
        code = code.strip().lower()
        if SCHOOL_CODE.match(code):
            return redirect(settings.SCHOOL_URL.format(code=code) + "/app/")

    def build(platform, context: dict) -> dict:
        return {
            "code": code or "",
            "error": code is not None,
            "school_suffix": settings.SCHOOL_URL.split("{code}", 1)[-1],
            "school_pattern": settings.SCHOOL_URL + "/app/",
        }

    return _render(request, "find", lang, build)


@require_GET
def school_space(request: HttpRequest) -> HttpResponse:
    """Ancienne adresse du formulaire (`/ecole/?code=…`, avant WEB.1b) : même règle."""
    lang = "en" if request.GET.get("lang") == "en" else "fr"
    return find_school(request, lang)


@require_GET
@public
def robots_txt(request: HttpRequest) -> HttpResponse:
    body = (
        "User-agent: *\nAllow: /\nDisallow: /ecole/\nDisallow: /*?code=\n\n"
        f"Sitemap: {_site(request)}/sitemap.xml\n"
    )
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
            "pages": PAGES.values(),
            "lastmod": max(platform.updated_at.date(), LEGAL_UPDATED).isoformat(),
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
                "pages": PAGES,
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
