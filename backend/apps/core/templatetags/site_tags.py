"""Balises du site public (WEB.1b) : icônes (tracés sur 24 px, ceux des maquettes) et captures
du produit (WebP faits par `make captures-site`)."""

from django import template
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

ICONS = {
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "book": '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5z"/>'
    '<path d="M4 19V4.5"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/>'
    '<path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    "cash": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.8"/>'
    '<path d="M6 9.5v5M18 9.5v5"/>',
    "chart": '<path d="M4 4v16h16"/><path d="M8.5 16v-4M12.5 16V8M16.5 16v-6"/>',
    "chat": '<path d="M4 19.5 5.4 15.6A8 8 0 1 1 8.4 18.4z"/>'
    '<path d="M8.5 11.5h.1M12 11.5h.1M15.5 11.5h.1"/>',
    "check": '<path d="M4.5 12.5l5 5 10-11"/>',
    "chevdown": '<path d="m6 9 6 6 6-6"/>',
    "database": '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 '
    '7.5 2.8s7.5-1.3 7.5-2.8v-13M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
    "file": '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 '
    '6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "journal": '<rect x="5" y="3.5" width="14" height="17" rx="2"/>'
    '<path d="M9 3.5V6h6V3.5M9 11h6M9 15h4"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l2 2M15 8l2 2"/>',
    "mail": '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    "megaphone": '<path d="M3 10v4l12 5V5z"/>'
    '<path d="M15 9a3 3 0 0 1 0 6M6 14.5 7.5 20h3l-1.3-4.5"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "phone": '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "pin": '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/>'
    '<circle cx="12" cy="10" r="2.3"/>',
    "print": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/>'
    '<path d="M6 14h12v7H6z"/>',
    "qr": '<rect x="3.5" y="3.5" width="6" height="6" rx="1"/><rect x="14.5" y="3.5" width="6" '
    'height="6" rx="1"/><rect x="3.5" y="14.5" width="6" height="6" rx="1"/><path d="M14.5 '
    '14.5h2v2h-2zM18.5 18.5h2v2h-2zM18.5 14.5h2M14.5 18.5v2"/>',
    "receipt": '<path d="M6 3h12v18l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5L6 21z"/>'
    '<path d="M9 8h6M9 12h6M9 16h3"/>',
    "school": '<path d="M2 9 12 4l10 5-10 5z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 '
    '12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    "students": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 '
    '6.5 5.5"/><circle cx="17" cy="9" r="2.6"/><path d="M16.5 14.6c2.4.2 4.2 1.9 5 4.9"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "userplus": '<circle cx="10" cy="8" r="3.5"/><path d="M3.5 20c.8-3.6 3.4-5.5 6.5-5.5 1.6 0 '
    '3 .4 4.2 1.2"/><path d="M18 14v6M15 17h6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 '
    '6.5 5.5"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.8c1.7.7 2.8 2.4 3.2 5.2"/>',
    "wallet": '<path d="M4 7.5h14a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a1 1 0 0 1-1-1z"/>'
    '<path d="M4 7.5 15 4v3.5M15.5 13.5h2"/>',
    "wifioff": '<path d="M3 3l18 18"/><path d="M8.5 16.5a5 5 0 0 1 7 0M5 12.9a10 10 0 0 1 '
    "5-2.7M14.5 10.4a10 10 0 0 1 4.5 2.5M2 9.3a15 15 0 0 1 4.3-2.6M11 5.1A15 15 0 0 1 22 "
    '9.3"/><path d="M12 20h.01"/>',
}

# Captures du produit (`make captures-site`) : la Gestion sans son menu latéral, 1 184 x 740 et
# moitié ; le Portail au téléphone, 390 x 844.
DESKTOP = (1184, 740)
MOBILE = (390, 844)


@register.simple_tag
def icon(name: str) -> str:
    return mark_safe(  # tracés fixes ci-dessus
        '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )


@register.simple_tag
def capture(name: str, alt: str = "", first: bool = False, later: bool = False) -> str:
    """Image d'une capture : `first` pour la première du héros (chargée tout de suite), `later`
    pour celles que le script charge après la page ; les autres, en chargement différé."""
    url = static(f"core/site/captures/{name}.webp")
    mobile = name.endswith("-mobile")
    width, height = MOBILE if mobile else DESKTOP
    attrs = {"alt": alt, "width": width, "height": height, "decoding": "async"}
    if later:
        attrs["data-src"] = url
    else:
        attrs["src"] = url
        if not mobile:
            half = static(f"core/site/captures/{name}-592.webp")
            attrs["srcset"] = f"{half} 592w, {url} 1184w"
            attrs["sizes"] = "(min-width: 1024px) 640px, 100vw"
    if first:
        attrs["fetchpriority"] = "high"
    elif not later:
        attrs["loading"] = "lazy"
    html = "".join(format_html(' {}="{}"', key, value) for key, value in attrs.items())
    return mark_safe(f"<img{html}>")  # valeurs échappées par format_html


# Photos du site (`static/core/site/photos/`, WebP 1 200 px et 600 px ; crédits :
# `maquettes/assets/photos/README.md`).
PHOTOS = {
    "goma-lac-kivu": (1200, 800),
    "itig-atelier-electricite": (960, 1200),
    "itig-atelier-mecanique-auto": (1200, 800),
    "itig-cour": (1080, 814),
}


@register.simple_tag
def photo(name: str, alt: str) -> str:
    width, height = PHOTOS[name]
    full = static(f"core/site/photos/{name}.webp")
    half = static(f"core/site/photos/{name}-600.webp")
    return format_html(
        '<img src="{}" srcset="{} 600w, {} {}w" sizes="(min-width: 1024px) 560px, 100vw" '
        'alt="{}" width="{}" height="{}" loading="lazy" decoding="async">',
        full,
        half,
        full,
        width,
        alt,
        width,
        height,
    )
