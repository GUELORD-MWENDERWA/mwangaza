"""Console de l'IA (IA.1.2) et « Crédits IA » de la Gestion. Logique dans `ai/console.py` et
`ai/services.py` ; chaque changement va au journal de la plateforme."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import console_mode, support
from apps.accounts import platform_roles as team
from apps.accounts.permissions import HasPlatformPermission, HasSchoolPermission, school_access
from apps.accounts.roles import (
    AI_USE,
    ANNOUNCEMENTS_PUBLISH,
    COURSES_CONFIGURE,
    SCHOOL_CONFIGURE,
)
from apps.ai import console, course_grid, drafting, questions, services
from apps.ai.models import AiCall
from apps.ai.serializers import (
    AiAllowanceChangeSerializer,
    AiCreditsSerializer,
    AiOverviewSerializer,
    AiPriceChangeSerializer,
    AiSchoolCardSerializer,
    AiSettingsChangeSerializer,
    AiTopUpSerializer,
    AiUseChangeSerializer,
    CourseGridAskSerializer,
    CourseGridCallSerializer,
    DraftAskSerializer,
    DraftCallSerializer,
    KeepSerializer,
    QuestionAskSerializer,
    QuestionCallSerializer,
)
from apps.core.errors import BusinessError, ErrorSerializer
from apps.core.tenancy import require_current_school
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
            daily_limit=data.get("daily_limit"),
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


AI_ERRORS = {
    **{code: ErrorSerializer for code in (400, 403, 404, 409, 413, 429)},
}


# IA dans l'école : lire un bulletin (IA.5), écrire un brouillon (IA.4), poser une question (IA.3).
# Chaque demande repasse les cinq verrous (`services.authorize`) ; la réponse se lit sur l'appel,
# seulement par la personne qui l'a demandé.


def _school_call(request: Request, pk, use: str) -> AiCall:
    return get_object_or_404(AiCall, pk=pk, user=request.user, use=use)


def _asker(request: Request) -> dict:
    return {
        "school": require_current_school(),
        "user": request.user,
        "permissions": school_access(request).permissions,
        "support": support.current(request) is not None,
    }


def _call_state(call: AiCall, serializer, key: str, value, code=status.HTTP_200_OK) -> Response:
    data = {"id": call.pk, "state": call.state, "refusal": call.refusal, key: value}
    return Response(serializer(data).data, status=code)


class _CourseGridView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = COURSES_CONFIGURE


@extend_schema(tags=["ai"])
class CourseGridView(_CourseGridView):
    parser_classes = [MultiPartParser]

    @extend_schema(
        request=CourseGridAskSerializer,
        responses={202: CourseGridCallSerializer, **AI_ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Envoie le PDF ou la photo d'un bulletin (IA.5) : l'appel est rendu tout de suite, la
        grille proposée se lit sur l'appel. Droits `courses.configure` et `ai.use`."""
        data = CourseGridAskSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        upload = data.validated_data["file"]
        if upload.size > max(course_grid.MAX_BYTES.values()):
            raise BusinessError(course_grid.TOO_BIG)
        call = course_grid.ask(
            **_asker(request),
            request_id=data.validated_data["request_id"],
            content=upload.read(),
        )
        return _call_state(
            call, CourseGridCallSerializer, "proposal", None, status.HTTP_202_ACCEPTED
        )


@extend_schema(tags=["ai"])
class CourseGridCallView(_CourseGridView):
    @extend_schema(responses={200: CourseGridCallSerializer, **AI_ERRORS})
    def get(self, request: Request, pk) -> Response:
        """État de la lecture ; prête, les cours lus (revérifiés) et ce qui n'a pas été repris."""
        call = _school_call(request, pk, course_grid.USE)
        ready = call.state == AiCall.State.DONE
        proposal = course_grid.proposal(call) if ready else None
        return _call_state(call, CourseGridCallSerializer, "proposal", proposal)

    @extend_schema(
        operation_id="ai_course_grid_settle",
        request=KeepSerializer,
        responses={204: None, **AI_ERRORS},
    )
    def post(self, request: Request, pk) -> Response:
        """La grille lue a été mise dans l'écran (gardée) ou laissée (abandonnée)."""
        data = KeepSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        course_grid.settle(
            _school_call(request, pk, course_grid.USE), kept=data.validated_data["kept"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class _DraftView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "communication"
    required_permission = ANNOUNCEMENTS_PUBLISH


@extend_schema(tags=["ai"])
class DraftsView(_DraftView):
    @extend_schema(request=DraftAskSerializer, responses={202: DraftCallSerializer, **AI_ERRORS})
    def post(self, request: Request) -> Response:
        """Demande un brouillon d'annonce, de relance ou de convocation (IA.4) à partir d'une
        phrase. Droits `announcements.publish` et `ai.use`."""
        data = DraftAskSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        call = drafting.ask(
            **_asker(request),
            request_id=values["request_id"],
            kind=values["kind"],
            tone=values["tone"],
            brief=values["brief"],
        )
        return _call_state(call, DraftCallSerializer, "draft", None, status.HTTP_202_ACCEPTED)


@extend_schema(tags=["ai"])
class DraftCallView(_DraftView):
    @extend_schema(responses={200: DraftCallSerializer, **AI_ERRORS})
    def get(self, request: Request, pk) -> Response:
        """État de la demande ; prête, le brouillon (titre, texte)."""
        call = _school_call(request, pk, drafting.USE)
        ready = call.state == AiCall.State.DONE
        return _call_state(
            call, DraftCallSerializer, "draft", drafting.draft(call) if ready else None
        )

    @extend_schema(
        operation_id="ai_drafts_settle", request=KeepSerializer, responses={204: None, **AI_ERRORS}
    )
    def post(self, request: Request, pk) -> Response:
        """Le brouillon a été mis dans le texte (gardé) ou laissé (abandonné)."""
        data = KeepSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        drafting.settle(_school_call(request, pk, drafting.USE), kept=data.validated_data["kept"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class _QuestionView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "ai"
    required_permission = AI_USE


@extend_schema(tags=["ai"])
class QuestionsView(_QuestionView):
    @extend_schema(
        request=QuestionAskSerializer, responses={202: QuestionCallSerializer, **AI_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Pose une question sur les chiffres de l'école (IA.3) : l'IA la traduit en une requête
        d'une liste fermée, l'application calcule la réponse avec les droits de la personne."""
        data = QuestionAskSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        call = questions.ask(
            **_asker(request),
            request_id=values["request_id"],
            question=values["question"],
            history=values.get("history", []),
        )
        return _call_state(call, QuestionCallSerializer, "answer", None, status.HTTP_202_ACCEPTED)


@extend_schema(tags=["ai"])
class QuestionCallView(_QuestionView):
    @extend_schema(responses={200: QuestionCallSerializer, **AI_ERRORS})
    def get(self, request: Request, pk) -> Response:
        """État de la question ; prête, la réponse calculée (une seule fois : ensuite l'appel est
        gardé ou abandonné et la réponse vit dans l'écran). Sans le droit de l'écran d'où vient
        la réponse : `forbidden`, sans chiffre."""
        call = _school_call(request, pk, questions.USE)
        answer = None
        if call.state == AiCall.State.DONE:
            asker = _asker(request)
            answer = questions.answer(
                call, permissions=asker["permissions"], support=asker["support"]
            )
            call.refresh_from_db()
        return _call_state(call, QuestionCallSerializer, "answer", answer)
