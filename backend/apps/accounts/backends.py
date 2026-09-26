from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied

from apps.accounts import attempts


class PhoneBackend(ModelBackend):
    """Connexion par numéro de téléphone et mot de passe, avec la limitation des tentatives :
    aussi pour la connexion de l'administration Django, qui passe par ici."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        raw = username if username is not None else kwargs.get("phone")
        if raw is None or password is None:
            return None
        phone = attempts.phone_key(raw)
        ip = attempts.client_ip(request) if request is not None else None
        if attempts.retry_after(phone, ip):
            # Django arrête là et répond comme pour un mauvais mot de passe.
            raise PermissionDenied
        user = super().authenticate(request, username=raw, password=password)
        if user is None:
            attempts.record_failure(phone, ip)
        return user
