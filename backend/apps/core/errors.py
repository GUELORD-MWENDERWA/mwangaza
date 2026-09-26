"""Erreurs de l'API : `{"code": …, "detail": …}`.

Le `code` est stable : l'interface affiche son propre texte traduit à partir du code (i18next).
`detail` aide au développement et passe par la traduction du serveur.
"""

from dataclasses import dataclass

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


@dataclass(frozen=True)
class ApiError:
    code: str
    detail: str | Promise
    status: int

    def body(self) -> dict[str, str]:
        return {"code": self.code, "detail": str(self.detail)}


class BusinessError(Exception):
    """Règle métier refusée par un service. L'API répond `{code, detail}` avec le statut de
    l'erreur ; les services n'ont pas besoin de connaître DRF."""

    def __init__(self, error: ApiError):
        super().__init__(str(error.detail))
        self.error = error


def api_exception_handler(exc, context):
    """Même format pour toutes les erreurs qui ne concernent pas un champ : `{code, detail}`
    (`not_authenticated`, `permission_denied`, `not_found`, `method_not_allowed`…). Les erreurs
    de saisie gardent le format de DRF : `{champ: [messages]}`."""
    if isinstance(exc, BusinessError):
        return Response(exc.error.body(), status=exc.error.status)
    response = drf_exception_handler(exc, context)
    if (
        response is not None
        and isinstance(response.data, dict)
        and set(response.data) == {"detail"}
    ):
        detail = response.data["detail"]
        response.data = {"code": getattr(detail, "code", "error"), "detail": str(detail)}
    return response


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="Code stable, traduit par l'interface.")
    detail = serializers.CharField()


SCHOOL_NOT_FOUND = ApiError("school_not_found", _("There is no school at this address."), 404)
SCHOOL_SUSPENDED = ApiError(
    "school_suspended", _("This school is suspended. Please contact Mwangaza."), 403
)
