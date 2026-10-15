from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import (
    CHARGES_READ,
    CREDITS_READ,
    CREDITS_USE,
    FEES_READ,
    FINANCE_APPROVE_CANCELLATION,
    FINANCE_COLLECT_PAYMENT,
    FINANCE_CONFIGURE_FEES,
    FINANCE_GRANT_DISCOUNT,
    FINANCE_IMPORT_PRIOR_PAYMENTS,
    FINANCE_REQUEST_CANCELLATION,
    FINANCE_SET_EXCHANGE_RATE,
    FINANCE_VIEW_REPORTS,
)
from apps.accounts.views import SchoolViewSet
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import (
    PRINT_RESPONSE,
    XLSX,
    XLSX_RESPONSE,
    file_response,
    print_options,
    render,
)
from apps.core.errors import ErrorSerializer
from apps.finance import (
    dashboard,
    documents,
    prior_payments,
    receipt_register,
    services,
    statements,
    unpaid,
)
from apps.finance.models import (
    CancellationRequest,
    CashRegister,
    CashSession,
    CreditAllocation,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    Payment,
    StudentCredit,
)
from apps.finance.serializers import (
    BalanceSerializer,
    CancellationCreateSerializer,
    CancellationDecisionSerializer,
    CancellationFilterSerializer,
    CancellationReceiptSerializer,
    CancellationRequestSerializer,
    CashCloseSerializer,
    CashClosingDetailSerializer,
    CashClosingSummarySerializer,
    CashRegisterSerializer,
    CashRegisterStateSerializer,
    CashRegisterUpdateSerializer,
    CashSessionClosingSerializer,
    CashSessionOpenSerializer,
    CashSessionSerializer,
    ClosingFilterSerializer,
    ClosingsSummarySerializer,
    CreditSummarySerializer,
    CurrentCashSessionSerializer,
    DashboardSerializer,
    DiscountCreateSerializer,
    DiscountRevokeSerializer,
    DiscountSerializer,
    ExchangeRateCreateSerializer,
    ExchangeRateSerializer,
    FeeRuleCreateSerializer,
    FeeRuleSerializer,
    FeeRuleUpdateSerializer,
    FeeTypeSerializer,
    FeeTypeWriteSerializer,
    PaymentCreateSerializer,
    PaymentFilterSerializer,
    PaymentReceiptSerializer,
    PaymentSerializer,
    PriorPaymentPreviewSerializer,
    PriorPaymentUploadSerializer,
    ReceiptRegisterSerializer,
    RescheduleSerializer,
    StatementSerializer,
    StudentChargeFilterSerializer,
    StudentChargeSerializer,
    StudentCreditDetailSerializer,
    StudentCreditFilterSerializer,
    StudentCreditSerializer,
    UnpaidExportSerializer,
    UnpaidFilterSerializer,
    UnpaidStudentSerializer,
    UnpaidSummarySerializer,
    YearFilterSerializer,
)
from apps.schools import organisation
from apps.students.models import Enrollment

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
INVALID = {400: ErrorSerializer}
CONFLICT = {409: ErrorSerializer}
YEAR_PARAM = OpenApiParameter(
    "academic_year", str, description="Identifiant de l'année ; absent : l'année en cours."
)


class _FinanceViewSet(SchoolViewSet):
    pagination_class = None
    write_permission: str

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        if self.action in {"list", "retrieve"}:
            return FEES_READ
        return self.write_permission

    def year(self):
        params = YearFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return params.validated_data.get("academic_year") or organisation.current_year()


