from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import FINANCE_MANAGE_BUDGET, FINANCE_VIEW_REPORTS
from apps.accounts.views import SchoolViewSet
from apps.core.documents import XLSX, XLSX_RESPONSE, file_response
from apps.core.errors import BusinessError, ErrorSerializer
from apps.core.tenancy import require_current_school
from apps.finance import budget
from apps.finance.budget_serializers import (
    BudgetQuerySerializer,
    BudgetReportSerializer,
    BudgetWriteSerializer,
    TreasuryMovementCreateSerializer,
    TreasuryMovementFilterSerializer,
    TreasuryMovementSerializer,
)
from apps.finance.expense_serializers import ExpenseCancelSerializer
from apps.finance.models import TreasuryMovement
from apps.finance.prior_payments import NO_CURRENT_YEAR
from apps.schools import organisation

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
INVALID = {400: ErrorSerializer}
CONFLICT = {409: ErrorSerializer}


def _year(year):
    """L'année demandée, sinon l'année en cours ; 409 `no_current_year` s'il n'y en a pas."""
    year = year or organisation.current_year()
    if year is None:
        raise BusinessError(NO_CURRENT_YEAR)
    return year


def _query(request: Request):
    params = BudgetQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    data = params.validated_data
    currency = data.get("currency") or budget.currencies(require_current_school())[0]
    return _year(data.get("academic_year")), currency


class BudgetView(APIView):
    """Budget et rapports de l'année (FIN.3), pour une devise : prévu et dépensé par catégorie,
    entrées et sorties par mois, solde des comptes (toutes devises). Lu avec
    `finance.view_reports` ; budget réglé avec `finance.manage_budget`. Jamais de somme entre
    deux devises."""

    permission_classes = [HasSchoolPermission]

    @property
    def required_permission(self) -> str:
        return FINANCE_VIEW_REPORTS if self.request.method == "GET" else FINANCE_MANAGE_BUDGET

    @extend_schema(
        parameters=[BudgetQuerySerializer],
        responses={200: BudgetReportSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    def get(self, request: Request) -> Response:
        year, currency = _query(request)
        return Response(BudgetReportSerializer(budget.report(year, currency)).data)

    @extend_schema(
        request=BudgetWriteSerializer,
        responses={200: BudgetReportSerializer, **INVALID, **ERRORS},
    )
    def put(self, request: Request) -> Response:
        """Prévu de chaque catégorie envoyée pour l'année et la devise ; 0 retire la ligne, les
        catégories absentes ne changent pas."""
        serializer = BudgetWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        budget.set_budget(
            actor=request.user,
            academic_year=data["academic_year"],
            currency=data["currency"],
            amounts={line["category"]: line["amount_minor"] for line in data["lines"]},
        )
        report = budget.report(data["academic_year"], data["currency"])
        return Response(BudgetReportSerializer(report).data)


class BudgetExportView(APIView):
    """Classeur Excel de l'année (FIN.3) : budget, entrées et sorties par mois, comptes, toutes
    devises, chacune dans sa colonne."""

    permission_classes = [HasSchoolPermission]
    required_permission = FINANCE_VIEW_REPORTS

    @extend_schema(
        parameters=[TreasuryMovementFilterSerializer],
        responses={**XLSX_RESPONSE, **INVALID, **CONFLICT, **ERRORS},
    )
    def get(self, request: Request):
        params = TreasuryMovementFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        year = _year(params.validated_data.get("academic_year"))
        name = f"budget-{require_current_school().code}-{year.name}.xlsx"
        return file_response(budget.workbook(year), XLSX, name)


@extend_schema_view(
    list=extend_schema(
        parameters=[TreasuryMovementFilterSerializer],
        responses={200: TreasuryMovementSerializer(many=True), **INVALID, **CONFLICT, **ERRORS},
    ),
    create=extend_schema(
        request=TreasuryMovementCreateSerializer,
        responses={201: TreasuryMovementSerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
)
class TreasuryMovementViewSet(mixins.ListModelMixin, SchoolViewSet):
    """Soldes de départ et virements entre les comptes de l'école (FIN.3), les plus récents
    d'abord. Lus avec `finance.view_reports` ; saisis et annulés avec `finance.manage_budget`.
    Rien ne s'efface : annuler écrit une ligne liée avec motif."""

    serializer_class = TreasuryMovementSerializer

    @property
    def required_permission(self) -> str:
        return FINANCE_VIEW_REPORTS if self.action == "list" else FINANCE_MANAGE_BUDGET

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TreasuryMovement.all_schools.none()
        if self.action == "list":
            params = TreasuryMovementFilterSerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            return budget.movements(_year(params.validated_data.get("academic_year")))
        return TreasuryMovement.objects.all()

    def create(self, request: Request) -> Response:
        serializer = TreasuryMovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        movement = budget.record_movement(
            actor=request.user, **{**data, "academic_year": _year(data.get("academic_year"))}
        )
        return Response(TreasuryMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ExpenseCancelSerializer,
        responses={200: TreasuryMovementSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        """Annuler un solde de départ ou un virement (motif). 409 `treasury_movement_cancelled`
        si déjà fait."""
        params = ExpenseCancelSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        movement = self.get_object()
        budget.cancel_movement(movement, actor=request.user, reason=params.validated_data["reason"])
        movement = TreasuryMovement.objects.select_related("recorded_by", "cancellation").get(
            pk=movement.pk
        )
        return Response(TreasuryMovementSerializer(movement).data)
