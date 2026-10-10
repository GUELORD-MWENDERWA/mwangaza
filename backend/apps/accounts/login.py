"""Connexion en plusieurs étapes (B4, maquettes de connexion, M1).

Le compte n'est connecté (`login()` de Django) qu'après **toutes** ses étapes. Avant, la session
garde seulement la « connexion en cours » (10 minutes au plus) : aucun point d'API n'est atteint
avec le mot de passe seul.

Étapes, dans cet ordre :

1. `password` : numéro et mot de passe ;
2. `totp` : code de double authentification ou code de secours, si elle est activée (sauf sur un
   appareil de confiance) ;
3. `new_password` : mot de passe provisoire donné par l'école, à remplacer (après le code : un
   mot de passe provisoire ne suffit pas à prendre un compte protégé) ;
4. `totp_setup` : activation de la double authentification, si un rôle l'exige ;
5. `done` : connecté.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core import signing
from django.db.models import TextChoices
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotAuthenticated

from apps.accounts import attempts, services
from apps.accounts.models import Membership, User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.crypto import decrypt, encrypt
from apps.core.errors import ApiError, BusinessError
from apps.core.http import client_ip

PENDING_SESSION_KEY = "accounts.login"
# Session connectée passée par la double authentification (vérifié par `HasSchoolPermission`).
MFA_SESSION_KEY = "accounts.mfa"
# Clé TOTP montrée à la personne, en attente du premier code (chiffrée).
TOTP_SETUP_SESSION_KEY = "accounts.totp_setup"
PENDING_DURATION = 10 * 60

# « Ne plus demander sur cet appareil pendant 7 jours » (maquette de double authentification).
TRUSTED_DEVICE_COOKIE = "mwangaza_trusted_device"
TRUSTED_DEVICE_DAYS = 7
_TRUSTED_DEVICE_SALT = "apps.accounts.trusted-device"

INVALID_CREDENTIALS = ApiError("invalid_credentials", _("Wrong phone number or password."), 400)
LOGIN_EXPIRED = ApiError("login_expired", _("The login took too long: start again."), 409)
WRONG_STEP = ApiError("wrong_step", _("This is not the current login step."), 409)
TOTP_SETUP_NOT_STARTED = ApiError("totp_setup_not_started", _("Ask for a new key first."), 409)


class Step(TextChoices):
    PASSWORD = "password", _("Phone number and password")
    TOTP = "totp", _("Two-factor authentication code")
    NEW_PASSWORD = "new_password", _("Replace the temporary password")
    TOTP_SETUP = "totp_setup", _("Turn on two-factor authentication")
    DONE = "done", _("Logged in")


def _next_step(user: User, *, second_factor_ok: bool) -> Step:
    if user.totp_enabled and not second_factor_ok:
        return Step.TOTP
    if user.must_change_password:
        return Step.NEW_PASSWORD
    if not user.totp_enabled and services.totp_required(user):
        return Step.TOTP_SETUP
    return Step.DONE


# Connexion en cours


def log_in(request, phone: str, password: str, *, admin_only: bool = False) -> Step:
    """Étape 1. Numéro inconnu, mauvais mot de passe ou compte désactivé : même réponse.

    `admin_only` (administration Django) : même réponse pour un compte qui n'est pas super-admin,
    et le code est toujours demandé (pas d'appareil de confiance)."""
    attempts.ensure_allowed(attempts.phone_key(phone), client_ip(request))
    user = authenticate(request, phone=phone, password=password)
    if user is None or (admin_only and not user.is_platform_admin):
        raise BusinessError(INVALID_CREDENTIALS)
    if request.user.is_authenticated:
        logout(request)
    # Nouvelle clé de session : un identifiant de session connu d'avance ne sert à rien.
    request.session.cycle_key()
    trusted = not admin_only and is_trusted_device(request, user)
    request.session[PENDING_SESSION_KEY] = {
        "user": str(user.pk),
        "started": time.time(),
        "second_factor_ok": trusted,
        # Comment le second facteur a été donné, pour le journal : `trusted_device`, `totp`,
        # `recovery_code`, ou rien (double authentification pas activée).
        "second_factor": "trusted_device" if trusted else None,
    }
    return advance(request, user)


def pending_user(request) -> User | None:
    """Le compte de la connexion en cours ; None s'il n'y en a pas. `LOGIN_EXPIRED` au-delà de
    10 minutes."""
    pending = request.session.get(PENDING_SESSION_KEY)
    if pending is None:
        return None
    if time.time() - pending["started"] > PENDING_DURATION:
        cancel(request)
        raise BusinessError(LOGIN_EXPIRED)
    user = User.objects.filter(pk=pending["user"], is_active=True).first()
    if user is None:
        cancel(request)
    return user


def current_step(request) -> Step:
    if request.user.is_authenticated:
        return Step.DONE
    try:
        user = pending_user(request)
    except BusinessError:
        return Step.PASSWORD
    if user is None:
        return Step.PASSWORD
    return _next_step(user, second_factor_ok=_pending(request)["second_factor_ok"])


def expect(request, step: Step) -> User:
    """Le compte de la connexion en cours, si elle en est bien à `step`."""
    user = pending_user(request)
    if user is None:
        raise NotAuthenticated
    if _next_step(user, second_factor_ok=_pending(request)["second_factor_ok"]) != step:
        raise BusinessError(WRONG_STEP)
    return user


def second_factor_passed(request, user: User, method: str) -> Step:
    """`method` : `totp` ou `recovery_code` (`services.verify_second_factor`)."""
    pending = _pending(request)
    pending["second_factor_ok"] = True
    pending["second_factor"] = method
    request.session[PENDING_SESSION_KEY] = pending
    return advance(request, user)


def advance(request, user: User) -> Step:
    """Étape suivante ; le compte est connecté quand il n'en reste plus."""
    pending = _pending(request)
    step = _next_step(user, second_factor_ok=pending["second_factor_ok"])
    if step == Step.DONE:
        _finish(request, user, pending)
    return step


def cancel(request) -> None:
    request.session.pop(PENDING_SESSION_KEY, None)
    request.session.pop(TOTP_SETUP_SESSION_KEY, None)


def _pending(request) -> dict:
    return request.session[PENDING_SESSION_KEY]


def _finish(request, user: User, pending: dict) -> None:
    cancel(request)
    login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
    request.session[MFA_SESSION_KEY] = pending["second_factor_ok"]
    attempts.clear_failures(user.phone)
    if request.school is None:
        return
    Membership.objects.filter(user=user, school=request.school).update(last_login_at=timezone.now())
    # Journal de l'école de l'adresse, si la personne y travaille.
    membership = Membership.objects.filter(user=user, school=request.school, is_active=True).first()
    if membership is not None:
        audit.record(
            Action.AUTH_LOGIN,
            membership,
            actor=user,
            after={"second_factor": pending.get("second_factor")},
            label=str(user),
        )


# Compte connecté ou connexion en cours


@contextmanager
def counting_failures(request, user: User) -> Iterator[None]:
    """Limitation des tentatives autour d'un service qui vérifie un code ou le mot de passe
    actuel : refusé si le numéro ou l'adresse est bloqué, échec compté sinon."""
    phone, ip = user.phone, client_ip(request)
    attempts.ensure_allowed(phone, ip)
    try:
        yield
    except BusinessError as exc:
        if exc.error in (services.INVALID_CODE, services.WRONG_PASSWORD):
            attempts.record_failure(phone, ip)
        raise


def start_totp_setup(request, secret: str) -> None:
    request.session[TOTP_SETUP_SESSION_KEY] = encrypt(secret)


def totp_setup_secret(request) -> str:
    token = request.session.get(TOTP_SETUP_SESSION_KEY)
    if token is None:
        raise BusinessError(TOTP_SETUP_NOT_STARTED)
    return decrypt(token)


def end_totp_setup(request) -> None:
    request.session.pop(TOTP_SETUP_SESSION_KEY, None)


# Appareil de confiance


def _trusted_device_fingerprint(user: User) -> str:
    # Changer de mot de passe ou de clé TOTP annule la confiance donnée aux appareils.
    return salted_hmac(
        _TRUSTED_DEVICE_SALT, f"{user.pk}|{user.password}|{user.totp_secret}", algorithm="sha256"
    ).hexdigest()


def trust_device(response, user: User) -> None:
    value = signing.dumps(
        {"user": str(user.pk), "fingerprint": _trusted_device_fingerprint(user)},
        salt=_TRUSTED_DEVICE_SALT,
    )
    response.set_cookie(
        TRUSTED_DEVICE_COOKIE,
        value,
        max_age=TRUSTED_DEVICE_DAYS * 24 * 3600,
        path="/api/auth/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )


def is_trusted_device(request, user: User) -> bool:
    if not user.totp_enabled:
        return False
    value = request.COOKIES.get(TRUSTED_DEVICE_COOKIE)
    if not value:
        return False
    try:
        data = signing.loads(
            value, salt=_TRUSTED_DEVICE_SALT, max_age=TRUSTED_DEVICE_DAYS * 24 * 3600
        )
    except signing.BadSignature:
        return False
    return data.get("user") == str(user.pk) and constant_time_compare(
        data.get("fingerprint", ""), _trusted_device_fingerprint(user)
    )


# Portail des familles (H1, 4.4) : adresse sans école, session à part


# « Rester connecté sur ce téléphone » : 90 jours après la dernière visite. Sinon 12 heures, sans
# prolongation ; cookie daté dans les deux cas (un cookie sans durée est perdu dès qu'on quitte
# l'application installée).
PORTAL_REMEMBER_DAYS = 90
PORTAL_SHORT_SESSION_HOURS = 12
# Jour de la dernière prolongation ; présent seulement avec « Rester connecté ».
PORTAL_RENEWED_SESSION_KEY = "accounts.portal_renewed"
PASSWORD_CHANGE_REQUIRED = ApiError(
    "password_change_required",
    _("Replace your temporary password at your school's address first."),
    403,
)


def log_in_portal(request, phone: str, password: str, *, remember: bool) -> User:
    """Numéro et mot de passe, sans double authentification : le portail ne montre que les
    enfants du compte, et sa session ne vaut pas à l'adresse d'une école (où elle est demandée).
    Mot de passe provisoire refusé : l'école qui l'a donné le connaît."""
    attempts.ensure_allowed(attempts.phone_key(phone), client_ip(request))
    user = authenticate(request, phone=phone, password=password)
    if user is None:
        raise BusinessError(INVALID_CREDENTIALS)
    if user.must_change_password:
        raise BusinessError(PASSWORD_CHANGE_REQUIRED)
    open_portal_session(request, user, remember=remember)
    return user


def open_portal_session(request, user: User, *, remember: bool) -> None:
    """Connecte `user` au portail : après la connexion, l'activation ou un nouveau mot de passe."""
    cancel(request)
    login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
    if remember:
        request.session.set_expiry(PORTAL_REMEMBER_DAYS * 24 * 3600)
        request.session[PORTAL_RENEWED_SESSION_KEY] = timezone.localdate().isoformat()
    else:
        request.session.set_expiry(PORTAL_SHORT_SESSION_HOURS * 3600)
    attempts.clear_failures(user.phone)


def renew_portal_session(request) -> None:
    """Le parent revient : ses 90 jours repartent. Le jour est gardé dans la session, donc au
    plus **une écriture par jour et par appareil** (session et cookie), jamais à chaque requête."""
    today = timezone.localdate().isoformat()
    if request.session.get(PORTAL_RENEWED_SESSION_KEY, today) == today:
        return
    request.session.set_expiry(PORTAL_REMEMBER_DAYS * 24 * 3600)
    request.session[PORTAL_RENEWED_SESSION_KEY] = today
