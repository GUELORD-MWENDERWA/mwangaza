"""Compte super-admin de la plateforme (S.3.1), où qu'il soit utilisé : console, administration
Django, adresse d'une école avant une session support.

- **Adresses autorisées** : réglage facultatif du serveur `DJANGO_CONSOLE_ALLOWED_IPS` (adresses
  ou réseaux séparés par des virgules ; vide : toutes). Hors liste, la connexion est refusée comme
  un mauvais mot de passe et une session déjà ouverte ne sert plus. Le réglage est sur le serveur,
  pas dans la console : celui qui a pris le compte ne peut pas l'élargir.
- **Session courte** : fermée après 2 heures sans activité.

Connexions et refus sont écrits au journal de la plateforme, avec l'adresse IP et le site, et
montrés sur l'écran des super-admin abonnés dans la console (S.3.2, `notifications/console.py`)."""

import ipaddress
import logging
import time
from functools import lru_cache

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core.errors import ApiError
from apps.core.http import client_ip
from apps.notifications import console

logger = logging.getLogger(__name__)

IDLE_SECONDS = 2 * 60 * 60
# La session n'est réécrite qu'à cet intervalle : jamais une écriture à chaque requête.
RENEW_AFTER = 5 * 60
SEEN_SESSION_KEY = "accounts.privileged_seen"
# Dernière adresse refusée notée au journal : une entrée par session et par adresse.
REFUSED_SESSION_KEY = "accounts.privileged_refused"

ADDRESS_NOT_ALLOWED = ApiError(
    "address_not_allowed", _("This account cannot be used from this network."), 403
)


@lru_cache(maxsize=8)
def _networks(allowed: tuple[str, ...]) -> tuple:
    networks = []
    for item in allowed:
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            # Une entrée mal écrite n'autorise personne : le réglage reste fermé, pas ouvert.
            logger.error("DJANGO_CONSOLE_ALLOWED_IPS : « %s » n'est ni adresse ni réseau.", item)
    return tuple(networks)


def address_allowed(request) -> bool:
    allowed = tuple(settings.CONSOLE_ALLOWED_IPS)
    if not allowed:
        return True
    try:
        address = ipaddress.ip_address(client_ip(request) or "")
    except ValueError:
        return False
    return any(address in network for network in _networks(allowed))


def record(action: str, user: User, request, **after) -> None:
    """Entrée du journal de la plateforme sur l'usage du compte : qui, depuis quelle adresse IP,
    sur quel site (console, administration, adresse d'une école) ; alerte aux super-admin."""
    label = " · ".join([str(user), client_ip(request) or "?", request.get_host()])
    entry = audit.record_platform(action, user, actor=user, after=after or None, label=label)
    console.alert(action, entry.pk, label, concerned=user.pk)


def keep_short(request) -> None:
    """Les 2 heures repartent : à la connexion, puis au plus toutes les 5 minutes d'activité."""
    seen = request.session.get(SEEN_SESSION_KEY)
    now = time.time()
    if seen is None or now - seen > RENEW_AFTER:
        request.session.set_expiry(IDLE_SECONDS)
        request.session[SEEN_SESSION_KEY] = now


class PrivilegedAccountMiddleware:
    """Chaque requête d'un super-admin connecté : refusée (403) hors des adresses autorisées,
    sinon sa session courte est prolongée. Les autres comptes ne sont pas concernés (leur compte
    est déjà lu par l'API : aucune requête de plus)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = request.user
        if user.is_authenticated and user.is_platform_admin:
            if not address_allowed(request):
                ip = client_ip(request)
                if request.session.get(REFUSED_SESSION_KEY) != ip:
                    request.session[REFUSED_SESSION_KEY] = ip
                    record(PlatformAction.ACCESS_ADDRESS_REFUSED, user, request)
                return JsonResponse(ADDRESS_NOT_ALLOWED.body(), status=ADDRESS_NOT_ALLOWED.status)
            keep_short(request)
        return self.get_response(request)
