"""Notifications sur l'écran (5.5) : centre de notifications de chaque application et envoi Web
Push aux navigateurs abonnés, par Celery, même application fermée."""

import json
import logging
from collections import defaultdict
from collections.abc import Iterable

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.text import Truncator

from apps.accounts.models import Membership, User
from apps.accounts.roles import (
    FINANCE_APPROVE_CANCELLATION,
    FINANCE_VIEW_REPORTS,
    GRADES_VALIDATE,
    ROLES_MANAGE,
)
from apps.core.models import PlatformSettings
from apps.core.tenancy import use_all_schools, use_school
from apps.notifications.models import (
    Notification,
    NotificationPreference,
    PlatformAnnouncement,
    PushSubscription,
)
from apps.schools.models import School

logger = logging.getLogger(__name__)

App = Notification.App
Kind = Notification.Kind

# Alertes du personnel : le droit qu'il faut, dans l'école, pour en recevoir (5.6.1).
STAFF_KINDS = {
    Kind.CANCELLATION_REQUEST: FINANCE_APPROVE_CANCELLATION,
    Kind.CASH_DIFFERENCE: FINANCE_VIEW_REPORTS,
    Kind.REGISTER_OPEN: FINANCE_VIEW_REPORTS,
    Kind.SENSITIVE_RIGHTS: ROLES_MANAGE,
    # Le titulaire la reçoit aussi (`events.grades_sent`), sans pouvoir la couper : une par cours.
    Kind.GRADES_SENT: GRADES_VALIDATE,
    Kind.REPORT_CARDS_READY: GRADES_VALIDATE,
}
# Alertes de sécurité : aucun compte ne peut les couper.
ALWAYS_SENT = frozenset({Kind.SENSITIVE_RIGHTS})
# Sortes qu'un compte peut couper, par application ; la notification d'essai part toujours.
PREFERENCE_KINDS = {
    App.GESTION: [
        Kind.PLATFORM_NEWS,
        Kind.STAFF_ANNOUNCEMENT,
        *(kind for kind in STAFF_KINDS if kind not in ALWAYS_SENT),
    ],
    App.PORTAIL: [
        Kind.PAYMENT_RECEIVED,
        Kind.ANNOUNCEMENT,
        Kind.SUMMONS,
        Kind.DISCIPLINE_INCIDENT,
        Kind.PLACE_OFFERED,
        Kind.PAYMENT_DUE,
        Kind.PAYMENT_OVERDUE,
    ],
}
# Notifications par tâche d'envoi : une annonce à mille familles ne retient pas un worker.
DELIVERY_BATCH = 200
# Un appareil éteint plus longtemps ne la reçoit pas sur l'écran ; elle reste au centre.
TTL = 24 * 60 * 60
# Le service de notifications refuse un message chiffré de plus de 4 Ko.
BODY_LENGTH = 300


def is_configured() -> bool:
    return bool(settings.WEBPUSH_VAPID_PUBLIC_KEY and settings.WEBPUSH_VAPID_PRIVATE_KEY)


def draft(
    user: User, *, app: str, kind: str, title: str, body: str = "", url: str = ""
) -> Notification:
    """Notification pas encore enregistrée, texte coupé à la taille du centre et de l'envoi."""
    return Notification(
        user=user,
        app=app,
        kind=kind,
        title=Truncator(title).chars(120),
        body=Truncator(body).chars(BODY_LENGTH),
        url=url,
    )


def notify(
    users: Iterable[User],
    *,
    school: School,
    app: str,
    kind: str,
    title: str,
    body: str = "",
    url: str = "",
) -> list[Notification]:
    """La même notification pour chaque compte (`create`)."""
    drafts = (draft(user, app=app, kind=kind, title=title, body=body, url=url) for user in users)
    return create(school, drafts)


def create(school: School, drafts: Iterable[Notification]) -> list[Notification]:
    """Ajoute les notifications au centre de leur compte, puis les envoie sur les écrans une fois
    la transaction validée (rien n'est envoyé pour une action annulée)."""
    with use_school(school):
        notifications = Notification.objects.bulk_create(drafts)
    if notifications and is_configured():
        from apps.notifications.tasks import deliver

        ids = [str(notification.pk) for notification in notifications]
        for start in range(0, len(ids), DELIVERY_BATCH):
            batch = ids[start : start + DELIVERY_BATCH]
            transaction.on_commit(lambda batch=batch: deliver.delay(batch))
    return notifications


def notify_platform_news(announcement: PlatformAnnouncement, schools: list[School]) -> None:
    """Annonce de la plateforme publiée (5.4.3) : tout le personnel actif des écoles visées
    (toutes les écoles non suspendues quand la liste est vide)."""
    memberships = Membership.objects.filter(is_active=True, user__is_active=True).exclude(
        school__status__in=School.CLOSED_STATUSES
    )
    if schools:
        memberships = memberships.filter(school__in=schools)
    by_school = defaultdict(list)
    for membership in memberships.select_related("school", "user"):
        by_school[membership.school].append(membership.user)
    for school, users in by_school.items():
        notify(
            users,
            school=school,
            app=App.GESTION,
            kind=Kind.PLATFORM_NEWS,
            title=announcement.title,
            body=announcement.body,
            url="/platform-news",
        )


