"""Écoles dans la console de la plateforme (5.3) : liste, fiche, création avec le premier
directeur, identité et abonnement (super-admin seulement)."""

from copy import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.models import Membership, User
from apps.accounts.modules import MODULE_CHOICES
from apps.accounts.modules import resolve as resolve_modules
from apps.accounts.serializers import PhoneField
from apps.audit.models import PlatformAuditLog
from apps.billing import invoicing
from apps.billing.models import Contract, Invoice
from apps.core.money import Currency
from apps.core.serializers import PlatformChangeSerializer
from apps.schools.models import Demonstration, School, SchoolExport
from apps.sync.models import Device


class HeadAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "last_name", "middle_name", "first_name"]


class ConsoleSchoolSerializer(serializers.ModelSerializer):
    """Une école vue par le super-admin. Il change son adresse (`code` : l'ancienne cesse de
    marcher), ses noms et son abonnement ; couleur, fuseau, devises et logo sont réglés par
    l'école (M5). Suspendre, arrêter et réactiver passent par leurs actions ; le type d'espace
    (`environment`) est fixé à la création."""

    url = serializers.CharField(read_only=True, help_text="Adresse de l'école.")
    environment = serializers.ChoiceField(choices=School.Environment.choices, read_only=True)
    status = serializers.ChoiceField(
        choices=School.Status.choices,
        required=False,
        help_text="Essai gratuit ou active ; « suspendue » et « arrêtée » par leurs actions.",
    )
    modules = serializers.ListField(
        child=serializers.ChoiceField(choices=MODULE_CHOICES),
        required=False,
        help_text="Fonctions données à l'école (M.1) ; le socle est toujours actif. Retirer un "
        "module ne supprime aucune donnée.",
    )
    student_count = serializers.IntegerField(
        read_only=True, help_text="Inscriptions actives de l'année en cours."
    )
    last_activity_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="Dernière entrée de son journal, hors support et super-admin.",
    )

    class Meta:
        model = School
        fields = [
            "id",
            "code",
            "name",
            "official_name",
            "url",
            "environment",
            "status",
            "plan",
            "modules",
            "trial_ends_on",
            "paid_until",
            "timetable_max_seconds",
            "enabled_currencies",
            "default_currency",
            "student_count",
            "last_activity_at",
            "contact_name",
            "contact_phone",
            "contact_email",
            "internal_notes",
            "created_at",
        ]
        read_only_fields = ["enabled_currencies", "default_currency", "created_at"]

    def validate_status(self, status: str) -> str:
        if status in School.CLOSED_STATUSES:
            message = _("Use « Suspend » or « Stop » to close a school.")
            raise serializers.ValidationError(message, code="use_suspend")
        if self.instance is not None and self.instance.is_closed:
            message = _("Reactivate the school first.")
            raise serializers.ValidationError(message, code="school_suspended")
        return status

    def validate(self, data):
        # Règles du modèle (`School.clean`) : devise principale parmi celles de l'école.
        school = copy(self.instance) if self.instance is not None else School()
        for field, value in data.items():
            if field != "head":
                setattr(school, field, value)
        try:
            school.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None
        if "modules" in data:
            current = self.instance.modules if self.instance is not None else ()
            try:
                data["modules"] = resolve_modules(data["modules"], current)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"modules": str(exc)}, code="module_required"
                ) from None
        if "enabled_currencies" in data:
            data["enabled_currencies"] = school.enabled_currencies
        return data


class DemonstrationSerializer(serializers.ModelSerializer):
    """Espace de démonstration créé depuis la console (4.17.2) : où en est son remplissage."""

    STATES = [*Demonstration.State.values, "resetting"]

    state = serializers.SerializerMethodField(
        help_text="`resetting` : remise à zéro demandée, l'espace s'efface puis se remplit."
    )

    class Meta:
        model = Demonstration
        fields = ["profile", "state", "steps_done", "steps_total"]

    @extend_schema_field(serializers.ChoiceField(choices=STATES))
    def get_state(self, demonstration: Demonstration) -> str:
        return "resetting" if demonstration.reset_requested else demonstration.state


class SchoolContractSerializer(serializers.Serializer):
    number = serializers.CharField()
    plan = serializers.CharField(source="plan.name")
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    price_per_student = serializers.IntegerField()
    currency = serializers.CharField()
    auto_renew = serializers.BooleanField()


class SchoolInvoiceSerializer(serializers.Serializer):
    number = serializers.CharField()
    kind = serializers.CharField()
    issued_on = serializers.DateField()
    due_on = serializers.DateField()
    currency = serializers.CharField()
    total = serializers.IntegerField()
    balance = serializers.IntegerField(help_text="Reste dû, 0 pour un avoir ou une facture soldée.")


class SchoolUsageSerializer(serializers.Serializer):
    students = serializers.IntegerField()
    accounts = serializers.IntegerField(help_text="Comptes ayant accès à l'école.")
    last_activity_at = serializers.DateTimeField(allow_null=True)
    last_sync_at = serializers.DateTimeField(allow_null=True)


class SchoolExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolExport
        fields = ["id", "state", "created_at", "expires_at"]


