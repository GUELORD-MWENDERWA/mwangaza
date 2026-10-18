"""Alertes sur l'écran du super-admin (S.3.2) : chaque usage d'un compte super-admin (entrées
`access.*` du journal de la plateforme), chaque session support ouverte dans une école et chaque
demande de démonstration du site (WEB.1d) sont montrés sur les navigateurs abonnés dans la
console, même console fermée.

Pas de centre de notifications ni de ligne `Notification` : l'alerte renvoie au journal de la
console, qui garde tout. L'abonnement survit à la déconnexion et à la fin de la session (2 heures) :
c'est console fermée que l'alerte sert."""

import logging

from celery.exceptions import OperationalError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import translation
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from apps.audit.actions import Action, PlatformAction
from apps.notifications import push
from apps.notifications.models import PushSubscription

logger = logging.getLogger(__name__)

CONSOLE = PushSubscription.CONSOLE
# Action du journal → écran de la console ouvert par un clic sur l'alerte. Le titre de l'alerte
# est le libellé de l'action.
PAGES = {
    PlatformAction.ACCESS_LOGIN: "/journal",
    PlatformAction.ACCESS_CODE_REFUSED: "/journal",
    PlatformAction.ACCESS_ADDRESS_REFUSED: "/journal",
    Action.SUPPORT_STARTED: "/journal/support",
}
TITLES = {action.value: action.label for action in PAGES}
# Demande de démonstration (WEB.1d) : pas une entrée du journal, sa propre page.
DEMO_REQUEST = "demo_request"
PAGES[DEMO_REQUEST] = "/demo-requests"
TITLES[DEMO_REQUEST] = _("New demo request")


def alert(action: str, entry_id, detail: str) -> None:
    """Prévient les super-admin d'une entrée du journal, une fois sa transaction validée."""
    if not push.is_configured():
        return
    transaction.on_commit(lambda: _enqueue(str(action), str(entry_id), detail))


def _enqueue(action: str, entry_id: str, detail: str) -> None:
    from apps.notifications.tasks import alert_console

    try:
        alert_console.delay(action, entry_id, detail)
    except OperationalError:
        # File de tâches injoignable (Redis arrêté) : l'alerte est perdue, pas la connexion du
        # super-admin, qui doit pouvoir ouvrir la console pour le voir. L'entrée reste au journal.
        logger.exception("Alerte du super-admin non envoyée : file de tâches injoignable.")


def subscriptions() -> QuerySet[PushSubscription]:
    """Navigateurs abonnés dans la console, des comptes encore super-admin et actifs."""
    return PushSubscription.objects.filter(
        app=CONSOLE, user__is_active=True, user__is_platform_admin=True
    )


def deliver(action: str, entry_id: str, detail: str) -> None:
    """Envoi (tâche Celery) à tous les super-admin abonnés, celui qui agit compris : si son
    compte a été pris, c'est lui qu'il faut prévenir. Titre dans la langue de chacun."""
    if not push.is_configured():
        return
    subject = push.vapid_subject()
    body = Truncator(detail).chars(push.BODY_LENGTH)
    for subscription in subscriptions().select_related("user"):
        with translation.override(subscription.user.language):
            title = str(TITLES[action])
        payload = {"id": entry_id, "title": title, "body": body, "url": PAGES[action]}
        push.send(subscription, payload, subject)
