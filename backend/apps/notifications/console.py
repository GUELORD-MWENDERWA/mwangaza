"""Alertes sur l'écran de l'équipe (S.3.2, EQ.1) : chaque usage d'un compte de la plateforme
(entrées `access.*` du journal de la plateforme), chaque session support ouverte dans une école et
chaque demande de démonstration du site (WEB.1d) sont montrés sur les navigateurs abonnés dans la
console, même console fermée, des membres qui ont le droit lié (`RIGHTS`).

Pas de centre de notifications ni de ligne `Notification` : l'alerte renvoie au journal de la
console, qui garde tout. L'abonnement survit à la déconnexion et à la fin de la session (2 heures) :
c'est console fermée que l'alerte sert."""

import logging

from celery.exceptions import OperationalError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import translation
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from apps.accounts import platform_roles
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
# IA (IA.1.1) : la dépense du mois atteint 80 % puis 100 % du plafond de la plateforme.
PAGES[PlatformAction.AI_CAP_80] = "/ia"
PAGES[PlatformAction.AI_CAP_100] = "/ia"
TITLES = {action.value: action.label for action in PAGES}
# Demande de démonstration (WEB.1d) : pas une entrée du journal, sa propre page.
DEMO_REQUEST = "demo_request"
PAGES[DEMO_REQUEST] = "/demo-requests"
TITLES[DEMO_REQUEST] = _("New demo request")
# Droit qui reçoit chaque alerte ; les autres : le journal.
RIGHTS = {DEMO_REQUEST: platform_roles.LEADS_MANAGE}


def alert(action: str, entry_id, detail: str, *, concerned=None) -> None:
    """Prévient l'équipe d'une entrée du journal, une fois sa transaction validée ; `concerned` :
    le compte dont il s'agit, prévenu lui aussi."""
    if not push.is_configured():
        return
    concerned = str(concerned) if concerned is not None else None
    transaction.on_commit(lambda: _enqueue(str(action), str(entry_id), detail, concerned))


def _enqueue(action: str, entry_id: str, detail: str, concerned: str | None) -> None:
    from apps.notifications.tasks import alert_console

    try:
        alert_console.delay(action, entry_id, detail, concerned)
    except OperationalError:
        # File de tâches injoignable (Redis arrêté) : l'alerte est perdue, pas la connexion du
        # membre, qui doit pouvoir ouvrir la console pour le voir. L'entrée reste au journal.
        logger.exception("Alerte de l'équipe non envoyée : file de tâches injoignable.")


def subscriptions(action: str | None = None, concerned=None) -> QuerySet[PushSubscription]:
    """Navigateurs abonnés dans la console, des membres actifs de l'équipe ; pour une alerte, ceux
    dont un rôle porte le droit lié (`RIGHTS` : le journal, ou les demandes de démonstration), et
    le compte concerné (`concerned`) quel que soit son rôle."""
    subscriptions = PushSubscription.objects.filter(
        app=CONSOLE, user__is_active=True, user__is_platform_admin=True
    )
    if action is None:
        return subscriptions
    right = RIGHTS.get(action, platform_roles.AUDIT_VIEW)
    receives = Q(user__platform_roles__overlap=platform_roles.roles_with(right))
    if concerned is not None:
        receives |= Q(user_id=concerned)
    return subscriptions.filter(receives)


def deliver(action: str, entry_id: str, detail: str, concerned: str | None = None) -> None:
    """Envoi (tâche Celery) aux membres abonnés qui ont le droit de l'alerte, et au compte
    concerné : si son mot de passe a été volé, c'est lui qu'il faut prévenir. Titre dans la langue
    de chacun."""
    if not push.is_configured():
        return
    subject = push.vapid_subject()
    body = Truncator(detail).chars(push.BODY_LENGTH)
    for subscription in subscriptions(action, concerned).select_related("user"):
        with translation.override(subscription.user.language):
            title = str(TITLES[action])
        payload = {"id": entry_id, "title": title, "body": body, "url": PAGES[action]}
        push.send(subscription, payload, subject)
