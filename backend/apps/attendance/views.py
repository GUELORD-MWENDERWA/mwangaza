"""Cartes (6.1, A.5) et liste de l'appareil de pointage (6.3). Droits `attendance.cards`
(cartes) et `attendance.scan` (liste) ; les passages arrivent par la synchronisation
(`attendance.scan`, `POST /api/sync/push/`)."""

from django.db.models import Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts import services as accounts_services
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import (
    ATTENDANCE_CARDS,
    ATTENDANCE_CORRECT,
    ATTENDANCE_SCAN,
    ATTENDANCE_VIEW,
)
from apps.attendance import cards, corrections, reports
from apps.attendance.models import AbsenceJustification, AttendanceCorrection, IdCard
from apps.attendance.serializers import (
    AbsenceSerializer,
    AbsencesQuerySerializer,
    CardListQuerySerializer,
    CardPrintResultSerializer,
    CardPrintSerializer,
    CardRevokeSerializer,
    CardSerializer,
    CardStaffSerializer,
    CardStudentSerializer,
    CardSummarySerializer,
    CorrectionQuerySerializer,
    CorrectionSerializer,
    CorrectionWriteSerializer,
    DayQuerySerializer,
    DaySerializer,
    JustificationDecisionSerializer,
    JustificationQuerySerializer,
    JustificationSerializer,
    PeriodQuerySerializer,
    PhotoResultSerializer,
    RosterQuerySerializer,
    RosterSerializer,
    RosterStaffSerializer,
    RosterStudentSerializer,
    SchoolJustificationSerializer,
    StaffDaySerializer,
)
from apps.core import printing
from apps.core.documents import XLSX, XLSX_RESPONSE, file_response
from apps.core.errors import ApiError, BusinessError, ErrorSerializer
from apps.core.ids import uuid7
from apps.schools import matricule
from apps.students import services as students_services
from apps.students.models import Student
from apps.students.photos import image_response
from apps.students.serializers import PhotoUploadSerializer
from apps.students.views import _words

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, 429: ErrorSerializer, **ERRORS}
PRINT_BUSY = ApiError(
    "print_busy",
    gettext_lazy("Too many documents in preparation: try again in a moment."),
    429,
)
PRINT_EXPIRED = ApiError(
    "print_expired",
    gettext_lazy(
        "This print is no longer available: card codes are never kept. Issue the cards again."
    ),
    410,
)
PRINT_PATH = "/api/attendance/cards/print/{batch}/"


def _ordered_cards() -> Prefetch:
    return Prefetch("cards", queryset=IdCard.objects.order_by("-created_at"))


