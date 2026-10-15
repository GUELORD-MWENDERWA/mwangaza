"""Ce qu'on lit d'une requête pour la sécurité : adresse IP (limitation des tentatives, journal
d'audit) et navigateur (journal d'audit). Images publiques servies sans risque."""

import ipaddress
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse

from apps.schools.logos import CONTENT_TYPES as LOGO_TYPES

USER_AGENT_MAX_LENGTH = 255


def client_ip(request) -> str | None:
    """Adresse du visiteur. En production, Django n'est joignable que par Caddy, qui écrit
    l'adresse réelle dans `CLIENT_IP_HEADER` (celle donnée par Cloudflare seulement si la requête
    vient de Cloudflare). Sans ce réglage, un en-tête envoyé par le visiteur est ignoré."""
    if settings.CLIENT_IP_HEADER:
        forwarded = request.META.get(settings.CLIENT_IP_HEADER, "").strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.META.get("REMOTE_ADDR") or None


def user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:USER_AGENT_MAX_LENGTH]


def serve_image(file, *, private: bool = False) -> HttpResponse | None:
    """Logo ou icône public (hors de l'API typée : c'est une image) ; None s'il manque. Un SVG
    ne peut rien exécuter, même ouvert seul dans le navigateur. L'adresse donnée par l'API change
    avec chaque fichier : il peut rester un jour en cache. `private` : cachet ou signature (DOC.1),
    gardés par le navigateur du compte (reçu imprimé hors ligne), jamais par un cache partagé."""
    if not file:
        return None
    try:
        content = file.open("rb")
    except FileNotFoundError:
        return None
    kind = Path(file.name).suffix.removeprefix(".")
    response = FileResponse(content, content_type=LOGO_TYPES.get(kind, "application/octet-stream"))
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    response["Cache-Control"] = f"{'private' if private else 'public'}, max-age=86400"
    return response
