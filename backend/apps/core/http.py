"""Ce qu'on lit d'une requête pour la sécurité : adresse IP (limitation des tentatives, journal
d'audit) et navigateur (journal d'audit)."""

USER_AGENT_MAX_LENGTH = 255


def client_ip(request) -> str | None:
    # Derrière Caddy et Cloudflare, l'adresse réelle viendra d'un en-tête du proxy (tâche 4.6).
    return request.META.get("REMOTE_ADDR") or None


def user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:USER_AGENT_MAX_LENGTH]