class _CardsView(GenericAPIView):
    permission_classes = [HasSchoolPermission]
    required_module = "attendance"
    required_permission = ATTENDANCE_CARDS

    def query(self, serializer_class) -> dict:
        params = serializer_class(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return params.validated_data


@extend_schema(tags=["attendance"], parameters=[CardListQuerySerializer])
class CardStudentsView(_CardsView, ListAPIView):
    """Élèves inscrits de l'année avec leur carte active et leur dernière carte révoquée."""

    serializer_class = CardStudentSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return IdCard.objects.none()
        data = self.query(CardListQuerySerializer)
        items = cards.students_list().prefetch_related(
            Prefetch("student__cards", queryset=IdCard.objects.order_by("-created_at"))
        )
        if data.get("class_group"):
            items = items.filter(class_group=data["class_group"])
        if data.get("search"):
            items = items.filter(
                _words(
                    data["search"],
                    "student__last_name",
                    "student__middle_name",
                    "student__first_name",
                    "student__matricule",
                )
            )
        if data.get("card") == "active":
            items = items.filter(cards.has_active_card("student", "student"))
        elif data.get("card") == "none":
            items = items.filter(~cards.has_active_card("student", "student"))
        return items


@extend_schema(tags=["attendance"], parameters=[CardListQuerySerializer])
class CardStaffView(_CardsView, ListAPIView):
    """Personnel actif de l'école avec sa carte (filtres `search` et `card`)."""

    serializer_class = CardStaffSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return IdCard.objects.none()
        data = self.query(CardListQuerySerializer)
        items = cards.staff_list().prefetch_related(_ordered_cards())
        if data.get("search"):
            items = items.filter(
                _words(data["search"], "user__last_name", "user__middle_name", "user__first_name")
            )
        if data.get("card") == "active":
            items = items.filter(cards.has_active_card("member"))
        elif data.get("card") == "none":
            items = items.filter(~cards.has_active_card("member"))
        return items


@extend_schema(tags=["attendance"])
class CardSummaryView(_CardsView):
    @extend_schema(responses={200: CardSummarySerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Compteurs de l'écran « Cartes » : actives, élèves sans carte, perdues cette année,
        cartes à réimprimer."""
        return Response(CardSummarySerializer(cards.summary()).data)


@extend_schema(tags=["attendance"])
class CardPrintView(_CardsView):
    @extend_schema(
        request=CardPrintSerializer, responses={201: CardPrintResultSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Émet une carte pour chaque personne choisie (l'ancienne est remplacée) et prépare le
        PDF à ouvrir aussitôt à `url` : le jeton du QR n'existe que dans ce PDF, jamais gardé
        en clair. Au plus 100 cartes à la fois ; planches A4 (10 élèves, 9 membres du
        personnel) ou une carte par page. Photo exigée par l'école : les personnes sans photo
        officielle sont laissées de côté (`without_photo`), 409 si plus personne ne reste."""
        serializer = CardPrintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Avant d'émettre : des cartes émises sans PDF ne s'imprimeraient plus jamais.
        if printing.busy() is not None:
            raise BusinessError(PRINT_BUSY)
        chosen = cards.select(
            students=data["students"],
            members=data["members"],
            class_group=data.get("class_group"),
            missing_only=data["missing_only"],
            missing=data.get("missing"),
            require_photo=request.school.card["require_photo"],
        )
        if chosen.without_photo and not (chosen.enrollments or chosen.members):
            raise BusinessError(cards.NO_PHOTO, without_photo=chosen.without_photo)
        issued = cards.issue(
            actor=request.user, enrollments=chosen.enrollments, members=chosen.members
        )
        head, bodies = cards.document(
            issued, {item.student_id: item for item in chosen.enrollments}, data["layout"]
        )
        path = PRINT_PATH.format(batch=uuid7())
        name = f"{_('cards')}-{timezone.localdate():%Y%m%d}.pdf"
        refused = printing.prepare_at(path, request.user, head, bodies, name)
        if refused is not None:
            raise BusinessError(PRINT_BUSY)
        result = {
            "issued": len(issued),
            "remaining": chosen.remaining,
            "without_photo": chosen.without_photo,
            "url": f"{path}?output=pdf",
        }
        return Response(CardPrintResultSerializer(result).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["attendance"])
class CardPrintFileView(_CardsView):
    @extend_schema(responses={410: ErrorSerializer, **ERRORS})
    def get(self, request: Request, batch) -> Response:
        """PDF des cartes que l'on vient d'émettre : servi par l'impression en tâche de fond
        (page d'attente puis PDF) dans les 10 minutes ; ensuite, ou pour un autre compte, 410."""
        raise BusinessError(PRINT_EXPIRED)


@extend_schema(tags=["attendance"])
class CardRevokeView(_CardsView):
    @extend_schema(request=CardRevokeSerializer, responses={200: CardSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Carte perdue ou départ : refusée à tous les pointages dès maintenant (au journal)."""
        serializer = CardRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        card = get_object_or_404(IdCard.objects, pk=pk)
        card = cards.revoke(card, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(CardSerializer(card).data)


@extend_schema(tags=["attendance"])
class RosterView(GenericAPIView):
    permission_classes = [HasSchoolPermission]
    required_module = "attendance"
    required_permission = ATTENDANCE_SCAN

    @extend_schema(parameters=[RosterQuerySerializer], responses={200: RosterSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Liste de l'appareil de pointage : élèves inscrits (par pages de 1 000) et personnel,
        avec l'empreinte de leur carte active et leur matricule (saisie à la main). Rien n'est
        envoyé si `version` est celle de l'appareil ; une version changée en cours de pages :
        reprendre depuis la première."""
        params = RosterQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        after, known = params.validated_data.get("after"), params.validated_data.get("version")
        version = cards.roster_version()
        check = matricule.has_check(request.school.matricule_format)
        if after is None and known == version:
            return Response(
                {
                    "version": version,
                    "unchanged": True,
                    "students": [],
                    "staff": [],
                    "next": None,
                    "matricule_check": check,
                }
            )
        students = cards.roster_students(after)
        has_more = len(students) > cards.ROSTER_PAGE
        students = students[: cards.ROSTER_PAGE]
        return Response(
            {
                "version": version,
                "unchanged": False,
                "students": RosterStudentSerializer(students, many=True).data,
                "staff": RosterStaffSerializer(
                    cards.roster_staff() if after is None else [], many=True
                ).data,
                "next": students[-1].student_id if has_more else None,
                "matricule_check": check,
            }
        )


class _PhotoView(GenericAPIView):
    """Photo officielle (carte, tablette de la porte) : lue avec le droit de pointer ou celui des
    cartes ; prise et changée avec celui des cartes seulement (séance photo), au journal. Jamais
    par la personne elle-même."""

    permission_classes = [HasSchoolPermission]
    required_module = "attendance"
    parser_classes = [MultiPartParser]

    @property
    def required_permission(self):
        if self.request.method == "GET":
            return [ATTENDANCE_SCAN, ATTENDANCE_CARDS]
        return ATTENDANCE_CARDS

    def holder(self, pk):
        raise NotImplementedError

    def field(self, holder):
        raise NotImplementedError

    def save(self, holder, photo, actor):
        raise NotImplementedError

    def get(self, request: Request, pk) -> Response:
        response = image_response(self.field(self.holder(pk)))
        if response is None:
            raise Http404
        return response

    def post(self, request: Request, pk) -> Response:
        holder = self.holder(pk)
        serializer = PhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        holder = self.save(holder, serializer.validated_data["photo"], request.user)
        return Response({"photo": cards.photo_url(holder)})


PHOTO_SCHEMA = {
    "get": extend_schema(
        responses={
            (200, "image/*"): OpenApiResponse(OpenApiTypes.BINARY, description="PNG ou JPEG."),
            **ERRORS,
        }
    ),
    "post": extend_schema(
        request={"multipart/form-data": PhotoUploadSerializer},
        responses={200: PhotoResultSerializer, **WRITE_ERRORS},
    ),
}


@extend_schema_view(**PHOTO_SCHEMA)
@extend_schema(tags=["attendance"])
class StudentPhotoView(_PhotoView):
    """Photo officielle d'un élève de l'école (la même que sur sa fiche)."""

    def holder(self, pk):
        return get_object_or_404(Student.objects, pk=pk)

    def field(self, holder):
        return holder.photo

    def save(self, holder, photo, actor):
        return students_services.set_photo(holder, photo, actor=actor)


@extend_schema_view(**PHOTO_SCHEMA)
@extend_schema(tags=["attendance"])
class StaffPhotoView(_PhotoView):
    """Photo officielle d'un membre actif du personnel (carte de service)."""

    def holder(self, pk):
        return get_object_or_404(cards.staff(), pk=pk)

    def field(self, holder):
        return holder.photo

    def save(self, holder, photo, actor):
        return accounts_services.set_photo(holder, photo, actor=actor)


# Suivi des présences (6.5), corrections et justifications (6.6)


class _FollowView(GenericAPIView):
    """Lecture : `attendance.view` ; écriture : `attendance.correct`."""

    permission_classes = [HasSchoolPermission]
    required_module = "attendance"

    @property
    def required_permission(self) -> str:
        return ATTENDANCE_VIEW if self.request.method in ("GET", "HEAD") else ATTENDANCE_CORRECT

    def query(self, serializer_class) -> dict:
        params = serializer_class(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return params.validated_data


@extend_schema(tags=["attendance"])
class DayView(_FollowView):
    @extend_schema(parameters=[DayQuerySerializer], responses={200: DaySerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Un jour à l'entrée (aujourd'hui par défaut) : présents, retards, absents (justifiés
        ou non), personnel, et chaque classe. Calculé à la demande, rien n'est stocké."""
        day = self.query(DayQuerySerializer).get("date") or timezone.localdate()
        return Response(DaySerializer(reports.day_summary(day)).data)


@extend_schema(tags=["attendance"], parameters=[AbsencesQuerySerializer])
class AbsencesView(_FollowView, ListAPIView):
    """Absents d'un jour (par classe et nom), avec leurs absences non justifiées de l'année ;
    filtres `class_group` et `state`."""

    serializer_class = AbsenceSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return IdCard.objects.none()
        data = self.query(AbsencesQuerySerializer)
        self.day = data.get("date") or timezone.localdate()
        return reports.absents(self.day, data.get("class_group"), data.get("state"))

    def list(self, request: Request, *args, **kwargs) -> Response:
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset.enrollments)
        rows = reports.absence_rows(self.day, page, queryset.states)
        return self.get_paginated_response(AbsenceSerializer(rows, many=True).data)


@extend_schema(tags=["attendance"], parameters=[DayQuerySerializer])
class StaffDayView(_FollowView, ListAPIView):
    """Personnel actif un jour : arrivé, en retard ou absent (corrections comprises)."""

    serializer_class = StaffDaySerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return IdCard.objects.none()
        self.day = self.query(DayQuerySerializer).get("date") or timezone.localdate()
        return cards.staff().select_related("user").order_by("user__last_name", "user__first_name")

    def list(self, request: Request, *args, **kwargs) -> Response:
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            StaffDaySerializer(reports.staff_rows(self.day, page), many=True).data
        )


@extend_schema(tags=["attendance"], parameters=[CorrectionQuerySerializer])
class CorrectionsView(_FollowView, ListAPIView):
    """Journal des corrections, plus récentes d'abord (filtres `date_from`, `date_to`)."""

    serializer_class = CorrectionSerializer

    def get_queryset(self):
        items = AttendanceCorrection.objects.select_related(
            "session", "student", "member__user", "created_by"
        )
        if getattr(self, "swagger_fake_view", False):
            return items
        data = self.query(CorrectionQuerySerializer)
        if data.get("date_from"):
            items = items.filter(session__date__gte=data["date_from"])
        if data.get("date_to"):
            items = items.filter(session__date__lte=data["date_to"])
        return items

    @extend_schema(
        request=CorrectionWriteSerializer, responses={201: CorrectionSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Corrige la présence d'une personne un jour de classe (« présent, carte oubliée ») :
        une ligne de plus au journal, jamais une modification du passage ; au journal d'audit."""
        data = CorrectionWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        correction = corrections.correct(
            actor=request.user,
            day=values["date"],
            status=values["status"],
            reason=values["reason"],
            student=values.get("student"),
            member=values.get("member"),
        )
        correction = self.get_queryset().get(pk=correction.pk)
        return Response(CorrectionSerializer(correction).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["attendance"], parameters=[JustificationQuerySerializer])
class JustificationsView(_FollowView, ListAPIView):
    """Justifications d'absence, plus récentes d'abord (filtres `status`, `student`) ; l'école
    note celle d'un parent venu avec un mot (acceptée d'emblée)."""

    serializer_class = JustificationSerializer
    parser_classes = [MultiPartParser, JSONParser]

    def get_queryset(self):
        items = AbsenceJustification.objects.select_related("student", "decided_by")
        if getattr(self, "swagger_fake_view", False):
            return items
        data = self.query(JustificationQuerySerializer)
        if data.get("status"):
            items = items.filter(status=data["status"])
        if data.get("student"):
            items = items.filter(student_id=data["student"])
        return items

    @extend_schema(
        request={"multipart/form-data": SchoolJustificationSerializer},
        responses={201: JustificationSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        data = SchoolJustificationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        justification = corrections.justify(
            actor=request.user, by_school=True, **data.validated_data
        )
        return Response(JustificationSerializer(justification).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["attendance"])
class JustificationDecideView(_FollowView):
    @extend_schema(
        request=JustificationDecisionSerializer,
        responses={200: JustificationSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request, pk) -> Response:
        """Accepte ou refuse une justification en attente ; le parent voit la réponse."""
        data = JustificationDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        justification = get_object_or_404(AbsenceJustification.objects, pk=pk)
        justification = corrections.decide(
            justification,
            actor=request.user,
            accept=data.validated_data["accept"],
            note=data.validated_data["note"],
        )
        return Response(JustificationSerializer(justification).data)


@extend_schema(tags=["attendance"])
class JustificationDocumentView(_FollowView):
    @extend_schema(responses={(200, "application/octet-stream"): bytes, **ERRORS})
    def get(self, request: Request, pk) -> FileResponse:
        """Le certificat (photo ou PDF), lu seulement par le personnel de l'école."""
        justification = get_object_or_404(AbsenceJustification.objects, pk=pk)
        if not justification.document:
            raise Http404
        return reports.document_response(justification)


@extend_schema(tags=["attendance"])
class ExportView(_FollowView):
    @extend_schema(parameters=[PeriodQuerySerializer], responses={**XLSX_RESPONSE, **ERRORS})
    def get(self, request: Request):
        """Rapport d'une période (une classe ou toute l'école) : jours de classe, à l'heure,
        retards, absences, justifiées et taux de chaque élève."""
        data = self.query(PeriodQuerySerializer)
        content, name = reports.export(data["date_from"], data["date_to"], data.get("class_group"))
        return file_response(content, XLSX, name)
