"""Détection (S.8) : alertes de sécurité à l'équipe de la plateforme, sans nouvel outil.

Quatre signes, vérifiés au moment où l'événement arrive (jamais par une tâche qui relit tout) :

- rafale de connexions ratées : une adresse bloquée (30 essais en 15 min), un numéro visé (20 en
  24 h, même de plusieurs adresses), toute la plateforme (200 en 15 min) ;
- export inhabituel : un compte qui exporte plus de 10 fichiers ou 10 000 lignes en une heure ;
- annulations hors norme : une école qui valide 5 annulations ou plus dans la journée, et plus de
  3 fois sa moyenne des 30 jours d'avant ;
- appareil déconnecté qui insiste : 5 contacts refusés en 24 h (le navigateur efface tout au
  premier refus ; plus, c'est quelqu'un qui force).

Chaque alerte est une entrée du journal de la plateforme (domaine `security`, sans auteur), au
plus une par jour pour un même sujet, et part sur l'écran des membres qui ont le droit journal
(`notifications/console.py`). Compteurs et anti-doublons dans le cache (Redis en production) :
aucune écriture en base hors de l'alerte. Le cache injoignable ne bloque jamais la connexion,
l'export ni l'annulation : la détection se tait (le tableau de bord montre déjà Redis en panne)."""

import logging
from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.db.models import Model
from django.utils import timezone

from apps.audit import services as audit
from apps.audit.actions import PlatformAction

logger = logging.getLogger(__name__)

LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_IP_FAILURES = 30  # = le blocage d'une adresse (`accounts/attempts.py`)
LOGIN_PHONE_FAILURES = 20  # essais gardés un jour (`attempts.KEEP_DURATION`)
LOGIN_PLATFORM_FAILURES = 200
EXPORT_WINDOW = timedelta(hours=1)
EXPORTS_PER_HOUR = 10
EXPORT_ROWS_PER_HOUR = 10_000
CANCELLATIONS_MIN = 5
CANCELLATIONS_FACTOR = 3
CANCELLATIONS_HISTORY_DAYS = 30
REVOKED_WINDOW = timedelta(days=1)
REVOKED_CONTACTS = 5
ONCE_EVERY = timedelta(days=1)
# Carte « Sécurité » du tableau de bord.
SHOWN_DAYS = 7
DOMAIN = "security"


def _seconds(delta: timedelta) -> int:
    return int(delta.total_seconds())


def _once(*subject) -> bool:
    """Vrai la première fois de la journée pour ce sujet ; faux ensuite, ou cache injoignable."""
    try:
        return cache.add(
            ":".join(["security", "once", *map(str, subject)]), 1, _seconds(ONCE_EVERY)
        )
    except Exception:
        logger.exception("Détection (S.8) : cache injoignable.")
        return False


def _count(key: str, amount: int, window: timedelta) -> int:
    """Ajoute `amount` au compteur, qui repart de zéro `window` après sa première valeur."""
    key = f"security:count:{key}"
    try:
        cache.add(key, 0, _seconds(window))
        return cache.incr(key, amount)
    except Exception:
        logger.exception("Détection (S.8) : cache injoignable.")
        return 0


def _raise(action: str, entity: Model | None, label: str, after: dict, *, demo=None) -> None:
    from apps.notifications import console

    entry = audit.record_platform(action, entity, actor=None, label=label, after=after, demo=demo)
    console.alert(action, entry.pk, label)


