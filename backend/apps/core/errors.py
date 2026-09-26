"""Erreurs de l'API : `{"code": …, "detail": …}`.

Le `code` est stable : l'interface affiche son propre texte traduit à partir du code (i18next).
`detail` aide au développement et passe par la traduction du serveur.
"""

from dataclasses import dataclass

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


@dataclass(frozen=True)
class ApiError:
    code: str
    detail: str | Promise
    status: int

    def body(self) -> dict[str, str]:
        return {"code": self.code, "detail": str(self.detail)}


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="Code stable, traduit par l'interface.")
    detail = serializers.CharField()


SCHOOL_NOT_FOUND = ApiError("school_not_found", _("There is no school at this address."), 404)
SCHOOL_SUSPENDED = ApiError(
    "school_suspended", _("This school is suspended. Please contact Mwangaza."), 403
)
