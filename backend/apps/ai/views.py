"""Console de l'IA (IA.1.2) et « Crédits IA » de la Gestion. Logique dans `ai/console.py` et
`ai/services.py` ; chaque changement va au journal de la plateforme."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import console_mode
from apps.accounts import platform_roles as team
from apps.accounts.permissions import HasPlatformPermission, HasSchoolPermission
from apps.accounts.roles import SCHOOL_CONFIGURE
from apps.ai import console, services
from apps.ai.serializers import (
    AiAllowanceChangeSerializer,
    AiCreditsSerializer,
    AiOverviewSerializer,
    AiPriceChangeSerializer,
    AiSchoolCardSerializer,
    AiSettingsChangeSerializer,
    AiTopUpSerializer,
    AiUseChangeSerializer,
)
from apps.core.errors import ErrorSerializer
from apps.schools.models import School

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


class _ConsoleAi(APIView):
    permission_classes = [HasPlatformPermission]
    platform_permission = team.AI_MANAGE

    def _overview(self, request: Request) -> Response:
        data = console.overview(
            console_mode.list_environments(request), live=not console_mode.is_demo(request)
        )
        return Response(AiOverviewSerializer(data).data)


@extend_schema(tags=["console"])
class ConsoleAiView(_ConsoleAi):
    """Page « IA » de la console (droit `platform.ai.manage`) : dépense du mois, par école et par
    usage, part des résultats gardés, alertes ; en mode réel, réglages de la plateforme. En
    démonstration : les espaces de démonstration, sans plafond ni réglages."""

    @extend_schema(responses={200: AiOverviewSerializer, 403: ErrorSerializer})
    def get(self, request: Request) -> Response:
        return self._overview(request)

    @extend_schema(
        request=AiSettingsChangeSerializer, responses={200: AiOverviewSerializer, **ERRORS}
    )
    def patch(self, request: Request) -> Response:
        """Interrupteur, plafond du mois (micro-dollars) et appels par personne et par heure ;
        mode réel seulement."""
        if console_mode.is_demo(request):
            raise NotFound
        serializer = AiSettingsChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data:
            services.update_settings(actor=request.user, **serializer.validated_data)
        return self._overview(request)


@extend_schema(tags=["console"])
class ConsoleAiPriceView(_ConsoleAi):
    """Prix d'un modèle connu, en micro-dollars par million de jetons ; mode réel seulement."""

    live_only = True

    @extend_schema(request=AiPriceChangeSerializer, responses={200: AiOverviewSerializer, **ERRORS})
    def put(self, request: Request, model: str) -> Response:
        serializer = AiPriceChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        console.change_price(
            actor=request.user,
            model=model,
            input_=data["input"],
            output=data["output"],
            cache_read=data["cache_read"],
        )
        return self._overview(request)


@extend_schema(tags=["console"])
class ConsoleAiUseView(_ConsoleAi):
    """Modèle et limites d'un usage du catalogue ; tout vide : réglage d'origine. Réel seulement."""

    live_only = True

    @extend_schema(request=AiUseChangeSerializer, responses={200: AiOverviewSerializer, **ERRORS})
    def put(self, request: Request, code: str) -> Response:
        serializer = AiUseChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        console.change_use(
            actor=request.user,
            code=code,
            model=data.get("model"),
            max_input=data.get("max_input_tokens"),
            max_output=data.get("max_output_tokens"),
        )
        return self._overview(request)


@extend_schema(tags=["console"])
class ConsoleAiSchoolView(_ConsoleAi):
    """Carte « IA » de la fiche d'une école du mode de la console : usages par module, crédits
    du mois, derniers appels (jamais leur texte) ; `PUT` : usages, crédits par mois, pause."""

    def _school(self, request: Request, pk) -> School:
        return get_object_or_404(
            School.objects.filter(environment__in=console_mode.list_environments(request)), pk=pk
        )

    @extend_schema(
        responses={200: AiSchoolCardSerializer, 403: ErrorSerializer, 404: ErrorSerializer}
    )
    def get(self, request: Request, pk) -> Response:
        return Response(AiSchoolCardSerializer(console.school_card(self._school(request, pk))).data)

    @extend_schema(
        request=AiAllowanceChangeSerializer, responses={200: AiSchoolCardSerializer, **ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        school = self._school(request, pk)
        serializer = AiAllowanceChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        codes = list(dict.fromkeys(data["uses"]))
        console.check_uses(school, codes)
        services.set_allowance(
            school,
            actor=request.user,
            uses_=codes,
            monthly_credits=data["monthly_credits"],
            paused=data["paused"],
        )
        return Response(AiSchoolCardSerializer(console.school_card(school)).data)


@extend_schema(tags=["console"])
class ConsoleAiTopUpView(ConsoleAiSchoolView):
    """Recharge : des crédits en plus pour le mois en cours de cette école."""

    http_method_names = ["post", "options"]

    @extend_schema(request=AiTopUpSerializer, responses={200: AiSchoolCardSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        school = self._school(request, pk)
        serializer = AiTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.top_up(school, actor=request.user, credits=serializer.validated_data["credits"])
        return Response(
            AiSchoolCardSerializer(console.school_card(school)).data, status=status.HTTP_200_OK
        )


@extend_schema(tags=["ai"])
class AiCreditsView(APIView):
    """« Crédits IA » de l'école (Gestion), en lecture seule : crédits du mois, usages donnés et,
    pour chacun, la raison d'un refus certain (bouton grisé). Droits `school.configure` ou
    `ai.use`."""

    permission_classes = [HasSchoolPermission]
    required_permission = (SCHOOL_CONFIGURE, "ai.use")

    @extend_schema(responses={200: AiCreditsSerializer, 403: ErrorSerializer})
    def get(self, request: Request) -> Response:
        return Response(AiCreditsSerializer(console.credits_for_school(request.school)).data)