def login_failed(phone: str, ip: str | None) -> None:
    """Après chaque essai raté (`attempts.record_failure`)."""
    from apps.accounts.models import LoginFailure
    from apps.accounts.phone import is_demo_phone

    now = timezone.now()
    action = PlatformAction.SECURITY_LOGIN_BURST
    if ip:
        failures = LoginFailure.objects.filter(ip=ip, created_at__gt=now - LOGIN_WINDOW).count()
        if failures >= LOGIN_IP_FAILURES and _once("ip", ip):
            after = {"scope": "ip", "failures": failures, "minutes": 15}
            _raise(action, None, ip, after, demo=False)
    # Les essais d'un numéro sont effacés à la connexion réussie et au bout d'un jour.
    failures = LoginFailure.objects.filter(phone=phone).count()
    if failures >= LOGIN_PHONE_FAILURES and _once("phone", phone):
        after = {"scope": "phone", "failures": failures, "hours": 24}
        _raise(action, None, phone, after, demo=is_demo_phone(phone))
    window = int(now.timestamp()) // _seconds(LOGIN_WINDOW)
    failures = _count(f"logins:{window}", 1, LOGIN_WINDOW)
    if failures >= LOGIN_PLATFORM_FAILURES and _once("platform"):
        after = {"scope": "platform", "failures": failures, "minutes": 15}
        _raise(action, None, "", after, demo=False)


def exported(user, rows: int) -> None:
    """Après chaque export de données d'une école (Excel ou PDF, pas l'aperçu) ; `rows` : lignes
    du fichier. Compté par école et par compte."""
    from apps.core.tenancy import get_current_school

    school = get_current_school()
    if school is None:
        return
    subject = f"{school.pk}:{user.pk}"
    files = _count(f"exports:{subject}", 1, EXPORT_WINDOW)
    total = _count(f"rows:{subject}", rows, EXPORT_WINDOW)
    if files < EXPORTS_PER_HOUR and total < EXPORT_ROWS_PER_HOUR:
        return
    if _once("export", subject):
        name = user.get_full_name()
        after = {"user": name, "exports": files, "rows": total}
        _raise(PlatformAction.SECURITY_UNUSUAL_EXPORT, school, f"{school.name} · {name}", after)


def payment_cancelled() -> None:
    """Après chaque annulation validée, dans sa transaction (école courante)."""
    from apps.core.tenancy import require_current_school
    from apps.finance.models import PaymentCancellation

    school = require_current_school()
    if school.is_demo:
        # Annulations fictives (remplissage d'une démonstration) : jamais une alerte.
        return
    today = timezone.localdate()
    start = timezone.make_aware(datetime.combine(today, time.min))
    count = PaymentCancellation.objects.filter(approved_at__gte=start).count()
    if count < CANCELLATIONS_MIN:
        return
    previous = PaymentCancellation.objects.filter(
        approved_at__gte=start - timedelta(days=CANCELLATIONS_HISTORY_DAYS), approved_at__lt=start
    ).count()
    # Plus de 3 fois la moyenne par jour, en entiers : count > 3 * previous / 30.
    if count * CANCELLATIONS_HISTORY_DAYS <= CANCELLATIONS_FACTOR * previous:
        return
    if _once("cancellations", school.pk, today):
        after = {"today": count, "previous_30_days": previous}
        _raise(PlatformAction.SECURITY_CANCELLATIONS, school, school.name, after)


def revoked_device_refused(device) -> None:
    """Un appareil déconnecté vient d'être refusé (reprise de session ou synchronisation)."""
    attempts = _count(f"revoked:{device.pk}", 1, REVOKED_WINDOW)
    if attempts >= REVOKED_CONTACTS and _once("revoked", device.pk):
        after = {"attempts": attempts, "user": device.user.get_full_name()}
        label = f"{device} · {device.school.name}"
        _raise(PlatformAction.SECURITY_REVOKED_DEVICE, device, label, after)


def recent(*, demo: bool) -> dict:
    """Carte « Sécurité » : alertes des 7 derniers jours de ce mode, les 5 dernières."""
    from apps.audit.models import PlatformAuditLog

    alerts = PlatformAuditLog.objects.select_related("actor").filter(
        is_demo=demo,
        action__startswith=f"{DOMAIN}.",
        created_at__gte=timezone.now() - timedelta(days=SHOWN_DAYS),
    )
    return {"count": alerts.count(), "days": SHOWN_DAYS, "alerts": list(alerts[:5])}
