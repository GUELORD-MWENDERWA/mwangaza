"""API de l'espace du titulaire (NB.3) : sa classe dans une période, et « Bulletins prêts ».
Module `academics`, un droit de notes, et surtout être le titulaire de la classe : tout autre
compte reçoit 403, directeur des études compris (il a « Suivi des notes »)."""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import board, homeroom
from apps.academics.serializers import BoardCourseSerializer
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE
from apps.core.errors import ErrorSerializer
from apps.schools.models import ClassGroup, Term
from apps.schools.serializers import TermSerializer, term_tree

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


class HomeroomFilterSerializer(serializers.Serializer):
    class_group = serializers.UUIDField(
        required=False, help_text="Absent : la première classe dont le compte est titulaire."
    )
    term = serializers.UUIDField(
        required=False, help_text="Absent : la période du jour, sinon la dernière commencée."
    )


class ReadySerializer(serializers.Serializer):
    class_group = serializers.UUIDField()
    term = serializers.UUIDField()


class HomeroomClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    is_titular = serializers.BooleanField(
        help_text="Titulaire (sinon cotitulaire, NB.7 : il complète, sans déclarer les bulletins "
        "prêts)."
    )


class HomeroomCourseSerializer(serializers.Serializer):
    course = BoardCourseSerializer()
    average = serializers.DecimalField(
        max_digits=5, decimal_places=1, allow_null=True, help_text="% moyen, fiche envoyée."
    )
    below_half = serializers.IntegerField(allow_null=True, help_text="Élèves sous la moitié.")


class HomeroomTotalSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    maximum = serializers.IntegerField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    place = serializers.IntegerField(allow_null=True)
    mention = serializers.CharField(allow_null=True)


class HomeroomStudentSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    number = serializers.IntegerField()
    full_name = serializers.CharField()
    total = HomeroomTotalSerializer(help_text="Score vide : une note manque.")
    conduct = serializers.CharField(help_text="Vide pour les examens.")
    application = serializers.CharField(help_text="Vide pour les examens ou sans note.")


class HomeroomStatsSerializer(serializers.Serializer):
    students = serializers.IntegerField()
    graded = serializers.IntegerField(help_text="Élèves avec toutes leurs notes.")
    average = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    highest = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    lowest = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    at_least_half = serializers.IntegerField()


class HomeroomSerializer(serializers.Serializer):
    classes = HomeroomClassSerializer(many=True, help_text="Classes dont le compte est titulaire.")
    class_group = HomeroomClassSerializer(allow_null=True)
    terms = TermSerializer(many=True)
    term = serializers.UUIDField(allow_null=True)
    courses = HomeroomCourseSerializer(many=True)
    complete = serializers.BooleanField(help_text="Toutes les fiches de la période validées.")
    ready_at = serializers.DateTimeField(allow_null=True, help_text="Bulletins déclarés prêts.")
    ready_by = serializers.CharField()
    students = HomeroomStudentSerializer(many=True, help_text="Vide tant que pas complète.")
    stats = HomeroomStatsSerializer(allow_null=True, help_text="Absent tant que pas complète.")


class _HomeroomView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)

    def own_class(self, request: Request, pk, *, titular: bool = False) -> ClassGroup:
        """Le titulaire ou le cotitulaire (NB.7) ; `titular` : le titulaire seul (bulletins
        prêts)."""
        # Manager de l'école de l'adresse : une classe d'une autre école est introuvable.
        group = get_object_or_404(
            ClassGroup.objects.select_related("academic_year", "level", "track"), pk=pk
        )
        allowed = (
            group.homeroom_teacher_id == request.user.pk
            if titular
            else group.is_homeroom_of(request.user)
        )
        if not allowed:
            raise PermissionDenied(_("Only the homeroom teacher of this class opens its space."))
        return group


def _class(group: ClassGroup, request: Request) -> dict:
    return {
        "id": group.pk,
        "name": group.name,
        "is_titular": group.homeroom_teacher_id == request.user.pk,
    }


@extend_schema(tags=["grades"])
class HomeroomView(_HomeroomView):
    @extend_schema(
        parameters=[HomeroomFilterSerializer], responses={200: HomeroomSerializer, **ERRORS}
    )
    def get(self, request: Request) -> Response:
        """Espace du titulaire : sa classe dans une période ou des examens — état de chaque fiche
        de cotes (moyenne et élèves sous la moitié une fois envoyée), puis, toutes validées, la
        vérification élève par élève et les chiffres de la classe ; « Bulletins prêts »."""
        params = HomeroomFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        classes = homeroom.homeroom_classes(request.user)
        data = {
            "classes": [_class(c, request) for c in classes],
            "class_group": None,
            "terms": [],
            "term": None,
            "courses": [],
            "complete": False,
            "ready_at": None,
            "ready_by": "",
            "students": [],
            "stats": None,
        }
        chosen = params.validated_data.get("class_group")
        group = self.own_class(request, chosen) if chosen else next(iter(classes), None)
        if group is None:
            return Response(HomeroomSerializer(data).data)
        terms = board.graded_terms(group.academic_year)
        term = next((t for t in terms if t.pk == params.validated_data.get("term")), None)
        term = term or board.default_term(group.academic_year, terms)
        data.update(
            class_group=_class(group, request),
            terms=term_tree(group.academic_year),
            term=term.pk if term else None,
        )
        if term is not None:
            found = homeroom.space(group, term)
            data.update(
                courses=found.courses,
                complete=found.complete,
                ready_at=found.ready_at,
                ready_by=found.ready_by,
                students=found.students,
                stats=found.stats,
            )
        return Response(HomeroomSerializer(data).data)


@extend_schema(tags=["grades"])
class HomeroomReadyView(_HomeroomView):
    def _target(self, request: Request) -> tuple[ClassGroup, Term]:
        serializer = ReadySerializer(data=request.data or request.query_params)
        serializer.is_valid(raise_exception=True)
        group = self.own_class(request, serializer.validated_data["class_group"], titular=True)
        return group, get_object_or_404(Term, pk=serializer.validated_data["term"])

    @extend_schema(request=ReadySerializer, responses={204: None, 409: ErrorSerializer, **ERRORS})
    def post(self, request: Request) -> Response:
        """Déclare les bulletins de la période prêts (le titulaire, pas le cotitulaire) : 409
        `sheets_missing` tant qu'une fiche n'est pas validée. Journal, notification
        `report_cards_ready` à ceux qui valident les notes."""
        group, term = self._target(request)
        homeroom.declare_ready(group, term, actor=request.user)
        return Response(status=204)

    @extend_schema(parameters=[ReadySerializer], responses={204: None, **ERRORS})
    def delete(self, request: Request) -> Response:
        """Retire la déclaration (`?class_group=&term=`) ; au journal."""
        group, term = self._target(request)
        homeroom.withdraw_ready(group, term, actor=request.user)
        return Response(status=204)
