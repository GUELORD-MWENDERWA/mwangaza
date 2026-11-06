"""Heures prestées (EDT.6, `worked.py`) : rapport du mois, heures d'un enseignant un jour donné,
exceptions (noter, annuler), fiche PDF d'un enseignant, export Excel pour la paie. Droit
`timetable.record_exceptions`."""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import TIMETABLE_RECORD_EXCEPTIONS
from apps.core.documents import (
    PRINT_RESPONSE,
    XLSX,
    XLSX_RESPONSE,
    file_response,
    print_options,
    render,
    school_header,
    workbook,
)
from apps.core.errors import ErrorSerializer
from apps.core.tenancy import require_current_school
from apps.timetable import worked
from apps.timetable.models import LessonException
from apps.timetable.worked_serializers import (
    CancelSerializer,
    DayLessonSerializer,
    DayQuerySerializer,
    ExceptionsQuerySerializer,
    LessonExceptionSerializer,
    LessonExceptionWriteSerializer,
    MonthQuerySerializer,
    SheetQuerySerializer,
    WorkedMonthSerializer,
)

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, **ERRORS}


class _WorkedView(GenericAPIView):
    permission_classes = [HasSchoolPermission]
    required_module = "timetable"
    required_permission = TIMETABLE_RECORD_EXCEPTIONS

    def query(self, serializer_class) -> dict:
        params = serializer_class(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return params.validated_data


def _staff(pk) -> User:
    """Un compte du personnel de l'école courante, sinon 404 (jamais celui d'une autre)."""
    return get_object_or_404(worked.active_staff(), pk=pk)


@extend_schema(tags=["timetable"])
class WorkedMonthView(_WorkedView):
    @extend_schema(
        parameters=[MonthQuerySerializer], responses={200: WorkedMonthSerializer, **ERRORS}
    )
    def get(self, request: Request) -> Response:
        """Heures prestées du mois (jusqu'à aujourd'hui) : une ligne par enseignant qui avait des
        heures ou une exception (prévues, absent, annulées, remplacements faits, en plus,
        prestées), jours de cours et congés."""
        report = worked.month_report(self.query(MonthQuerySerializer)["month"])
        return Response(WorkedMonthSerializer(report).data)


@extend_schema(tags=["timetable"])
class WorkedDayView(_WorkedView):
    @extend_schema(
        parameters=[DayQuerySerializer], responses={200: DayLessonSerializer(many=True), **ERRORS}
    )
    def get(self, request: Request) -> Response:
        """Heures d'un enseignant un jour donné dans l'horaire en vigueur ce jour-là (une par
        heure, cours commun compris), avec l'exception déjà notée."""
        data = self.query(DayQuerySerializer)
        rows = worked.day_lessons(data["date"], _staff(data["teacher"]))
        return Response(DayLessonSerializer(rows, many=True).data)


@extend_schema(tags=["timetable"])
class LessonExceptionsView(_WorkedView):
    serializer_class = LessonExceptionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LessonException.all_schools.none()
        data = self.query(ExceptionsQuerySerializer)
        first, last = worked.month_range(data["month"])
        found = LessonException.objects.filter(
            date__gte=first, date__lte=last, cancelled_at__isnull=True
        ).select_related("teacher", "replacement", "created_by")
        if data.get("kind"):
            found = found.filter(kind=data["kind"])
        return found.order_by("-date", "first", "created_at")

    @extend_schema(
        parameters=[ExceptionsQuerySerializer],
        responses={200: LessonExceptionSerializer(many=True), **ERRORS},
    )
    def get(self, request: Request) -> Response:
        """Exceptions actives du mois, les plus récentes d'abord (paginées)."""
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(LessonExceptionSerializer(page, many=True).data)

    @extend_schema(
        request=LessonExceptionWriteSerializer,
        responses={201: LessonExceptionSerializer(many=True), **WRITE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Note ce qui s'est passé un jour passé : absence, remplacement ou annulation d'heures de
        l'horaire de l'enseignant (une exception par heure), ou heure en plus d'un cours. Motif
        obligatoire ; journal."""
        data = LessonExceptionWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        rows = worked.record(
            actor=request.user,
            day=values["date"],
            kind=values["kind"],
            teacher=values["teacher"],
            reason=values["reason"],
            entries=values.get("entries", []),
            replacement=values.get("replacement"),
            course=values.get("course"),
            hours=values.get("hours"),
        )
        return Response(
            LessonExceptionSerializer(rows, many=True).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["timetable"])
class LessonExceptionCancelView(_WorkedView):
    @extend_schema(
        request=CancelSerializer, responses={200: LessonExceptionSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request, pk) -> Response:
        """Annule une exception (motif, journal) : elle sort du calcul, la ligne reste."""
        data = CancelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        exception = worked.cancel(
            get_object_or_404(LessonException, pk=pk),
            actor=request.user,
            reason=data.validated_data["reason"],
        )
        return Response(LessonExceptionSerializer(exception).data)


@extend_schema(tags=["timetable"])
class WorkedSheetView(_WorkedView):
    @extend_schema(parameters=[SheetQuerySerializer], responses={**PRINT_RESPONSE, **ERRORS})
    def get(self, request: Request):
        """Fiche des heures prestées d'un enseignant pour un mois (une page, à la demande, pas
        gardée : les exceptions peuvent changer) ; deux signatures."""
        data = self.query(SheetQuerySerializer)
        context = worked.sheet(data["month"], _staff(data["teacher"]))
        return render(
            "timetable/worked_sheet.html",
            {**school_header(require_current_school()), **context},
            data["output"],
            "heures-prestees.pdf",
            print_options(data, "portrait"),
        )


@extend_schema(tags=["timetable"])
class WorkedExportView(_WorkedView):
    @extend_schema(parameters=[MonthQuerySerializer], responses={**XLSX_RESPONSE, **ERRORS})
    def get(self, request: Request):
        """Classeur du mois pour la paie et les primes : une ligne par enseignant."""
        report = worked.month_report(self.query(MonthQuerySerializer)["month"])
        content = workbook(
            [
                _("Teacher"),
                _("Planned"),
                _("Absent"),
                _("Cancelled"),
                _("Replacements"),
                _("Extra"),
                _("Hours worked"),
            ],
            (
                [
                    row.name,
                    row.planned,
                    row.absent,
                    row.cancelled,
                    row.replacements,
                    row.extra,
                    row.given,
                ]
                for row in report["teachers"]
            ),
            title=report["month"].strftime("%Y-%m"),
            widths=[32, 12, 12, 12, 16, 12, 16],
        )
        return file_response(content, XLSX, f"heures-prestees-{report['month']:%Y-%m}.xlsx")
