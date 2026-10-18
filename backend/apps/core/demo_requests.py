"""Demandes de démonstration du site public (WEB.1d) : formulaire de la page Démonstration, rangé
dans la console (« Demandes »), alerte au super-admin.

- **Spam**, sans dépendance : un champ caché (`site_web`) qu'un robot remplit (on répond « merci »
  sans rien garder) et 5 demandes par heure et par adresse IP (compteur dans le cache, l'adresse
  n'est jamais écrite en base).
- **Doublon** : le même téléphone dans les 24 heures ne crée ni demande ni alerte.
- **Alerte** : sur l'écran des super-admin abonnés (comme les connexions du journal, S.3.2) et par
  e-mail à `ALERT_EMAILS` si le serveur a une boîte d'envoi (`EMAIL_HOST`) ; jamais d'envoi à un
  service tiers (CRM, formulaire hébergé).
- **Confidentialité** : effacée un an après son envoi (`purge`, chaque nuit).
"""

import logging
from datetime import timedelta

from celery.exceptions import OperationalError
from django import forms
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.accounts.phone import (
    INVALID_PHONE_MESSAGE,
    InvalidPhoneError,
    format_phone,
    normalize_phone,
)
from apps.core.models import DemoRequest, PlatformSettings
from apps.notifications import console

logger = logging.getLogger(__name__)

PER_HOUR = 5
DUPLICATE_WINDOW = timedelta(hours=24)
KEEP = timedelta(days=365)
CONSOLE_PAGE = "/demo-requests"


class DemoRequestForm(forms.Form):
    name = forms.CharField(max_length=120)
    role = forms.ChoiceField(choices=DemoRequest.Role.choices)
    school_name = forms.CharField(max_length=120)
    town = forms.CharField(max_length=60)
    phone = forms.CharField(max_length=24)
    size = forms.ChoiceField(choices=DemoRequest.Size.choices, required=False)
    email = forms.EmailField(required=False)
    message = forms.CharField(max_length=1000, required=False)
    consent = forms.BooleanField(
        error_messages={"required": gettext_lazy("Tick the box so that we may call you back.")}
    )
    site_web = forms.CharField(required=False)  # caché aux personnes : un robot le remplit

    def clean_phone(self) -> str:
        try:
            return normalize_phone(self.cleaned_data["phone"])
        except InvalidPhoneError:
            raise ValidationError(INVALID_PHONE_MESSAGE, code="invalid_phone") from None


def allow(ip: str | None) -> bool:
    """Compte une demande de cette adresse ; faux au-delà de 5 dans l'heure."""
    key = f"demo-request:{ip or 'unknown'}"
    cache.add(key, 0, 60 * 60)
    try:
        return cache.incr(key) <= PER_HOUR
    except ValueError:  # clé expirée entre `add` et `incr`
        cache.set(key, 1, 60 * 60)
        return True


def submit(data: dict, language: str) -> DemoRequest | None:
    """Range la demande (formulaire valide) et prévient le super-admin, une fois enregistrée.
    None : robot (champ caché rempli) ou même téléphone dans les 24 heures."""
    data = dict(data)
    data.pop("consent")
    if data.pop("site_web"):
        return None
    since = timezone.now() - DUPLICATE_WINDOW
    if DemoRequest.objects.filter(phone=data["phone"], created_at__gte=since).exists():
        return None
    request = DemoRequest.objects.create(**data, language=language)
    detail = f"{request.school_name}, {request.town} — {request.name}"
    console.alert(console.DEMO_REQUEST, request.pk, detail)
    if email_configured():
        transaction.on_commit(lambda: _enqueue_email(str(request.pk)))
    return request


def email_configured() -> bool:
    return bool(settings.EMAIL_HOST and settings.ALERT_EMAILS)


def _enqueue_email(request_id: str) -> None:
    from apps.core.tasks import email_demo_request

    try:
        email_demo_request.delay(request_id)
    except OperationalError:
        # File de tâches injoignable : la demande reste dans la console, l'alerte sur l'écran aussi.
        logger.exception("E-mail de la demande de démonstration non envoyé : file injoignable.")


def send_email(request_id: str) -> None:
    """E-mail au super-admin (tâche Celery, jamais dans la requête du visiteur)."""
    if not email_configured():
        return
    request = DemoRequest.objects.filter(pk=request_id).first()
    if request is None:  # effacée entre-temps
        return
    platform = PlatformSettings.load()
    with translation.override(settings.LANGUAGE_CODE):
        lines = [
            (_("School"), f"{request.school_name}, {request.town}"),
            (_("Contact"), f"{request.name} ({request.get_role_display()})"),
            (_("Phone"), format_phone(request.phone)),
            (_("Email"), request.email or "—"),
            (_("Number of pupils"), request.get_size_display() or "—"),
            (_("Message"), request.message or "—"),
        ]
        body = "\n".join(f"{label} : {value}" for label, value in lines)
        address = settings.SCHOOL_URL.format(code="admin") + CONSOLE_PAGE
        body += "\n\n" + _("Follow it up in the console: %(address)s") % {"address": address}
        subject = _("Demo request: %(school)s") % {"school": request.school_name}
    send_mail(
        subject,
        body,
        f"{platform.name} <{settings.EMAIL_HOST_USER}>",
        settings.ALERT_EMAILS,
    )


def purge() -> int:
    """Efface les demandes de plus d'un an (chaque nuit)."""
    deleted, _rows = DemoRequest.objects.filter(created_at__lt=timezone.now() - KEEP).delete()
    return deleted
