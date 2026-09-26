"""Limitation des tentatives de connexion (`01` § 9.3, maquette de connexion).

5 essais ratés pour un numéro en 15 minutes → ce numéro est bloqué 15 minutes, même s'il n'a pas
de compte (on ne devine pas qui en a un). 30 essais ratés d'une même adresse IP → cette adresse est
bloquée 15 minutes (essais sur beaucoup de numéros). Le seuil par adresse reste haut : toute une
école passe souvent par la même connexion internet.

Comptent : le mot de passe (API et administration Django), le code de double authentification ou
de secours, le mot de passe actuel demandé pour en changer.
"""

from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException

from apps.accounts.models import LoginFailure
from apps.accounts.phone import InvalidPhoneError, normalize_phone

MAX_FAILURES = 5
MAX_FAILURES_PER_IP = 30
LOCK_DURATION = timedelta(minutes=15)
KEEP_DURATION = timedelta(days=1)


class TooManyAttempts(APIException):
    """429 avec l'en-tête `Retry-After` (secondes), ajouté par DRF à partir de `wait`."""

    status_code = 429
    default_detail = _("Too many failed attempts. Try again later.")
    default_code = "too_many_attempts"

    def __init__(self, wait: int):
        super().__init__()
        self.wait = wait


def phone_key(raw: str) -> str:
    """Le numéro au format E.164 s'il est valable (`0971…` et `+243971…` comptent ensemble),
    sinon le texte tapé."""
    try:
        return normalize_phone(raw)
    except InvalidPhoneError:
        return raw.strip()[:64]


def client_ip(request) -> str | None:
    # Derrière Caddy et Cloudflare, l'adresse réelle viendra d'un en-tête du proxy (tâche 4.6).
    return request.META.get("REMOTE_ADDR") or None


def _wait(failures: QuerySet, limit: int, now) -> int:
    # Bloqué tant que `limit` échecs ont eu lieu dans les 15 dernières minutes : jusqu'à ce que le
    # plus ancien des `limit` derniers sorte de cette fenêtre.
    recent = list(
        failures.filter(created_at__gt=now - LOCK_DURATION)
        .order_by("-created_at")
        .values_list("created_at", flat=True)[:limit]
    )
    if len(recent) < limit:
        return 0
    return max(1, int((recent[-1] + LOCK_DURATION - now).total_seconds()) + 1)


def retry_after(phone: str, ip: str | None) -> int:
    """Secondes avant de pouvoir réessayer ; 0 si ni le numéro ni l'adresse ne sont bloqués."""
    now = timezone.now()
    waits = [_wait(LoginFailure.objects.filter(phone=phone), MAX_FAILURES, now)]
    if ip:
        waits.append(_wait(LoginFailure.objects.filter(ip=ip), MAX_FAILURES_PER_IP, now))
    return max(waits)


def ensure_allowed(phone: str, ip: str | None) -> None:
    wait = retry_after(phone, ip)
    if wait:
        raise TooManyAttempts(wait)


def record_failure(phone: str, ip: str | None) -> None:
    LoginFailure.objects.create(phone=phone, ip=ip)
    LoginFailure.objects.filter(created_at__lt=timezone.now() - KEEP_DURATION).delete()


def clear_failures(phone: str) -> None:
    """Connexion réussie : les essais ratés de ce numéro sont oubliés."""
    LoginFailure.objects.filter(phone=phone).delete()
