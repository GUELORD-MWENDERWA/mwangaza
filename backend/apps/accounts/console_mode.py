"""Console réelle ou démonstration (lot 5, ②bis) : un interrupteur, pas deux consoles.

Le navigateur envoie `X-Console-Mode: live|demo` ; sans lui, ou avec une valeur inconnue, c'est
`live` : on ne montre jamais du fictif par défaut. Chaque point d'API de la console filtre selon ce
mode (écoles par `environment`, comptes et équipe par numéro fictif, prospects, annonces et journal
par `is_demo`) ; ce qui n'existe qu'en réel (site public, facturation, identité, affaires) répond
404 en démonstration (`live_only` sur la vue). Les données d'un mode ne sont jamais lisibles ni
modifiables depuis l'autre.
"""

from django.db.models import Q

from apps.accounts.phone import DEMO_PHONE_PREFIX
from apps.schools.models import School

LIVE = "live"
DEMO = "demo"
HEADER = "X-Console-Mode"


def mode(request) -> str:
    return DEMO if request.headers.get(HEADER) == DEMO else LIVE


def is_demo(request) -> bool:
    return mode(request) == DEMO


def stats_environments(request) -> tuple[str, ...]:
    """Espaces comptés dans les chiffres : les réels seulement (4.15), ou les démonstrations."""
    return (School.Environment.DEMO,) if is_demo(request) else (School.Environment.LIVE,)


def list_environments(request) -> tuple[str, ...]:
    """Espaces listés : réels et essais en mode réel (un essai est un vrai prospect), ou les
    démonstrations."""
    if is_demo(request):
        return (School.Environment.DEMO,)
    return (School.Environment.LIVE, School.Environment.TEST)


def account_scope(request) -> Q:
    """Comptes du mode : ceux de la plage fictive (`phone.DEMO_PHONE_PREFIX`) en démonstration ;
    les autres en réel, plus l'équipe de la plateforme (la même dans les deux modes, et dont le
    compte de développement a un numéro fictif)."""
    fictional = Q(phone__startswith=DEMO_PHONE_PREFIX)
    if is_demo(request):
        return fictional & Q(is_platform_admin=False)
    return ~fictional | Q(is_platform_admin=True)
