"""Horaire des interrogations et des examens (EDT.5, `exams.py`) : l'API du directeur des
études ; le droit est `timetable.manage`, la publication `timetable.publish`."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.roles import TIMETABLE_PUBLISH
from apps.schools.models import Term
from apps.timetable import exams
from apps.timetable.exam_serializers import (
    ExamScheduleSerializer,
    ExamSittingSerializer,
    ExamSittingWriteSerializer,
)
from apps.timetable.models import ExamSitting
from apps.timetable.views import WRITE_ERRORS, _TimetableView

TERM = OpenApiParameter("term", str, required=True, description="La période ou les examens.")


def _term(pk) -> Term:
    return exams.period(get_object_or_404(Term, pk=pk))


def _state(term: Term) -> Response:
    data = exams.state(term)
    schedule = data["schedule"]
    return Response(
        ExamScheduleSerializer(
            {
                **data,
                "schedule_status": schedule.status if schedule else "draft",
                "published_at": schedule.published_at if schedule else None,
                "published_by": str(schedule.published_by)
                if schedule and schedule.published_by_id
                else None,
            }
        ).data
    )


@extend_schema(tags=["timetable"])
class ExamsView(_TimetableView):
    @extend_schema(parameters=[TERM], responses={200: ExamScheduleSerializer, **WRITE_ERRORS})
    def get(self, request: Request, term) -> Response:
        """Horaire des épreuves d'une période : état, épreuves (par jour et heure) et contrôles
        (rouge : conflit de classe, de surveillant ou de salle, date hors de la période ;
        orange : surveillant absent, jour de congé)."""
        return _state(_term(term))

    @extend_schema(
        request=ExamSittingWriteSerializer,
        responses={201: ExamSittingSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request, term) -> Response:
        """Ajoute une épreuve (brouillon seulement, 409 si l'horaire est publié) ; les conflits
        ne refusent pas le geste, ils se voient dans les contrôles."""
        period = _term(term)
        data = ExamSittingWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        sitting = exams.save_sitting(
            period, sitting=None, values=data.validated_data, actor=request.user
        )
        return Response(ExamSittingSerializer(sitting).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class ExamSittingView(_TimetableView):
    @extend_schema(
        request=ExamSittingWriteSerializer, responses={200: ExamSittingSerializer, **WRITE_ERRORS}
    )
    def patch(self, request: Request, pk) -> Response:
        """Change une épreuve (brouillon seulement)."""
        sitting = get_object_or_404(ExamSitting.objects.select_related("schedule__term"), pk=pk)
        data = ExamSittingWriteSerializer(sitting, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        saved = exams.save_sitting(
            sitting.schedule.term, sitting=sitting, values=data.validated_data, actor=request.user
        )
        return Response(ExamSittingSerializer(saved).data)

    @extend_schema(responses={204: None, **WRITE_ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Retire une épreuve (brouillon seulement)."""
        sitting = get_object_or_404(
            ExamSitting.objects.select_related("schedule__term", "course"), pk=pk
        )
        exams.delete_sitting(sitting, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["timetable"])
class ExamPublishView(_TimetableView):
    required_permission = TIMETABLE_PUBLISH

    @extend_schema(request=None, responses={200: ExamScheduleSerializer, **WRITE_ERRORS})
    def post(self, request: Request, term) -> Response:
        """Publie l'horaire de la période. Refusé (409) vide ou avec un conflit."""
        period = _term(term)
        exams.publish(period, actor=request.user)
        return _state(period)

    @extend_schema(request=None, responses={200: ExamScheduleSerializer, **WRITE_ERRORS})
    def delete(self, request: Request, term) -> Response:
        """Rouvre un horaire publié pour le changer (écrit au journal)."""
        period = _term(term)
        exams.reopen(period, actor=request.user)
        return _state(period)