def inbox(user: User, app: str) -> QuerySet[Notification]:
    """Centre de notifications du compte dans l'école courante."""
    return Notification.objects.filter(user=user, app=app)


def mark_read(user: User, app: str, ids: list | None) -> None:
    """Toutes (`ids` vide ou absent) ou celles données ; celles d'une autre école sont ignorées
    (manager de l'école courante)."""
    unread = inbox(user, app).filter(read_at__isnull=True)
    if ids:
        unread = unread.filter(pk__in=ids)
    unread.update(read_at=timezone.now())


def offered_kinds(app: str, permissions: Iterable[str] = ()) -> list[str]:
    """Sortes que le compte règle dans cette application : dans la Gestion, une alerte du
    personnel seulement s'il a, dans l'école de l'adresse, le droit d'en recevoir."""
    return [
        kind
        for kind in PREFERENCE_KINDS[app]
        if kind not in STAFF_KINDS or STAFF_KINDS[kind] in permissions
    ]


def muted_kinds(user: User, kinds: list[str]) -> list[str]:
    """Sortes coupées par le compte, parmi celles qu'il règle ici (`offered_kinds`)."""
    preference = NotificationPreference.objects.filter(user=user).first()
    stored = preference.muted if preference else []
    return [kind for kind in stored if kind in kinds]


def set_muted_kinds(user: User, kinds: list[str], muted: list[str]) -> list[str]:
    """Remplace les sortes coupées parmi celles qu'il règle ici ; les autres (l'autre
    application, ou une alerte reçue dans une autre école avec d'autres droits) ne bougent pas."""
    preference = NotificationPreference.objects.filter(user=user).first()
    others = [kind for kind in (preference.muted if preference else []) if kind not in kinds]
    NotificationPreference.objects.update_or_create(
        user=user, defaults={"muted": sorted({*others, *muted})}
    )
    return sorted(muted)


@transaction.atomic
def subscribe(
    user: User, *, app: str, school: School | None, endpoint: str, p256dh: str, auth: str, ua: str
) -> PushSubscription:
    """Abonne ce navigateur. Le même navigateur repris par un autre compte (ordinateur partagé)
    passe à ce compte : l'ancien n'y reçoit plus rien."""
    subscription, _ = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": user,
            "app": app,
            "school": school,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": ua[:300],
        },
    )
    return subscription


def unsubscribe(user: User, *, app: str, school: School | None, endpoint: str) -> None:
    PushSubscription.objects.filter(user=user, app=app, school=school, endpoint=endpoint).delete()


def deliver(notification_ids: list[str]) -> None:
    """Envoi sur l'écran (tâche Celery) : aux navigateurs abonnés du compte pour la même
    application (et la même école dans la Gestion), sauf sorte coupée. Un abonnement expiré est
    supprimé ; une autre erreur est seulement notée (la notification reste au centre)."""
    if not is_configured():
        return
    # Tâche de fond, sans école courante : liste filtrée sur les identifiants donnés.
    with use_all_schools():
        notifications = list(Notification.all_schools.filter(pk__in=notification_ids))
    user_ids = {notification.user_id for notification in notifications}
    muted = dict(
        NotificationPreference.objects.filter(user_id__in=user_ids).values_list("user_id", "muted")
    )
    subscriptions = defaultdict(list)
    for subscription in PushSubscription.objects.filter(user_id__in=user_ids, user__is_active=True):
        key = (subscription.user_id, subscription.app, subscription.school_id)
        subscriptions[key].append(subscription)
    subject = vapid_subject()
    for notification in notifications:
        if notification.kind in muted.get(notification.user_id, ()):
            continue
        payload = {
            "id": str(notification.pk),
            "title": notification.title,
            "body": notification.body,
            "url": notification.url,
        }
        school_id = notification.school_id if notification.app == App.GESTION else None
        for subscription in subscriptions[(notification.user_id, notification.app, school_id)]:
            send(subscription, payload, subject)


def vapid_subject() -> str:
    """Contact de la plateforme donné aux services de notifications (Google, Apple, Mozilla)."""
    email = PlatformSettings.load().support_email
    return f"mailto:{email}" if email else settings.PORTAL_URL


def webpush(**kwargs):
    """`pywebpush` (≈ 40 Mo avec aiohttp) chargé au premier envoi, pas au démarrage de chaque
    processus (PERF.8) : seul le travailleur qui envoie le paie."""
    from pywebpush import webpush as send_push

    return send_push(**kwargs)


def send(subscription: PushSubscription, payload: dict, subject: str) -> None:
    """Un message (`id`, `title`, `body`, `url`) à un navigateur ; lu par `push-sw.js`."""
    from pywebpush import WebPushException

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
            vapid_claims={"sub": subject},
            ttl=TTL,
            timeout=10,
        )
    except WebPushException as error:
        status = getattr(error.response, "status_code", None)
        if status in (404, 410):
            subscription.delete()
        else:
            logger.warning("Web Push refusé (%s) pour l'abonnement %s", status, subscription.pk)
