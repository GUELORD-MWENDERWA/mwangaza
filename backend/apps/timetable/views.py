"""API des paramètres de l'emploi du temps : grilles horaires, grille et salle des classes, salles,
règles générales (EDT.1a) ; disponibilités, contrôles (EDT.1b) ; règles (EDT.1c). Module
`timetable`, droit `timetable.manage` ; en ligne seulement. Listes courtes (quelques grilles, au
plus 300 salles, 500 règles, classes de l'année) : pas de pagination."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import TIMETABLE_MANAGE
from apps.core.errors import ErrorSerializer
from apps.core.tenancy import require_current_school
from apps.schools import organisation
from apps.schools.models import ClassGroup
from apps.timetable import checks, constraints, services
from apps.timetable.models import Room, TimeGrid, TimetableRule
from apps.timetable.serializers import (
    ChecksSerializer,
    RoomCreateSerializer,
    RoomSerializer,
    RoomUpdateSerializer,
    RuleChoicesSerializer,
    TeacherProfileSerializer,
    TimeGridCreateSerializer,
    TimeGridSerializer,
    TimeGridWriteSerializer,
    TimetableClassSerializer,
    TimetableClassUpdateSerializer,
    TimetableRuleSerializer,
    TimetableRulesSerializer,
    TimetableRuleWriteSerializer,
)

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, **ERRORS}


class _TimetableView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "timetable"
    required_permission = TIMETABLE_MANAGE


def _grid(grid_id) -> dict:
    grid = next(grid for grid in services.grids() if grid.pk == grid_id)
    return TimeGridSerializer(grid).data


@extend_schema(tags=["timetable"])
class GridsView(_TimetableView):
    @extend_schema(responses={200: TimeGridSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Grilles horaires de l'école (par défaut en premier) avec leurs cases."""
        return Response(TimeGridSerializer(services.grids(), many=True).data)

    @extend_schema(
        request=TimeGridCreateSerializer, responses={201: TimeGridSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Nouvelle grille ; sans cases, la semaine proposée (5 jours de 7 heures, samedi de 4,
        récréations après la 3e et la 5e heure) calculée avec la durée et le début donnés."""
        data = TimeGridCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        preset = {
            "lesson_minutes": services.PRESET_LESSON_MINUTES,
            "start_time": services.PRESET_START,
        }
        grid = services.create_grid(actor=request.user, **{**preset, **data.validated_data})
        return Response(_grid(grid.pk), status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class GridView(_TimetableView):
    @extend_schema(
        request=TimeGridWriteSerializer, responses={200: TimeGridSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        """Enregistre les réglages et toute la semaine d'une grille, d'un bloc."""
        grid = get_object_or_404(TimeGrid.objects, pk=pk)
        data = TimeGridWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update_grid(grid, actor=request.user, **data.validated_data)
        return Response(_grid(grid.pk))

    @extend_schema(request=None, responses={204: None, **WRITE_ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Supprime une grille (jamais celle par défaut) ; ses classes suivent la grille par
        défaut."""
        services.delete_grid(get_object_or_404(TimeGrid.objects, pk=pk), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["timetable"])
class ClassesView(_TimetableView):
    @extend_schema(responses={200: TimetableClassSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Classes de l'année en cours : grille, salle habituelle, heures de cours et places."""
        rows = services.class_rows(organisation.current_year())
        return Response(TimetableClassSerializer(rows, many=True).data)


@extend_schema(tags=["timetable"])
class ClassView(_TimetableView):
    @extend_schema(
        request=TimetableClassUpdateSerializer,
        responses={200: TimetableClassSerializer, **WRITE_ERRORS},
    )
    def patch(self, request: Request, pk) -> Response:
        """Change la grille ou la salle habituelle d'une classe (vide : les retire)."""
        group = get_object_or_404(ClassGroup.objects, pk=pk)
        data = TimetableClassUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_class(group, actor=request.user, **data.validated_data)
        row = next(row for row in services.class_rows(group.academic_year) if row["id"] == group.pk)
        return Response(TimetableClassSerializer(row).data)


@extend_schema(tags=["timetable"])
class RoomsView(_TimetableView):
    @extend_schema(responses={200: RoomSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Salles, ateliers et laboratoires, retirés compris."""
        return Response(RoomSerializer(services.rooms(), many=True).data)

    @extend_schema(request=RoomCreateSerializer, responses={201: RoomSerializer, **WRITE_ERRORS})
    def post(self, request: Request) -> Response:
        """Ajoute une salle."""
        data = RoomCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = {"capacity": None, **data.validated_data}
        room = services.create_room(actor=request.user, **fields)
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class RoomView(_TimetableView):
    @extend_schema(request=RoomUpdateSerializer, responses={200: RoomSerializer, **WRITE_ERRORS})
    def patch(self, request: Request, pk) -> Response:
        """Change le nom, le type ou les places d'une salle, ou la retire (`is_active`)."""
        room = get_object_or_404(Room.objects, pk=pk)
        data = RoomUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        room = services.update_room(room, actor=request.user, **data.validated_data)
        return Response(RoomSerializer(room).data)


@extend_schema(tags=["timetable"])
class RulesView(_TimetableView):
    @extend_schema(responses={200: TimetableRulesSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Règles générales de l'emploi du temps de l'école."""
        return Response(services.rules_of(require_current_school()))

    @extend_schema(
        request=TimetableRulesSerializer, responses={200: TimetableRulesSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request) -> Response:
        """Enregistre les règles générales."""
        data = TimetableRulesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(services.set_rules(data.validated_data, actor=request.user))


@extend_schema(tags=["timetable"])
class TeachersView(_TimetableView):
    @extend_schema(responses={200: TeacherProfileSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Disponibilités réglées des enseignants (charge au plus, heures par jour, absences) ;
        un enseignant absent de la liste n'a rien de réglé."""
        return Response(TeacherProfileSerializer(services.teacher_profiles(), many=True).data)


@extend_schema(tags=["timetable"])
class TeacherView(_TimetableView):
    @extend_schema(
        request=TeacherProfileSerializer, responses={200: TeacherProfileSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        """Règle la disponibilité d'un membre du personnel actif de l'école (`pk` : son compte) ;
        une absence en jour entier couvre les plages du même jour."""
        data = TeacherProfileSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        profile = services.set_teacher_profile(pk, actor=request.user, **data.validated_data)
        return Response(TeacherProfileSerializer(profile).data)


@extend_schema(tags=["timetable"])
class ChecksView(_TimetableView):
    @extend_schema(responses={200: ChecksSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Contrôles avant le calcul de l'horaire (année en cours) : classes, enseignants et
        salles surchargés, cours impossibles à étaler, cours incomplets ; rouge d'abord."""
        return Response(ChecksSerializer(checks.run(organisation.current_year())).data)


@extend_schema(tags=["timetable"])
class ConstraintsView(_TimetableView):
    @extend_schema(responses={200: TimetableRuleSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Règles de l'horaire de l'école (liste fermée de kinds), actives d'abord."""
        return Response(TimetableRuleSerializer(constraints.rules(), many=True).data)

    @extend_schema(
        request=TimetableRuleWriteSerializer,
        responses={201: TimetableRuleSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Ajoute une règle : paramètres vérifiés par le schéma de son kind ; cours, salles et
        enseignants de l'école seulement ; un cours dans un seul groupe ; au plus 500 règles."""
        data = TimetableRuleWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = constraints.create_rule(actor=request.user, **data.validated_data)
        return Response(TimetableRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class ConstraintView(_TimetableView):
    @extend_schema(
        request=TimetableRuleWriteSerializer,
        responses={200: TimetableRuleSerializer, **WRITE_ERRORS},
    )
    def put(self, request: Request, pk) -> Response:
        """Remplace une règle (kind compris) ; ce qui change va dans le journal."""
        rule = get_object_or_404(TimetableRule, pk=pk)
        data = TimetableRuleWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = constraints.update_rule(rule, actor=request.user, **data.validated_data)
        return Response(TimetableRuleSerializer(rule).data)

    @extend_schema(responses={204: None, **ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Supprime une règle (journal) ; la désactiver la garde sans la compter."""
        constraints.delete_rule(get_object_or_404(TimetableRule, pk=pk), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["timetable"])
class ConstraintChoicesView(_TimetableView):
    @extend_schema(responses={200: RuleChoicesSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Ce que l'éditeur des règles propose : kinds (forces permises, poids par défaut), cours
        enseignés cette année et leurs enseignants."""
        return Response(RuleChoicesSerializer(constraints.choices()).data)
