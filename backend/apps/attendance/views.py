"""Cartes (6.1, A.5) et liste de l'appareil de pointage (6.3). Droits `attendance.cards`
(cartes) et `attendance.scan` (liste) ; les passages arrivent par la synchronisation
(`attendance.scan`, `POST /api/sync/push/`)."""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import ATTENDANCE_CARDS, ATTENDANCE_SCAN
from apps.attendance import cards
from apps.attendance.models import IdCard
from apps.attendance.serializers import (
    CardListQuerySerializer,
    CardPrintResultSerializer,
    CardPrintSerializer,
    CardRevokeSerializer,
    CardSerializer,
    CardStaffSerializer,
    CardStudentSerializer,
    CardSummarySerializer,
    RosterQuerySerializer,
    RosterSerializer,
    RosterStaffSerializer,
    RosterStudentSerializer,
)
from apps.core import printing
from apps.core.errors import ApiError, BusinessError, ErrorSerializer
from apps.core.ids import uuid7
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
        """Compteurs de l'écran « Cartes » : actives, élèves sans carte, perdues cette année."""
        return Response(CardSummarySerializer(cards.summary()).data)


@extend_schema(tags=["attendance"])
class CardPrintView(_CardsView):
    @extend_schema(
        request=CardPrintSerializer, responses={201: CardPrintResultSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Émet une carte pour chaque personne choisie (l'ancienne est remplacée) et prépare le
        PDF à ouvrir aussitôt à `url` : le jeton du QR n'existe que dans ce PDF, jamais gardé
        en clair. Au plus 100 cartes à la fois ; planche A4 de 10 ou une carte par page."""
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
        )
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
        result = {"issued": len(issued), "remaining": chosen.remaining, "url": f"{path}?output=pdf"}
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
        if after is None and known == version:
            return Response(
                {"version": version, "unchanged": True, "students": [], "staff": [], "next": None}
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
            }
        )
