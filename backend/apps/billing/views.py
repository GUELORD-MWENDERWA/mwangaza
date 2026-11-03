from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import platform_roles as team
from apps.accounts.permissions import HasPlatformPermission, HasSchoolPermission
from apps.billing import documents, invoicing, services
from apps.billing.models import Contract, Invoice, InvoiceLine, InvoicePayment, LegalDocument, Plan
from apps.billing.serializers import (
    ContractCreateSerializer,
    ContractSerializer,
    ContractSignSerializer,
    InvoiceCreateSerializer,
    InvoicePaymentCreateSerializer,
    InvoicePaymentSerializer,
    InvoiceReasonSerializer,
    InvoiceSerializer,
    LegalAcceptSerializer,
    LegalDocumentSerializer,
    PlanSerializer,
)
from apps.core.http import client_ip
from apps.schools.models import School

READ = (team.BILLING_MANAGE, team.SCHOOLS_VIEW)
FINANCE = (team.BILLING_MANAGE,)  # factures et paiements : l'équipe finance seulement


class ConsolePlanViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Offres de la plateforme (ABO.1) : prix par élève inscrit et par période, modules compris."""

    permission_classes = [HasPlatformPermission]
    platform_permission = {
        "list": READ,
        "retrieve": READ,
        "create": team.BILLING_MANAGE,
        "update": team.BILLING_MANAGE,
        "partial_update": team.BILLING_MANAGE,
    }
    serializer_class = PlanSerializer
    queryset = Plan.objects.all()
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.instance = services.save_plan(
            actor=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer):
        serializer.instance = services.save_plan(
            actor=self.request.user, plan=serializer.instance, **serializer.validated_data
        )


class ConsoleContractViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Contrats des écoles (CTR.1) : brouillon, signature (scan ou en ligne), avenant."""

    permission_classes = [HasPlatformPermission]
    platform_permission = {
        "list": READ,
        "retrieve": READ,
        "create": team.BILLING_MANAGE,
        "sign": team.BILLING_MANAGE,
        "amend": team.BILLING_MANAGE,
        "pdf": READ,
    }
    serializer_class = ContractSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        contracts = Contract.all_schools.select_related("school", "plan", "replaces")
        if code := self.request.query_params.get("school"):
            contracts = contracts.filter(school__code=code)
        return contracts

    @extend_schema(request=ContractCreateSerializer, responses={201: ContractSerializer})
    def create(self, request, *args, **kwargs):
        form = ContractCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = dict(form.validated_data)
        school = get_object_or_404(School, code=data.pop("school"))
        plan = get_object_or_404(Plan, code=data.pop("plan"))
        contract = services.draft_contract(actor=request.user, school=school, plan=plan, **data)
        return Response(ContractSerializer(contract).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ContractSignSerializer, responses={200: ContractSerializer})
    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        form = ContractSignSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        contract = services.activate_contract(
            self.get_object(),
            actor=request.user,
            signature=form.validated_data["signature"],
            signer_name=form.validated_data.get("signer_name", ""),
            signed_file=form.validated_data.get("signed_file"),
        )
        return Response(ContractSerializer(contract).data)

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Le contrat en PDF (numéroté ; un avenant porte le numéro du contrat qu'il remplace)."""
        return documents.contract_pdf(self.get_object())

    @extend_schema(request=ContractCreateSerializer, responses={201: ContractSerializer})
    @action(detail=True, methods=["post"])
    def amend(self, request, pk=None):
        """Avenant : nouveau brouillon lié au contrat actif."""
        form = serializers_partial(request.data)
        draft = services.amend_contract(self.get_object(), actor=request.user, **form)
        return Response(ContractSerializer(draft).data, status=status.HTTP_201_CREATED)


def serializers_partial(data) -> dict:
    """Champs d'un avenant : seulement ceux que la console change (prix, dates, offre)."""
    form = ContractCreateSerializer(data=data, partial=True)
    form.is_valid(raise_exception=True)
    values = dict(form.validated_data)
    values.pop("school", None)
    if code := values.pop("plan", None):
        values["plan"] = get_object_or_404(Plan, code=code)
    return values


class ConsoleInvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Factures des écoles (ABO.2) : émettre, annuler par un avoir, encaisser (à la main),
    annuler un paiement, PDF. Une facture ne se modifie ni ne se supprime."""

    permission_classes = [HasPlatformPermission]
    platform_permission = {
        "list": FINANCE,
        "retrieve": FINANCE,
        "pdf": FINANCE,
        "create": team.BILLING_MANAGE,
        "cancel": team.BILLING_MANAGE,
        "pay": team.BILLING_MANAGE,
        "reverse_payment": team.BILLING_MANAGE,
    }
    serializer_class = InvoiceSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        invoices = invoicing.with_balance(
            Invoice.all_schools.select_related("school", "contract", "credit_for", "credit_note")
            .prefetch_related(
                Prefetch("lines", queryset=InvoiceLine.all_schools.all()),
                Prefetch("payments", queryset=InvoicePayment.all_schools.all()),
            )
            .order_by("-issued_on", "-number")
        )
        if code := self.request.query_params.get("school"):
            invoices = invoices.filter(school__code=code)
        return invoices

    @extend_schema(request=InvoiceCreateSerializer, responses={201: InvoiceSerializer})
    def create(self, request, *args, **kwargs):
        form = InvoiceCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = dict(form.validated_data)
        contract = get_object_or_404(Contract.all_schools, number=data.pop("contract"))
        extra = [(x["description"], x["quantity"], x["unit_amount"]) for x in data.pop("lines", [])]
        invoice = invoicing.issue_invoice(contract, actor=request.user, extra_lines=extra, **data)
        return Response(self._one(invoice), status=status.HTTP_201_CREATED)

    def _one(self, invoice):
        return InvoiceSerializer(self.get_queryset().get(pk=invoice.pk)).data

    @extend_schema(request=InvoiceReasonSerializer, responses={201: InvoiceSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Avoir complet : la facture reste, son reste dû tombe à 0."""
        form = InvoiceReasonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        note = invoicing.cancel_invoice(
            self.get_object(), actor=request.user, reason=form.validated_data["reason"]
        )
        return Response(self._one(note), status=status.HTTP_201_CREATED)

    @extend_schema(
        request=InvoicePaymentCreateSerializer, responses={201: InvoicePaymentSerializer}
    )
    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        form = InvoicePaymentCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        payment = invoicing.record_payment(
            self.get_object(), actor=request.user, **form.validated_data
        )
        return Response(InvoicePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=InvoiceReasonSerializer,
        responses={201: InvoicePaymentSerializer},
        parameters=[OpenApiParameter("payment", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    )
    @action(detail=True, methods=["post"], url_path=r"payments/(?P<payment>[^/.]+)/reverse")
    def reverse_payment(self, request, pk=None, payment=None):
        """Annule un paiement par une écriture liée, avec motif."""
        form = InvoiceReasonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        original = get_object_or_404(
            InvoicePayment.all_schools, pk=payment, invoice=self.get_object()
        )
        reversal = invoicing.reverse_payment(
            original, actor=request.user, reason=form.validated_data["reason"]
        )
        return Response(InvoicePaymentSerializer(reversal).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        return documents.invoice_pdf(self.get_object())


class ConsoleStatementView(APIView):
    """Relevé d'une école (ABO.2) : factures, avoirs et paiements par devise, solde courant."""

    permission_classes = [HasPlatformPermission]
    platform_permission = {"get": FINANCE}

    @extend_schema(responses={200: dict})
    def get(self, request, code):
        school = get_object_or_404(School, code=code)
        return Response(invoicing.statement(school))


class ConsoleLegalViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Versions des conditions, de la politique de confidentialité et du registre (CTR.1) :
    publier une version ; une version publiée ne change plus."""

    permission_classes = [HasPlatformPermission]
    platform_permission = {"list": READ, "create": team.BILLING_MANAGE}
    serializer_class = LegalDocumentSerializer
    queryset = LegalDocument.objects.all()
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        serializer.instance = services.publish_legal(
            actor=self.request.user, **serializer.validated_data
        )


class LegalCurrentView(APIView):
    """Textes en vigueur, publics (site et applications) : dernière version de chacun."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(responses={200: LegalDocumentSerializer(many=True)})
    def get(self, request):
        return Response(LegalDocumentSerializer(services.current_documents(), many=True).data)


class LegalPendingView(APIView):
    """Versions que l'école n'a pas encore acceptées, pour son administrateur principal."""

    permission_classes = [HasSchoolPermission]
    required_permission = "roles.manage"

    @extend_schema(responses={200: LegalDocumentSerializer(many=True)})
    def get(self, request):
        return Response(
            LegalDocumentSerializer(services.pending_for(request.school), many=True).data
        )


class LegalAcceptView(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = "roles.manage"

    @extend_schema(request=LegalAcceptSerializer, responses={204: None})
    def post(self, request):
        form = LegalAcceptSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        document = get_object_or_404(LegalDocument, pk=form.validated_data["document"])
        services.accept(
            school=request.school, user=request.user, document=document, ip=client_ip(request)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
