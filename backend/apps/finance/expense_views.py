from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import (
    EXPENSES_READ,
    FINANCE_APPROVE_EXPENSE,
    FINANCE_CANCEL_EXPENSE,
    FINANCE_COLLECT_PAYMENT,
    FINANCE_CONFIGURE_FEES,
    FINANCE_RECORD_EXPENSE,
    FINANCE_VIEW_REPORTS,
)
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ErrorSerializer
from apps.core.http import LOGO_TYPES
from apps.core.tenancy import require_current_school
from apps.finance import cash_outs
from apps.finance import expenses as services
from apps.finance.expense_serializers import (
    CashOutCreateSerializer,
    CashOutFilterSerializer,
    CashOutSerializer,
    ExpenseCancelSerializer,
    ExpenseCategorySerializer,
    ExpenseCategoryWriteSerializer,
    ExpenseCreateSerializer,
    ExpenseDecisionSerializer,
    ExpenseFilterSerializer,
    ExpenseSerializer,
    ExpenseSettingsSerializer,
    ExpenseSummarySerializer,
    PayableExpenseSerializer,
)
from apps.finance.models import CashOut, Expense, ExpenseCategory

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
INVALID = {400: ErrorSerializer}
CONFLICT = {409: ErrorSerializer}


@extend_schema_view(
    list=extend_schema(responses={200: ExpenseCategorySerializer(many=True), **ERRORS}),
    create=extend_schema(
        request=ExpenseCategoryWriteSerializer,
        responses={201: ExpenseCategorySerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
    partial_update=extend_schema(
        request=ExpenseCategoryWriteSerializer,
        responses={200: ExpenseCategorySerializer, **INVALID, **CONFLICT, **ERRORS},
    ),
)
class ExpenseCategoryViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, SchoolViewSet
):
    """Catégories de dépenses de l'école (FIN.1) : lues avec le droit de saisir ou de lire les
    rapports, réglées avec `finance.configure_fees`."""

    pagination_class = None
    serializer_class = ExpenseCategorySerializer

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        return EXPENSES_READ if self.action == "list" else FINANCE_CONFIGURE_FEES

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ExpenseCategory.all_schools.none()
        return ExpenseCategory.objects.all()

    def create(self, request: Request) -> Response:
        serializer = ExpenseCategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = services.create_category(
            actor=request.user, name=serializer.validated_data["name"]
        )
        return Response(ExpenseCategorySerializer(category).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk=None) -> Response:
        serializer = ExpenseCategoryWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = services.update_category(
            self.get_object(), actor=request.user, **serializer.validated_data
        )
        return Response(ExpenseCategorySerializer(category).data)


class ExpenseSettingsView(APIView):
    """Seuil de validation d'une dépense, par devise (FIN.1)."""

    permission_classes = [HasSchoolPermission]

    @property
    def required_permission(self):
        return EXPENSES_READ if self.request.method == "GET" else FINANCE_CONFIGURE_FEES

    def _body(self, values: dict) -> dict:
        return {
            "usd_threshold_minor": values["USD"],
            "cdf_threshold_minor": values["CDF"],
        }

    @extend_schema(responses={200: ExpenseSettingsSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        return Response(self._body(services.thresholds(require_current_school())))

    @extend_schema(
        request=ExpenseSettingsSerializer,
        responses={200: ExpenseSettingsSerializer, **INVALID, **ERRORS},
    )
    def put(self, request: Request) -> Response:
        serializer = ExpenseSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        values = services.update_thresholds(
            actor=request.user,
            values={"USD": data["usd_threshold_minor"], "CDF": data["cdf_threshold_minor"]},
        )
        return Response(self._body(values))


MONTH = OpenApiParameter("month", str, description="Mois « AAAA-MM » de la date de la dépense.")


@extend_schema_view(
    list=extend_schema(
        parameters=[ExpenseFilterSerializer, MONTH],
        responses={200: ExpenseSerializer(many=True), **INVALID, **ERRORS},
    ),
    retrieve=extend_schema(responses={200: ExpenseSerializer, **ERRORS}),
)
class ExpenseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Dépenses de l'école (FIN.1), les plus récentes d'abord. Saisir : `finance.record_expense` ;
    valider ou refuser : `finance.approve_expense`, jamais la sienne ; annuler :
    `finance.cancel_expense`. Création : 201, ou 200 si cette dépense (même `id`) était déjà
    enregistrée. Une dépense ne s'efface jamais."""

    serializer_class = ExpenseSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        return {
            "create": FINANCE_RECORD_EXPENSE,
            "approve": FINANCE_APPROVE_EXPENSE,
            "reject": FINANCE_APPROVE_EXPENSE,
            "cancel": FINANCE_CANCEL_EXPENSE,
        }.get(self.action, EXPENSES_READ)

    def _filtered(self):
        params = ExpenseFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        items = services.expenses()
        if "status" in data:
            items = items.filter(status=data["status"])
        if "category" in data:
            items = items.filter(category_id=data["category"])
        if "month" in data:
            year, month = data["month"].split("-")
            items = items.filter(spent_on__year=year, spent_on__month=month)
        return items

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Expense.all_schools.none()
        return self._filtered() if self.action in {"list", "summary"} else services.expenses()

    @extend_schema(
        parameters=[ExpenseFilterSerializer, MONTH],
        responses={200: ExpenseSummarySerializer, **INVALID, **ERRORS},
    )
    @action(detail=False, methods=["get"])
    def summary(self, request: Request) -> Response:
        """Totaux de la liste filtrée, par devise (jamais de somme entre devises)."""
        return Response(services.summary(self.get_queryset()))

    @extend_schema(
        request={"multipart/form-data": ExpenseCreateSerializer},
        responses={201: ExpenseSerializer, 200: ExpenseSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    def create(self, request: Request) -> Response:
        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        category = ExpenseCategory.objects.filter(pk=data["category"]).first()
        if category is None:
            raise Http404
        expense, created = services.record_expense(
            actor=request.user,
            category=category,
            beneficiary=data["beneficiary"],
            reason=data["reason"],
            amount_minor=data["amount_minor"],
            currency=data["currency"],
            spent_on=data["spent_on"],
            account=data["account"],
            voucher=data.get("voucher"),
            expense_id=data.get("id"),
        )
        return Response(
            ExpenseSerializer(services.expenses().get(pk=expense.pk)).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def _decide(self, request: Request, *, approve: bool) -> Response:
        params = ExpenseDecisionSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        expense = services.decide_expense(
            self.get_object(),
            actor=request.user,
            approve=approve,
            note=params.validated_data["note"],
        )
        return Response(ExpenseSerializer(services.expenses().get(pk=expense.pk)).data)

    @extend_schema(
        request=ExpenseDecisionSerializer,
        responses={200: ExpenseSerializer, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk=None) -> Response:
        """Valider une dépense en attente. 409 `expense_decided` ; 403 `own_expense` pour la
        sienne."""
        return self._decide(request, approve=True)

    @extend_schema(
        request=ExpenseDecisionSerializer,
        responses={200: ExpenseSerializer, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk=None) -> Response:
        """Refuser une dépense en attente (motif conseillé dans `note`)."""
        return self._decide(request, approve=False)

    @extend_schema(
        request=ExpenseCancelSerializer,
        responses={200: ExpenseSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        """Annuler : une ligne liée avec motif ; la dépense reste dans la liste. 409
        `expense_cancelled` si déjà annulée."""
        params = ExpenseCancelSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        expense = self.get_object()
        services.cancel_expense(expense, actor=request.user, reason=params.validated_data["reason"])
        return Response(ExpenseSerializer(services.expenses().get(pk=expense.pk)).data)

    @extend_schema(responses={(200, "application/octet-stream"): bytes, **ERRORS})
    @action(detail=True, methods=["get"])
    def voucher(self, request: Request, pk=None) -> FileResponse:
        """Le justificatif (photo ou PDF), lu seulement par le personnel de l'école."""
        expense = self.get_object()
        if not expense.voucher:
            raise Http404
        kind = expense.voucher.name.rsplit(".", 1)[-1]
        response = FileResponse(
            expense.voucher.open("rb"),
            content_type="application/pdf" if kind == "pdf" else LOGO_TYPES.get(kind, "image/jpeg"),
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
        response["Cache-Control"] = "private, max-age=3600"
        return response


@extend_schema_view(
    list=extend_schema(
        parameters=[CashOutFilterSerializer],
        responses={200: CashOutSerializer(many=True), **INVALID, **ERRORS},
    ),
    retrieve=extend_schema(responses={200: CashOutSerializer, **ERRORS}),
)
class CashOutViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Sorties de caisse (FIN.2), les plus récentes d'abord : une dépense validée payée en
    espèces depuis la session ouverte du caissier (`finance.collect_payment`). Le caissier voit
    les siennes, `finance.view_reports` toutes. Annuler : `finance.cancel_expense`, tant que la
    session est ouverte. Création : 201, ou 200 si cette sortie (même `id`) était déjà
    enregistrée. Une sortie ne s'efface jamais."""

    serializer_class = CashOutSerializer

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        return {
            "create": FINANCE_COLLECT_PAYMENT,
            "payable": FINANCE_COLLECT_PAYMENT,
            "cancel": FINANCE_CANCEL_EXPENSE,
        }.get(self.action, (FINANCE_COLLECT_PAYMENT, FINANCE_VIEW_REPORTS))

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CashOut.all_schools.none()
        items = cash_outs.cash_outs()
        if self.action == "cancel":
            return items
        if FINANCE_VIEW_REPORTS not in school_access(self.request).permissions:
            items = items.filter(cash_session__cashier=self.request.user)
        if self.action == "list":
            params = CashOutFilterSerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            if "cash_session" in params.validated_data:
                items = items.filter(cash_session_id=params.validated_data["cash_session"])
        return items

    @extend_schema(responses={200: PayableExpenseSerializer(many=True), **ERRORS})
    @action(detail=False, methods=["get"])
    def payable(self, request: Request) -> Response:
        """Dépenses validées à payer en espèces, pas encore sorties de la caisse, les plus
        anciennes d'abord."""
        page = self.paginate_queryset(cash_outs.payable_expenses())
        return self.get_paginated_response(PayableExpenseSerializer(page, many=True).data)

    @extend_schema(
        request=CashOutCreateSerializer,
        responses={201: CashOutSerializer, 200: CashOutSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    def create(self, request: Request) -> Response:
        """Sortir l'argent d'une dépense de la session ouverte du caissier. 409
        `no_open_session`, `expense_not_payable_in_cash` (pas validée, ou pas en espèces),
        `expense_already_paid`, `expense_cancelled`, `not_enough_cash` (la session n'a pas reçu
        assez dans cette devise)."""
        serializer = CashOutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        expense = Expense.objects.filter(pk=data["expense"]).first()
        if expense is None:
            raise Http404
        cash_out, created = cash_outs.record_cash_out(
            actor=request.user,
            expense=expense,
            received_by=data["received_by"],
            cash_out_id=data.get("id"),
        )
        return Response(
            CashOutSerializer(cash_out).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        request=ExpenseCancelSerializer,
        responses={200: CashOutSerializer, **INVALID, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        """Annuler une sortie : l'argent revient dans la caisse, la dépense redevient à payer.
        409 `cash_out_session_closed` après la clôture, `cash_out_cancelled` si déjà fait."""
        params = ExpenseCancelSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        cash_out = self.get_object()
        cash_outs.cancel_cash_out(
            cash_out, actor=request.user, reason=params.validated_data["reason"]
        )
        return Response(CashOutSerializer(cash_outs.cash_outs().get(pk=cash_out.pk)).data)
