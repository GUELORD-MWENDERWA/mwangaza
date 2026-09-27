from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.roles import (
    FINANCE_CONFIGURE_FEES,
    FINANCE_GRANT_DISCOUNT,
    FINANCE_SET_EXCHANGE_RATE,
)
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ErrorSerializer
from apps.finance import services
from apps.finance.models import ExchangeRate, FeeRule, FeeType
from apps.finance.serializers import (
    ExchangeRateCreateSerializer,
    ExchangeRateSerializer,
    FeeRuleCreateSerializer,
    FeeRuleSerializer,
    FeeRuleUpdateSerializer,
    FeeTypeSerializer,
    FeeTypeWriteSerializer,
    YearFilterSerializer,
)
from apps.schools import organisation

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
INVALID = {400: ErrorSerializer}
CONFLICT = {409: ErrorSerializer}
YEAR_PARAM = OpenApiParameter(
    "academic_year", str, description="Identifiant de l'année ; absent : l'année en cours."
)
# Écran « Frais et barèmes » : lu avec l'un des droits de son entrée du menu.
FEES_READ = (FINANCE_CONFIGURE_FEES, FINANCE_SET_EXCHANGE_RATE, FINANCE_GRANT_DISCOUNT)


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
