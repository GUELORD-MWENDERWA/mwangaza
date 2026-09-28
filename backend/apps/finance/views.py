from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import school_access
from apps.accounts.roles import (
    CHARGES_READ,
    FEES_READ,
    FINANCE_COLLECT_PAYMENT,
    FINANCE_CONFIGURE_FEES,
    FINANCE_GRANT_DISCOUNT,
    FINANCE_SET_EXCHANGE_RATE,
    FINANCE_VIEW_REPORTS,
)
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ErrorSerializer
from apps.finance import services
from apps.finance.models import (
    CashRegister,
    CashSession,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    Payment,
    PaymentAllocation,
    PaymentCancellation,
)
from apps.finance.serializers import (
    BalanceSerializer,
    CashRegisterSerializer,
    CashRegisterStateSerializer,
    CashRegisterUpdateSerializer,
    CashSessionOpenSerializer,
    CashSessionSerializer,
    CurrentCashSessionSerializer,
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
    PaymentSerializer,
    RescheduleSerializer,
    StudentChargeFilterSerializer,
    StudentChargeSerializer,
    YearFilterSerializer,
)
from apps.schools import organisation

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
    ouverte. La clôture vient en 3.8."""

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


@extend_schema_view(
    list=extend_schema(parameters=[PaymentFilterSerializer]),
    create=extend_schema(
        request=PaymentCreateSerializer,
        responses={
            200: PaymentSerializer,
            201: PaymentSerializer,
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
    paiement (même `id`) était déjà enregistré."""

    serializer_class = PaymentSerializer

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        if self.action == "create":
            return FINANCE_COLLECT_PAYMENT
        return (FINANCE_COLLECT_PAYMENT, FINANCE_VIEW_REPORTS)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Payment.all_schools.none()
        payments = (
            Payment.objects.select_related(
                "enrollment__student",
                "enrollment__class_group__level",
                "enrollment__class_group__track",
                "cash_session__cash_register",
                "cashier",
            )
            .prefetch_related(
                Prefetch(
                    "allocations",
                    queryset=PaymentAllocation.objects.select_related("student_charge__fee_type"),
                )
            )
            .annotate(
                is_cancelled=Exists(PaymentCancellation.objects.filter(payment=OuterRef("pk")))
            )
            .order_by("-paid_at", "-id")
        )
        if FINANCE_VIEW_REPORTS not in school_access(self.request).permissions:
            payments = payments.filter(cash_session__cashier=self.request.user)
        if self.action != "list":
            return payments
        params = PaymentFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        if "session" in filters:
            payments = payments.filter(cash_session_id=filters["session"])
        if "enrollment" in filters:
            payments = payments.filter(enrollment_id=filters["enrollment"])
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
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
