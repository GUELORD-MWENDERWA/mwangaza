"""Ce qu'on lit d'une requête pour la sécurité : adresse IP (limitation des tentatives, journal
d'audit) et navigateur (journal d'audit)."""

import ipaddress

from django.conf import settings

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