class ConsoleSchoolDetailSerializer(ConsoleSchoolSerializer):
    HISTORY = 10

    history = serializers.SerializerMethodField(
        help_text="Les derniers changements faits dans la console, du plus récent au plus ancien."
    )
    demonstration = DemonstrationSerializer(
        read_only=True,
        allow_null=True,
        help_text="Vide : pas un espace de démonstration créé depuis la console.",
    )

    contract = serializers.SerializerMethodField(
        help_text="Contrat en cours, vide sans contrat (espaces d'essai compris)."
    )
    invoices = serializers.SerializerMethodField(help_text="Les 5 dernières factures et avoirs.")
    usage = serializers.SerializerMethodField()
    exports = serializers.SerializerMethodField(help_text="Les 3 derniers exports complets.")

    class Meta(ConsoleSchoolSerializer.Meta):
        fields = [
            *ConsoleSchoolSerializer.Meta.fields,
            "history",
            "demonstration",
            "contract",
            "invoices",
            "usage",
            "exports",
        ]

    @extend_schema_field(SchoolExportSerializer(many=True))
    def get_exports(self, school: School) -> list[dict]:
        return SchoolExportSerializer(school.exports.all()[:3], many=True).data

    @extend_schema_field(SchoolContractSerializer(allow_null=True))
    def get_contract(self, school: School):
        contract = (
            Contract.all_schools.filter(school=school, status=Contract.Status.ACTIVE)
            .select_related("plan")
            .first()
        )
        return SchoolContractSerializer(contract).data if contract else None

    @extend_schema_field(SchoolInvoiceSerializer(many=True))
    def get_invoices(self, school: School) -> list[dict]:
        rows = invoicing.with_balance(
            Invoice.all_schools.filter(school=school).order_by("-issued_on", "-number")
        )[:5]
        for invoice in rows:
            invoice.balance = invoicing.balance(invoice)
        return SchoolInvoiceSerializer(rows, many=True).data

    @extend_schema_field(SchoolUsageSerializer)
    def get_usage(self, school: School) -> dict:
        seen = (
            Device.all_schools.filter(school=school, revoked_at__isnull=True)
            .order_by("-last_seen_at")
            .values_list("last_seen_at", flat=True)
            .first()
        )
        return SchoolUsageSerializer(
            {
                "students": school.student_count,
                "accounts": Membership.objects.filter(school=school, is_active=True).count(),
                "last_activity_at": school.last_activity_at,
                "last_sync_at": seen,
            }
        ).data

    @extend_schema_field(PlatformChangeSerializer(many=True))
    def get_history(self, school: School) -> list[dict]:
        changes = PlatformAuditLog.objects.filter(
            entity_type=school._meta.label_lower, entity_id=str(school.pk)
        ).select_related("actor")[: self.HISTORY]
        return PlatformChangeSerializer(changes, many=True).data


class SchoolHeadSerializer(serializers.Serializer):
    """Premier directeur. Nouveau numéro : nom obligatoire ; numéro connu : noms ignorés (B3)."""

    phone = PhoneField(help_text="Ex. 0971234567 ou +243971234567.")
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, data):
        known = User.objects.filter(phone=data["phone"]).exists()
        if not known and not data.get("last_name", "").strip():
            message = _("This phone number has no account yet: enter the name.")
            raise serializers.ValidationError({"last_name": message}, code="name_required")
        return data


class ConsoleSchoolCreateSerializer(ConsoleSchoolSerializer):
    enabled_currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=Currency.choices),
        allow_empty=False,
        help_text="Devises de l'école (au moins une).",
    )
    default_currency = serializers.ChoiceField(choices=Currency.choices)
    environment = serializers.ChoiceField(
        choices=[School.Environment.LIVE, School.Environment.TEST],
        default=School.Environment.LIVE,
        help_text="Réel ou essai, jamais changé ensuite. Démonstration : `schools/demo/`.",
    )
    head = SchoolHeadSerializer(write_only=True)
    prospect = serializers.UUIDField(
        write_only=True,
        required=False,
        help_text="Prospect (demande de démonstration) d'où vient l'essai : il passe à « essai » "
        "et garde le lien vers l'école.",
    )

    class Meta(ConsoleSchoolSerializer.Meta):
        fields = [*ConsoleSchoolSerializer.Meta.fields, "head", "prospect"]
        read_only_fields = ["created_at"]


class DemonstrationCreateSerializer(serializers.ModelSerializer):
    """Nouvel espace de démonstration : son adresse, son nom et la taille de l'école fictive."""

    profile = serializers.ChoiceField(
        choices=Demonstration.Profile.choices,
        help_text="Petite école (≈ 150 élèves) ou grande école (≈ 800).",
    )

    class Meta:
        model = School
        fields = ["code", "name", "profile"]


class AccessSheetQuerySerializer(serializers.Serializer):
    output = serializers.ChoiceField(choices=["pdf", "html"], help_text="PDF, ou son aperçu HTML.")


class SchoolStopSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=200, help_text="Motif, gardé dans le journal de la plateforme."
    )
    confirm = serializers.CharField(
        max_length=63, help_text="Code de l'espace, retapé pour confirmer."
    )


class SchoolDeleteSerializer(serializers.Serializer):
    confirm = serializers.CharField(
        max_length=63, help_text="Code de l'espace, retapé pour confirmer."
    )


class ConsoleSchoolCreatedSerializer(serializers.Serializer):
    school = ConsoleSchoolSerializer()
    head = HeadAccountSerializer()
    temporary_password = serializers.CharField(
        allow_null=True,
        help_text="Nouveau compte seulement : affiché une seule fois, à transmettre au directeur.",
    )