@extend_schema_view(
    list=extend_schema(responses={200: FeeTypeSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: FeeTypeSerializer, **ERRORS}),
    create=extend_schema(
        request=FeeTypeWriteSerializer,
        responses={201: FeeTypeSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
    partial_update=extend_schema(
        responses={200: FeeTypeSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
    destroy=extend_schema(responses={204: None, **CONFLICT, **ERRORS}),
)
@extend_schema(tags=["finance"])
class FeeTypeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    _FinanceViewSet,
):
    """Types de frais de l'école (« Minerval », « Frais d'atelier ») (E1)."""

    write_permission = FINANCE_CONFIGURE_FEES
    serializer_class = FeeTypeSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FeeType.all_schools.none()
        return FeeType.objects.annotate(rule_count=Count("rules"))

    def get_serializer_class(self):
        if self.action in {"create", "partial_update"}:
            return FeeTypeWriteSerializer
        return FeeTypeSerializer

    def _fee_type(self, fee_type: FeeType, status_code=status.HTTP_200_OK) -> Response:
        fee_type = self.get_queryset().get(pk=fee_type.pk)
        return Response(FeeTypeSerializer(fee_type).data, status=status_code)

    def create(self, request: Request) -> Response:
        serializer = FeeTypeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fee_type = services.create_fee_type(actor=request.user, **serializer.validated_data)
        return self._fee_type(fee_type, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk=None) -> Response:
        fee_type = self.get_object()
        serializer = FeeTypeWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_fee_type(fee_type, actor=request.user, **serializer.validated_data)
        return self._fee_type(fee_type)

    def perform_destroy(self, instance: FeeType) -> None:
        services.delete_fee_type(instance, actor=self.request.user)


@extend_schema_view(
    list=extend_schema(
        parameters=[YEAR_PARAM], responses={200: FeeRuleSerializer(many=True), **ERRORS}
    ),
    retrieve=extend_schema(responses={200: FeeRuleSerializer, **ERRORS}),
    create=extend_schema(
        request=FeeRuleCreateSerializer,
        responses={201: FeeRuleSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
    update=extend_schema(
        request=FeeRuleUpdateSerializer,
        responses={200: FeeRuleSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
    destroy=extend_schema(responses={204: None, **ERRORS}),
)
@extend_schema(tags=["finance"])
class FeeRuleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    _FinanceViewSet,
):
    """Barèmes d'une année, avec leurs tranches (E2) : montant et devise d'un type de frais pour
    toute l'école, un niveau, une option ou une classe."""

    write_permission = FINANCE_CONFIGURE_FEES
    serializer_class = FeeRuleSerializer
    http_method_names = ["get", "post", "put", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FeeRule.all_schools.none()
        queryset = FeeRule.objects.select_related(
            "level", "track", "class_group__level", "class_group__track"
        ).prefetch_related("installments")
        if self.action == "list":
            queryset = queryset.filter(academic_year=self.year())
        return queryset

    def get_serializer_class(self):
        return {"create": FeeRuleCreateSerializer, "update": FeeRuleUpdateSerializer}.get(
            self.action, FeeRuleSerializer
        )

    def _rule(self, rule: FeeRule, status_code=status.HTTP_200_OK) -> Response:
        rule = self.get_queryset().get(pk=rule.pk)
        return Response(FeeRuleSerializer(rule).data, status=status_code)

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = services.create_fee_rule(actor=request.user, **serializer.to_service())
        return self._rule(rule, status.HTTP_201_CREATED)

    def update(self, request: Request, pk=None) -> Response:
        rule = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_fee_rule(rule, actor=request.user, **serializer.to_service())
        return self._rule(rule)

    def perform_destroy(self, instance: FeeRule) -> None:
        services.delete_fee_rule(instance, actor=self.request.user)


@extend_schema_view(
    list=extend_schema(
        parameters=[YEAR_PARAM], responses={200: ExchangeRateSerializer(many=True), **ERRORS}
    ),
    create=extend_schema(
        request=ExchangeRateCreateSerializer,
        responses={201: ExchangeRateSerializer, **INVALID, **ERRORS},
    ),
)
@extend_schema(tags=["finance"])
class ExchangeRateViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, _FinanceViewSet):
    """Taux USD → CDF d'une année (E5), le plus récent d'abord : le premier est le taux en
    vigueur, les suivants l'historique des corrections. Ni modifiable ni effaçable."""

    write_permission = FINANCE_SET_EXCHANGE_RATE
    serializer_class = ExchangeRateSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ExchangeRate.all_schools.none()
        return (
            ExchangeRate.objects.filter(academic_year=self.year())
            .select_related("created_by")
            .order_by("-created_at", "-id")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ExchangeRateCreateSerializer
        return ExchangeRateSerializer

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rate = services.set_exchange_rate(actor=request.user, **serializer.validated_data)
        rate = ExchangeRate.objects.select_related("created_by").get(pk=rate.pk)
        return Response(ExchangeRateSerializer(rate).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        parameters=[StudentChargeFilterSerializer],
        responses={200: StudentChargeSerializer(many=True), **INVALID, **ERRORS},
    )
)
@extend_schema(tags=["finance"])
class StudentChargeViewSet(mixins.ListModelMixin, SchoolViewSet):
    """Frais dus d'une inscription, par date limite (2.6) : ceux des barèmes ou d'un échéancier
    particulier, et les frais retirés (changement de classe, barème modifié) ou remplacés
    (échéancier), gardés pour l'histoire."""

    serializer_class = StudentChargeSerializer
    # Bornée par inscription (quelques dizaines de lignes) : l'écran les veut toutes.
    pagination_class = None

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        return FINANCE_GRANT_DISCOUNT if self.action == "reschedule" else CHARGES_READ

    def list(self, request: Request) -> Response:
        params = StudentChargeFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        charges = services.charges_of(params.validated_data["enrollment"])
        return Response(StudentChargeSerializer(charges, many=True).data)

    @extend_schema(
        parameters=[StudentChargeFilterSerializer],
        responses={200: BalanceSerializer, **INVALID, **ERRORS},
    )
    @action(detail=False)
    def balance(self, request: Request) -> Response:
        """Solde et retards de l'inscription (2.7), par devise : dû après réductions, payé,
        reste, en retard, prochaine échéance."""
        params = StudentChargeFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        charges = services.charges_of(params.validated_data["enrollment"])
        return Response(BalanceSerializer(services.balance(charges)).data)

    @extend_schema(
        parameters=[StudentChargeFilterSerializer],
        responses={200: StudentCreditSerializer(many=True), **INVALID, **ERRORS},
    )
    @action(detail=False)
    def credits(self, request: Request) -> Response:
        """Crédits à traiter de l'inscription (M14), les plus anciens d'abord : proposés à la
        caisse au prochain paiement (3.6.2) et montrés sur la fiche de l'élève."""
        params = StudentChargeFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        items = services.open_credits([params.validated_data["enrollment"]])
        return Response(StudentCreditSerializer(items, many=True).data)

    @extend_schema(
        parameters=[StatementSerializer],
        responses={**PRINT_RESPONSE, **INVALID, **ERRORS},
    )
    @action(detail=False)
    def statement(self, request: Request) -> HttpResponse:
        """Situation financière imprimable (G2), une page par élève (groupée depuis les Impayés) :
        PDF A4 ou son aperçu HTML ; chaque PDF est noté dans le journal d'audit."""
        query = request.query_params
        params = StatementSerializer(
            data={**query.dict(), "enrollment": query.getlist("enrollment")}
        )
        params.is_valid(raise_exception=True)
        data = params.validated_data
        items = statements.statements(data["enrollment"])
        names = [item.enrollment.student.full_name for item in items]
        if data["output"] == "pdf":
            audit.record(
                Action.FINANCE_STATEMENT_PRINTED,
                actor=request.user,
                label=" · ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else ""),
                after={"students": len(items), "enrollments": [str(i) for i in data["enrollment"]]},
            )
        context = documents.statement_document(
            items,
            actor=request.user,
            absolute=request.build_absolute_uri,
            upcoming=data["upcoming"],
            payments=data["payments"],
            hide_paid=data["hide_paid"],
        )
        name = slugify(names[0] if len(names) == 1 else f"situations-{len(names)}")
        return render(
            "finance/statement.html",
            context,
            data["output"],
            f"situation-{name}.pdf",
            print_options(data),
        )

    @extend_schema(
        request=RescheduleSerializer,
        responses={200: StudentChargeSerializer(many=True), **INVALID, **ERRORS},
    )
    @action(detail=False, methods=["post"])
    def reschedule(self, request: Request) -> Response:
        """Échéancier particulier (E4) : ce qui reste dû pour un frais, réorganisé en versements
        de même total ; renvoie tous les frais dus de l'inscription."""
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.to_service()
        enrollment = data.pop("enrollment")
        services.reschedule_charges(enrollment, actor=request.user, **data)
        charges = services.charges_of(enrollment.pk)
        return Response(StudentChargeSerializer(charges, many=True).data)


@extend_schema_view(
    list=extend_schema(
        parameters=[StudentChargeFilterSerializer],
        responses={200: DiscountSerializer(many=True), **INVALID, **ERRORS},
    ),
    create=extend_schema(
        request=DiscountCreateSerializer,
        responses={201: DiscountSerializer, **INVALID, **ERRORS},
    ),
)
@extend_schema(tags=["finance"])
class DiscountViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, SchoolViewSet):
    """Réductions d'une inscription (E3), retirées comprises (jamais effacées)."""

    serializer_class = DiscountSerializer
    # Bornée par inscription (quelques lignes).
    pagination_class = None

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        return CHARGES_READ if self.action == "list" else FINANCE_GRANT_DISCOUNT

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Discount.all_schools.none()
        discounts = Discount.objects.select_related("fee_type", "created_by", "revoked_by")
        if self.action != "list":
            return discounts
        params = StudentChargeFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return discounts.filter(enrollment_id=params.validated_data["enrollment"])

    def create(self, request: Request) -> Response:
        serializer = DiscountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        discount = services.grant_discount(data.pop("enrollment"), actor=request.user, **data)
        discount = self.get_queryset().get(pk=discount.pk)
        return Response(DiscountSerializer(discount).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=DiscountRevokeSerializer,
        responses={200: DiscountSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        """Retirer une réduction, avec son motif : rien n'est effacé."""
        serializer = DiscountRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discount = services.revoke_discount(
            self.get_object(), actor=request.user, **serializer.validated_data
        )
        return Response(DiscountSerializer(self.get_queryset().get(pk=discount.pk)).data)


# Caisses et paiements (F1-F2)


@extend_schema_view(
    list=extend_schema(responses={200: CashRegisterStateSerializer(many=True), **ERRORS}),
    create=extend_schema(
        request=CashRegisterSerializer,
        responses={201: CashRegisterStateSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
    partial_update=extend_schema(
        request=CashRegisterUpdateSerializer,
        responses={200: CashRegisterStateSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
)
@extend_schema(tags=["finance"])
class CashRegisterViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, SchoolViewSet
):
    """Caisses de l'école (M13), avec leur session ouverte : désactivées, jamais effacées ; le
    code ne change pas."""

    serializer_class = CashRegisterStateSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        if self.action == "list":
            return (FINANCE_COLLECT_PAYMENT, FINANCE_CONFIGURE_FEES)
        return FINANCE_CONFIGURE_FEES

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CashRegister.all_schools.none()
        open_sessions = CashSession.objects.filter(closed_at__isnull=True).select_related("cashier")
        return CashRegister.objects.prefetch_related(
            Prefetch("sessions", queryset=open_sessions, to_attr="open_sessions")
        )

    def _register(self, register: CashRegister, status_code=status.HTTP_200_OK) -> Response:
        register = self.get_queryset().get(pk=register.pk)
        return Response(CashRegisterStateSerializer(register).data, status=status_code)

    def create(self, request: Request) -> Response:
        serializer = CashRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        register = services.create_cash_register(actor=request.user, **serializer.validated_data)
        return self._register(register, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk=None) -> Response:
        serializer = CashRegisterUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        register = services.update_cash_register(
            self.get_object(), actor=request.user, **serializer.validated_data
        )
        return self._register(register)


@extend_schema_view(
    create=extend_schema(
        request=CashSessionOpenSerializer,
        responses={201: CashSessionSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
)
@extend_schema(tags=["finance"])
class CashSessionViewSet(mixins.CreateModelMixin, SchoolViewSet):
    """Sessions de caisse du caissier connecté (M13) : ouvrir une caisse, voir celle qui est
    ouverte, la clôturer (F8) ; celles d'un autre caissier sont introuvables."""

    required_permission = FINANCE_COLLECT_PAYMENT
    serializer_class = CashSessionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CashSession.all_schools.none()
        return CashSession.objects.filter(cashier=self.request.user)

    def create(self, request: Request) -> Response:
        serializer = CashSessionOpenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        session = services.open_cash_session(
            actor=request.user, cash_register=data["cash_register"], session_id=data.get("id")
        )
        return Response(CashSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: CurrentCashSessionSerializer, **ERRORS})
    @action(detail=False)
    def current(self, request: Request) -> Response:
        """La caisse ouverte du caissier (ou `null`), ses totaux et le taux des encaissements."""
        session = services.open_session_of(request.user)
        rate, fallback = services.payment_rate()
        data = {
            "session": session,
            "totals": services.session_totals(session) if session else [],
            "rate": rate.rate if rate else None,
            "rate_is_fallback": fallback,
        }
        return Response(CurrentCashSessionSerializer(data).data)

    @extend_schema(responses={200: CashClosingSummarySerializer, **ERRORS})
    @action(detail=True)
    def closing(self, request: Request, pk=None) -> Response:
        """Ce que montre la clôture de la session : attendu par devise, détail, reçus,
        annulations ; la clôture elle-même une fois faite."""
        summary = services.closing_summary(self.get_object())
        return Response(CashClosingSummarySerializer(summary).data)

    @extend_schema(
        request=CashCloseSerializer,
        responses={200: CashClosingSummarySerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk=None) -> Response:
        """Clôture la session (F8) : l'argent compté par devise, l'explication d'un écart."""
        session = self.get_object()
        serializer = CashCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.close_cash_session(session, actor=request.user, **serializer.to_service())
        session.refresh_from_db()
        return Response(CashClosingSummarySerializer(services.closing_summary(session)).data)


# Clôtures vues par le comptable (3.8.3, M16)


@extend_schema_view(
    list=extend_schema(
        parameters=[ClosingFilterSerializer],
        responses={200: CashSessionClosingSerializer(many=True), **INVALID, **ERRORS},
    ),
    retrieve=extend_schema(responses={200: CashClosingDetailSerializer, **ERRORS}),
)
@extend_schema(tags=["finance"])
class CashClosingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Clôtures de caisse vues par le comptable (M16), en lecture seule : les sessions de tous
    les caissiers, par mois, avec l'attendu, le compté et l'écart par devise, l'état, les
    paiements arrivés après la clôture ; le détail et le bordereau ; l'export Excel."""

    required_permission = FINANCE_VIEW_REPORTS
    serializer_class = CashSessionClosingSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CashSession.all_schools.none()
        if self.action != "list":
            return CashSession.objects.select_related("cash_register", "cashier")
        return services.cash_sessions(**self._filters())

    def _filters(self) -> dict:
        params = ClosingFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return {
            "month": params.validated_data.get("month") or services.today(),
            "cash_register": params.validated_data.get("cash_register"),
        }

    def list(self, request: Request) -> Response:
        page = self.paginate_queryset(self.get_queryset())
        sessions = services.with_closings(page)
        return self.get_paginated_response(self.get_serializer(sessions, many=True).data)

    def retrieve(self, request: Request, pk=None) -> Response:
        detail = services.closing_detail(self.get_object())
        return Response(CashClosingDetailSerializer(detail).data)

    @extend_schema(
        parameters=[ClosingFilterSerializer],
        responses={200: ClosingsSummarySerializer, **INVALID, **ERRORS},
    )
    @action(detail=False)
    def summary(self, request: Request) -> Response:
        """Chiffres de l'écran pour le mois, et les sessions pas clôturées (bandeau)."""
        summary = services.closings_summary(**self._filters())
        return Response(ClosingsSummarySerializer(summary).data)

    @extend_schema(
        parameters=[ClosingFilterSerializer], responses={**XLSX_RESPONSE, **INVALID, **ERRORS}
    )
    @action(detail=False, pagination_class=None)
    def export(self, request: Request):
        """Export Excel du mois (une ligne par session, montants en nombres)."""
        filters = self._filters()
        content = documents.closings_workbook(**filters)
        return file_response(content, XLSX, f"clotures-{filters['month']:%Y-%m}.xlsx")


@extend_schema_view(
    list=extend_schema(parameters=[PaymentFilterSerializer]),
    retrieve=extend_schema(responses={200: PaymentReceiptSerializer, **ERRORS}),
    create=extend_schema(
        request=PaymentCreateSerializer,
        responses={
            200: PaymentReceiptSerializer,
            201: PaymentReceiptSerializer,
            **INVALID,
            **CONFLICT,
            **ERRORS,
        },
    ),
)
@extend_schema(tags=["finance"])
class PaymentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, SchoolViewSet
):
    """Paiements (F1-F2), les plus récents d'abord ; ni modifiables ni effaçables. Sans
    `finance.view_reports`, seulement ceux des sessions du caissier. Création : 201, ou 200 si ce
    paiement (même `id`) était déjà enregistré. Création, lecture et réimpression rendent le
    reçu (F3)."""

    serializer_class = PaymentSerializer

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        if self.action == "create":
            return FINANCE_COLLECT_PAYMENT
        return (FINANCE_COLLECT_PAYMENT, FINANCE_VIEW_REPORTS)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Payment.all_schools.none()
        payments = services.receipt_payments()
        if FINANCE_VIEW_REPORTS not in school_access(self.request).permissions:
            payments = payments.filter(cash_session__cashier=self.request.user)
        if self.action == "reprint":
            # Une reprise (E6) n'a pas de reçu : rien à réimprimer.
            return payments.filter(origin=Payment.Origin.CASH)
        if self.action != "list":
            return payments
        params = PaymentFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        if "session" in filters:
            payments = payments.filter(cash_session_id=filters["session"])
        if "enrollment" in filters:
            payments = payments.filter(enrollment_id=filters["enrollment"])
        if "origin" in filters:
            payments = payments.filter(origin=filters["origin"])
        if search := filters.get("search", "").strip():
            payments = payments.filter(
                Q(receipt_number__icontains=search)
                | Q(enrollment__student__matricule__icontains=search)
                | Q(enrollment__student__last_name__icontains=search)
                | Q(enrollment__student__middle_name__icontains=search)
                | Q(enrollment__student__first_name__icontains=search)
            )
        return payments

    def create(self, request: Request) -> Response:
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.to_service()
        payment, created = services.record_payment(
            data.pop("enrollment"), actor=request.user, **data
        )
        payment = self.get_queryset().get(pk=payment.pk)
        return self._receipt(payment, status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def retrieve(self, request: Request, pk=None) -> Response:
        return self._receipt(self.get_object())

    @extend_schema(request=None, responses={200: PaymentReceiptSerializer, **CONFLICT, **ERRORS})
    @action(detail=True, methods=["post"])
    def reprint(self, request: Request, pk=None) -> Response:
        """Réimpression du reçu (F6) : le même reçu, marqué DUPLICATA par l'appareil, noté au
        journal ; 409 `payment_cancelled` pour un paiement annulé."""
        payment = self.get_object()
        services.reprint_payment(payment, actor=request.user)
        return self._receipt(payment)

    def _receipt(self, payment: Payment, status_code=status.HTTP_200_OK) -> Response:
        payment.balance_after = services.balance_after(payment)
        return Response(PaymentReceiptSerializer(payment).data, status=status_code)


# Crédits d'élèves (3.6.1, M14)


@extend_schema_view(
    list=extend_schema(
        parameters=[StudentCreditFilterSerializer],
        responses={200: StudentCreditSerializer(many=True), **INVALID, **ERRORS},
    ),
    retrieve=extend_schema(responses={200: StudentCreditDetailSerializer, **ERRORS}),
)
@extend_schema(tags=["finance"])
class StudentCreditViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Crédits d'élèves de l'année (M14), les plus récents d'abord : argent reçu en trop, jamais
    perdu. Lire : `finance.view_reports` ou `finance.approve_cancellation` ; utiliser :
    `finance.approve_cancellation`, ou `finance.collect_payment` à la caisse (3.6.2)."""

    serializer_class = StudentCreditSerializer

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        return CREDITS_USE if self.action == "use" else CREDITS_READ

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudentCredit.all_schools.none()
        items = services.credits()
        if self.action != "list":
            return items.prefetch_related(
                Prefetch(
                    "allocations",
                    queryset=CreditAllocation.objects.select_related(
                        "student_charge__fee_type", "created_by"
                    ).order_by("created_at", "student_charge__due_on"),
                )
            )
        params = StudentCreditFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        year = params.validated_data.get("academic_year") or organisation.current_year()
        items = items.filter(enrollment__academic_year=year).order_by("-created_at", "-id")
        state = params.validated_data["state"]
        return items if state == "all" else services.with_state(items, state)

    def retrieve(self, request: Request, pk=None) -> Response:
        return self._detail(self.get_object())

    @extend_schema(
        parameters=[YearFilterSerializer],
        responses={200: CreditSummarySerializer, **INVALID, **ERRORS},
    )
    @action(detail=False)
    def summary(self, request: Request) -> Response:
        """Chiffres de l'écran : crédits à traiter, leur reste par devise, utilisés ce mois."""
        params = YearFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        year = params.validated_data.get("academic_year") or organisation.current_year()
        return Response(CreditSummarySerializer(services.credits_summary(year)).data)

    @extend_schema(
        request=None, responses={200: StudentCreditDetailSerializer, **CONFLICT, **ERRORS}
    )
    @action(detail=True, methods=["post"])
    def use(self, request: Request, pk=None) -> Response:
        """Utiliser le crédit sur les échéances les plus anciennes de sa devise, sans paiement ;
        409 `credit_used`, `credit_voided` ou `nothing_owed`."""
        services.use_credit(self.get_object(), actor=request.user)
        return self._detail(self.get_queryset().get(pk=pk))

    def _detail(self, credit: StudentCredit) -> Response:
        credit.proposal = [
            {
                "student_charge": charge.pk,
                "fee_type_name": charge.fee_type.name,
                "label": charge.label,
                "due_on": charge.due_on,
                "amount_minor": amount,
            }
            for charge, _part, amount in services.credit_proposal(credit)
        ]
        return Response(StudentCreditDetailSerializer(credit).data)


# Annulations (3.8.1, F7)

CANCELLATIONS_READ = (FINANCE_REQUEST_CANCELLATION, FINANCE_APPROVE_CANCELLATION)


@extend_schema_view(
    list=extend_schema(parameters=[CancellationFilterSerializer]),
    retrieve=extend_schema(responses={200: CancellationRequestSerializer, **ERRORS}),
    create=extend_schema(
        request=CancellationCreateSerializer,
        responses={
            200: CancellationRequestSerializer,
            201: CancellationRequestSerializer,
            **INVALID,
            **CONFLICT,
            **ERRORS,
        },
    ),
)
@extend_schema(tags=["finance"])
class CancellationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, SchoolViewSet
):
    """Demandes d'annulation de paiements (F7), les plus récentes d'abord. Demander :
    `finance.request_cancellation` (sans `finance.view_reports`, seulement pour ses paiements) ;
    valider ou refuser : `finance.approve_cancellation`, jamais sa propre demande. Sans
    `finance.approve_cancellation`, on ne voit que ses demandes. Création : 201, ou 200 si cette
    demande (même `id`) était déjà enregistrée."""

    serializer_class = CancellationRequestSerializer

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        if self.action == "create":
            return FINANCE_REQUEST_CANCELLATION
        if self.action in {"approve", "reject"}:
            return FINANCE_APPROVE_CANCELLATION
        return CANCELLATIONS_READ

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CancellationRequest.all_schools.none()
        items = services.cancellation_requests()
        if FINANCE_APPROVE_CANCELLATION not in school_access(self.request).permissions:
            items = items.filter(requested_by=self.request.user)
        if self.action in {"receipt", "reprint"}:
            items = items.filter(status=CancellationRequest.Status.APPROVED)
        if self.action != "list":
            return items
        params = CancellationFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return items.filter(status=params.validated_data["status"])

    def create(self, request: Request) -> Response:
        serializer = CancellationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment = data["payment"]
        own = FINANCE_VIEW_REPORTS not in school_access(request).permissions
        if own and payment.cashier_id != request.user.pk:
            raise PermissionDenied()
        item, created = services.request_cancellation(
            payment, actor=request.user, reason=data["reason"], request_id=data.get("id")
        )
        return Response(
            CancellationRequestSerializer(self.get_queryset().get(pk=item.pk)).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        request=CancellationDecisionSerializer,
        responses={200: CancellationReceiptSerializer, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk=None) -> Response:
        """Valider : le paiement est annulé ; rend le reçu d'annulation à imprimer. 409
        `cancellation_decided` ; 403 `own_cancellation` pour sa propre demande."""
        params = CancellationDecisionSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        services.approve_cancellation(
            self.get_object(), actor=request.user, note=params.validated_data["note"]
        )
        return self._receipt(self.get_queryset().get(pk=pk))

    @extend_schema(
        request=CancellationDecisionSerializer,
        responses={200: CancellationRequestSerializer, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk=None) -> Response:
        """Refuser : le paiement reste valable. 409 `cancellation_decided`."""
        params = CancellationDecisionSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        services.reject_cancellation(
            self.get_object(), actor=request.user, note=params.validated_data["note"]
        )
        return Response(CancellationRequestSerializer(self.get_queryset().get(pk=pk)).data)

    @extend_schema(responses={200: CancellationReceiptSerializer, **ERRORS})
    @action(detail=True)
    def receipt(self, request: Request, pk=None) -> Response:
        """Reçu d'annulation (M15) d'une demande validée."""
        return self._receipt(self.get_object())

    @extend_schema(request=None, responses={200: CancellationReceiptSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def reprint(self, request: Request, pk=None) -> Response:
        """Réimpression du reçu d'annulation : le même, marqué DUPLICATA, noté au journal."""
        item = self.get_object()
        services.reprint_cancellation(item.payment.cancellation, actor=request.user)
        return self._receipt(item)

    def _receipt(self, item: CancellationRequest) -> Response:
        item.balance_after = services.balance_after_cancellation(item.payment.cancellation)
        return Response(CancellationReceiptSerializer(item).data)


@extend_schema_view(
    list=extend_schema(
        parameters=[UnpaidFilterSerializer],
        responses={200: UnpaidStudentSerializer(many=True), **INVALID, **ERRORS},
    ),
)
@extend_schema(tags=["finance"])
class UnpaidViewSet(mixins.ListModelMixin, SchoolViewSet):
    """Impayés (G1) : élèves de l'année dont un frais dû est en retard (échéance passée et reste
    > 0), filtrés par classe, frais, tranche, retard et devise ; chiffres clés ; export Excel ou
    PDF (tracé dans le journal d'audit : données personnelles)."""

    required_permission = FINANCE_VIEW_REPORTS
    serializer_class = UnpaidStudentSerializer

    def get_queryset(self):
        return Enrollment.objects.none()

    def _filters(self, serializer=UnpaidFilterSerializer):
        params = serializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return params

    def list(self, request: Request) -> Response:
        rows = unpaid.unpaid_students(self._filters().filters())
        page = unpaid.with_contacts(self.paginate_queryset(rows))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(
        parameters=[UnpaidFilterSerializer],
        responses={200: UnpaidSummarySerializer, **INVALID, **ERRORS},
    )
    @action(detail=False, pagination_class=None)
    def summary(self, request: Request) -> Response:
        """Chiffres clés selon les filtres, et les classes, frais et tranches à proposer."""
        return Response(UnpaidSummarySerializer(unpaid.summary(self._filters().filters())).data)

    @extend_schema(
        parameters=[UnpaidExportSerializer],
        responses={**XLSX_RESPONSE, **PRINT_RESPONSE, **INVALID, **ERRORS},
    )
    @action(detail=False, pagination_class=None)
    def export(self, request: Request) -> HttpResponse:
        """Mêmes filtres que la liste : Excel (une ligne par frais en retard), PDF A4 à
        l'italienne par classe ou en liste unique, ou son aperçu HTML (pas tracé)."""
        params = self._filters(UnpaidExportSerializer)
        data, filters = params.validated_data, params.filters()
        rows = unpaid.with_contacts(unpaid.unpaid_students(filters))
        output = data["output"]
        if output != "html":
            audit.record(
                Action.FINANCE_UNPAID_EXPORTED,
                actor=request.user,
                label=f"{output.upper()} · {filters.class_group or filters.academic_year}",
                after={
                    "output": output,
                    "students": len(rows),
                    **{key: str(value) for key, value in request.query_params.items()},
                },
            )
        name = f"impayes-{slugify(str(filters.class_group or filters.academic_year))}"
        if output == "xlsx":
            return file_response(documents.unpaid_workbook(rows), XLSX, f"{name}.xlsx")
        context = documents.unpaid_document(
            rows,
            filters,
            by_class=data["group"] == "class",
            page_per_class=data["page_per_class"],
            phone=data["phone"],
            detail=data["detail"],
        )
        return render(
            "finance/unpaid.html",
            context,
            output,
            f"{name}.pdf",
            print_options(data, orientation="landscape"),
        )


@extend_schema(tags=["finance"])
class ReceiptRegisterView(APIView):
    """Registre des reçus (DOC.3) : un reçu par ligne, par période et par caisse, totaux par caisse
    et par devise, cachet et signature du chef. Excel, PDF (3 000 reçus au plus) ou aperçu HTML ;
    chaque fichier est tracé dans le journal d'audit (noms d'élèves et montants)."""

    permission_classes = [HasSchoolPermission]
    required_permission = FINANCE_VIEW_REPORTS

    @extend_schema(
        parameters=[ReceiptRegisterSerializer],
        responses={**XLSX_RESPONSE, **PRINT_RESPONSE, **INVALID, **ERRORS},
    )
    def get(self, request: Request) -> HttpResponse:
        params = ReceiptRegisterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        filters, output = params.filters(), params.validated_data["output"]
        limit = (
            receipt_register.MAX_XLSX_ROWS if output == "xlsx" else receipt_register.MAX_PDF_ROWS
        )
        rows = list(receipt_register.payments(filters)[: limit + 1])
        if len(rows) > limit:
            raise serializers.ValidationError(
                {
                    "end": _(
                        "Too many receipts for one file (%(limit)s at most): shorten the period."
                    )
                    % {"limit": limit}
                }
            )
        found = receipt_register.groups(rows)
        if output != "html":
            audit.record(
                Action.FINANCE_RECEIPT_REGISTER_EXPORTED,
                actor=request.user,
                label=f"{output.upper()} · {filters.start:%d/%m/%Y} → {filters.end:%d/%m/%Y}",
                after={
                    "output": output,
                    "receipts": len(rows),
                    **{key: str(value) for key, value in request.query_params.items()},
                },
            )
        name = f"registre-des-recus-{filters.start:%Y%m%d}-{filters.end:%Y%m%d}"
        if output == "xlsx":
            return file_response(documents.receipt_register_workbook(found), XLSX, f"{name}.xlsx")
        context = documents.receipt_register_document(found, filters, actor=request.user)
        return render(
            "finance/receipt_register.html",
            context,
            output,
            f"{name}.pdf",
            print_options(params.validated_data, orientation="landscape"),
        )


@extend_schema(tags=["finance"])
class DashboardView(APIView):
    """Tableau de bord du directeur (G3) : encaissé aujourd'hui, ce mois et jour par jour,
    impayés échus, recouvrement et effectifs par classe, derniers paiements, alertes selon les
    seuils de l'école (M5). Lecture seule, aussi pour le promoteur."""

    permission_classes = [HasSchoolPermission]
    required_permission = FINANCE_VIEW_REPORTS

    @extend_schema(responses={200: DashboardSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        return Response(DashboardSerializer(dashboard.overview()).data)


@extend_schema(tags=["finance"])
class PriorPaymentsView(APIView):
    """Reprise en cours d'année (E6) : ce que chaque élève avait payé avant que l'école
    n'utilise l'application, importé d'un fichier. Sans `expected` : aperçu (200), rien n'est
    écrit. Avec les totaux de l'aperçu : enregistré (201) hors caisse et sans reçu, lignes en
    erreur laissées ; 409 `preview_outdated` si le résultat n'est plus celui de l'aperçu."""

    permission_classes = [HasSchoolPermission]
    required_permission = FINANCE_IMPORT_PRIOR_PAYMENTS
    parser_classes = [MultiPartParser]

    @extend_schema(
        request={"multipart/form-data": PriorPaymentUploadSerializer},
        responses={
            200: PriorPaymentPreviewSerializer,
            201: PriorPaymentPreviewSerializer,
            **INVALID,
            **CONFLICT,
            **ERRORS,
        },
    )
    def post(self, request: Request) -> Response:
        params = PriorPaymentUploadSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        file, expected = params.validated_data["file"], params.validated_data.get("expected")
        if expected is None:
            preview = prior_payments.check(file)
        else:
            preview = prior_payments.record(file, actor=request.user, expected=expected)
        errors = preview.errors
        data = {
            "recorded": expected is not None,
            "ready_count": len(preview.ready),
            "error_count": len(errors),
            "empty_count": preview.empty,
            "totals": preview.totals,
            "errors": errors[: prior_payments.MAX_ERRORS],
            "ready": preview.ready[: prior_payments.MAX_READY],
        }
        return Response(
            PriorPaymentPreviewSerializer(data).data,
            status=status.HTTP_200_OK if expected is None else status.HTTP_201_CREATED,
        )


@extend_schema(tags=["finance"])
class PriorPaymentsTemplateView(APIView):
    """Modèle Excel de la reprise, déjà garni : les élèves de l'année et leur reste à payer."""

    permission_classes = [HasSchoolPermission]
    required_permission = FINANCE_IMPORT_PRIOR_PAYMENTS

    @extend_schema(responses={**XLSX_RESPONSE, **CONFLICT, **ERRORS})
    def get(self, request: Request) -> HttpResponse:
        return file_response(prior_payments.template_workbook(), XLSX, "reprise-paiements.xlsx")
