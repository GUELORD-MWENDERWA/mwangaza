from django.utils.functional import SimpleLazyObject

from apps.core.models import PlatformSettings


def platform(request) -> dict:
    """Identité de la plateforme dans les pages servies par Django (vérification d'un reçu) ; lue
    seulement si la page s'en sert."""
    return {"platform": SimpleLazyObject(PlatformSettings.load)}
