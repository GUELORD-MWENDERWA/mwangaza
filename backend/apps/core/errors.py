"""Erreurs de l'API : `{"code": …, "detail": …}`.

Le `code` est stable : l'interface affiche son propre texte traduit à partir du code (i18next).
`detail` aide au développement et passe par la traduction du serveur.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from rest_framework.fields import get_error_detail
from rest_framework.response import Response
from rest_framework.settings import api_settings
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


INVALID = ApiError("invalid", _("Some fields are invalid."), 400)


def api_exception_handler(exc, context):
    """Même format pour toutes les erreurs : `{code, detail}` (`not_authenticated`,
    `permission_denied`, `not_found`, `method_not_allowed`…). Erreurs de saisie : `code`
    `invalid` et, dans `fields`, chaque champ avec ses erreurs `{code, detail}` (ex.
    `password_too_short`) ; l'interface les traduit par leur code. Un service peut lever la
    `ValidationError` de Django (`{"terms.0.ends_on": ValidationError(…, code=…)}`) : même
    réponse."""
    if isinstance(exc, BusinessError):
        return Response(exc.error.body(), status=exc.error.status)
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(get_error_detail(exc))
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, exceptions.ValidationError):
        response.data = {**INVALID.body(), "fields": _field_errors(exc.get_full_details())}
    elif isinstance(response.data, dict) and set(response.data) == {"detail"}:
        detail = response.data["detail"]
        response.data = {"code": getattr(detail, "code", "error"), "detail": str(detail)}
    return response


def _field_errors(details, prefix: str = "") -> dict[str, list[dict[str, str]]]:
    """`{champ: [{message, code}]}` de DRF, à plat : `contact.phone`, `roles.1.name` ; une
    erreur sans champ va dans `non_field_errors`."""
    if isinstance(details, dict) and set(details) == {"message", "code"}:
        details = [details]
    if isinstance(details, list) and all(
        isinstance(item, dict) and set(item) == {"message", "code"} for item in details
    ):
        key = prefix or api_settings.NON_FIELD_ERRORS_KEY
        return {key: [{"code": item["code"], "detail": str(item["message"])} for item in details]}
    items = details.items() if isinstance(details, dict) else enumerate(details)
    fields: dict[str, list[dict[str, str]]] = {}
    for name, value in items:
        if value:
            fields.update(_field_errors(value, f"{prefix}.{name}" if prefix else str(name)))
    return fields


class FieldErrorSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="Code stable, traduit par l'interface.")
    detail = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="Code stable, traduit par l'interface.")
    detail = serializers.CharField()
    fields = serializers.DictField(
        child=FieldErrorSerializer(many=True),
        required=False,
        help_text="Erreurs de saisie (`code` `invalid`) : chaque champ et ses erreurs.",
    )


SCHOOL_NOT_FOUND = ApiError("school_not_found", _("There is no school at this address."), 404)
SCHOOL_SUSPENDED = ApiError(
    "school_suspended", _("This school is suspended. Please contact Mwangaza."), 403
)
