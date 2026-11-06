from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Membership
from apps.core.money import Currency
from apps.inventory import catalogue
from apps.inventory.models import Copy, Item, Loan, LossReport
from apps.schools.models import Level
from apps.students.models import Student

IMPORT_ISSUES = [
    ("missing_title", "Title missing"),
    ("too_long", "Title or author too long"),
    ("unknown_level", "Level unknown in this school"),
    ("invalid_copies", "Number of copies unreadable (1 to 200)"),
    ("invalid_price", "Price unreadable"),
    ("duplicate_title", "Same title and author as another line"),
    ("already_in_catalogue", "Already in the catalogue: left as is"),
]
LOAN_STATES = [("open", "Open"), ("overdue", "Overdue"), ("returned", "Returned")]


def _borrower(loan: Loan) -> dict:
    if loan.student_id:
        student = loan.student
        return {
            "kind": "student",
            "id": student.pk,
            "name": str(student),
            "number": student.matricule,
        }
    member = loan.member
    return {"kind": "staff", "id": member.pk, "name": str(member.user), "number": ""}


class BorrowerSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=[("student", "Student"), ("staff", "Staff member")])
    id = serializers.UUIDField(help_text="Élève, ou appartenance du membre du personnel.")
    name = serializers.CharField()
    number = serializers.CharField(help_text="Matricule de l'élève ; vide pour le personnel.")


class LevelRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class BookSerializer(serializers.ModelSerializer):
    """Titre du catalogue, avec ses exemplaires en service, disponibles et prêtés."""

    level = LevelRefSerializer(read_only=True, allow_null=True)
    copies_total = serializers.IntegerField(read_only=True)
    copies_available = serializers.IntegerField(read_only=True)
    copies_lent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Item
        fields = [
            "id",
            "name",
            "author",
            "isbn",
            "category",
            "level",
            "price_minor",
            "currency",
            "reference_only",
            "is_active",
            "copies_total",
            "copies_available",
            "copies_lent",
        ]


class BookWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    author = serializers.CharField(max_length=120, required=False, allow_blank=True)
    isbn = serializers.CharField(max_length=20, required=False, allow_blank=True)
    category = serializers.CharField(max_length=60, required=False, allow_blank=True)
    level = serializers.PrimaryKeyRelatedField(
        queryset=Level.objects, required=False, allow_null=True
    )
    price_minor = serializers.IntegerField(
        min_value=0, required=False, allow_null=True, help_text="Prix de remplacement, en entiers."
    )
    currency = serializers.ChoiceField(choices=Currency.choices, required=False, allow_blank=True)
    reference_only = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    copies = serializers.IntegerField(
        min_value=0,
        max_value=catalogue.MAX_COPIES,
        required=False,
        help_text="Création seulement : exemplaires à créer.",
    )


class CopyLoanSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    borrower = BorrowerSerializer()
    due_on = serializers.DateField()


class CopySerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, help_text="Code de l'étiquette : LIV-000414.")
    loan = serializers.SerializerMethodField()

    class Meta:
        model = Copy
        fields = ["id", "number", "code", "state", "loan"]

    @staticmethod
    @extend_schema_field(CopyLoanSerializer(allow_null=True))
    def get_loan(copy: Copy) -> dict | None:
        loan = getattr(copy, "open_loan", None)
        if loan is None:
            return None
        return {"id": loan.pk, "borrower": _borrower(loan), "due_on": loan.due_on}


class BookDetailSerializer(BookSerializer):
    copies = CopySerializer(many=True, read_only=True, source="copy_list")

    class Meta(BookSerializer.Meta):
        fields = [*BookSerializer.Meta.fields, "copies"]


class CopiesAddSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=catalogue.MAX_COPIES)


class CatalogueQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    level = serializers.UUIDField(required=False)


class CatalogueImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Excel (.xlsx) ou CSV, 3 000 titres au plus.")
    currency = serializers.ChoiceField(choices=Currency.choices, help_text="Devise des prix.")
    expected = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Nombre de lignes prêtes de l'aperçu : présent, les titres sont créés.",
    )


class CatalogueImportIssueSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=IMPORT_ISSUES)
    line = serializers.IntegerField(required=False, help_text="`duplicate_title` : autre ligne.")
    level = serializers.CharField(required=False, help_text="`unknown_level` : niveau écrit.")


class CatalogueImportLineSerializer(serializers.Serializer):
    line = serializers.IntegerField(source="number")
    name = serializers.CharField()
    author = serializers.CharField()
    copies = serializers.IntegerField()
    price_minor = serializers.IntegerField(allow_null=True)
    status = serializers.ChoiceField(
        choices=[("ready", "Ready"), ("skipped", "Skipped"), ("error", "Error")]
    )
    issues = CatalogueImportIssueSerializer(many=True)


class CatalogueImportSerializer(serializers.Serializer):
    recorded = serializers.BooleanField()
    ready_count = serializers.IntegerField()
    skipped_count = serializers.IntegerField()
    error_count = serializers.IntegerField()
    lines = CatalogueImportLineSerializer(many=True)


class LendingRulesSerializer(serializers.Serializer):
    """Règles de prêt de l'école (`inventory/rules.py`)."""

    student_days = serializers.IntegerField(min_value=1, max_value=365)
    student_max = serializers.IntegerField(min_value=1, max_value=50)
    student_extensions = serializers.IntegerField(min_value=0, max_value=10)
    staff_days = serializers.IntegerField(min_value=1, max_value=365)
    staff_max = serializers.IntegerField(min_value=1, max_value=50)
    staff_extensions = serializers.IntegerField(min_value=0, max_value=10)
    tool_days = serializers.IntegerField(
        min_value=0, max_value=30, help_text="Outil : 0 = rendu le jour même."
    )
    block_if_overdue = serializers.BooleanField()
    notify_parent = serializers.BooleanField()
    remind_days_before = serializers.IntegerField(min_value=0, max_value=14)
    remind_every_days = serializers.IntegerField(min_value=1, max_value=30)
    late_fee_minor = serializers.IntegerField(
        min_value=0, help_text="Pénalité par jour de retard, en entiers ; 0 = aucune."
    )
    late_fee_currency = serializers.ChoiceField(choices=Currency.choices)


class LoanSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="copy.code")
    item = serializers.CharField(source="copy.item.name")
    item_kind = serializers.CharField(source="copy.item.kind")
    borrower = serializers.SerializerMethodField()
    overdue_days = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            "id",
            "number",
            "code",
            "item",
            "item_kind",
            "borrower",
            "lent_at",
            "due_on",
            "extensions",
            "returned_at",
            "return_condition",
            "reminders",
            "overdue_days",
        ]

    @staticmethod
    @extend_schema_field(BorrowerSerializer)
    def get_borrower(loan: Loan) -> dict:
        return _borrower(loan)

    @staticmethod
    def get_overdue_days(loan: Loan) -> int:
        end = timezone.localdate(loan.returned_at) if loan.returned_at else timezone.localdate()
        return max((end - loan.due_on).days, 0)


class LoanQuerySerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=LOAN_STATES, default="open")
    search = serializers.CharField(required=False, allow_blank=True)


class ReportWriteSerializer(serializers.Serializer):
    copy = serializers.PrimaryKeyRelatedField(queryset=Copy.objects)
    kind = serializers.ChoiceField(
        choices=[(LossReport.Kind.LOST, "Lost"), (LossReport.Kind.DAMAGED, "Damaged")]
    )
    note = serializers.CharField(max_length=200)
    amount_minor = serializers.IntegerField(
        min_value=0, required=False, help_text="Frais de remplacement ; absent : prix du titre."
    )
    currency = serializers.ChoiceField(choices=Currency.choices, required=False)


class ReportSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="copy.code")
    item = serializers.CharField(source="copy.item.name")
    borrower = serializers.SerializerMethodField()
    corrected = serializers.SerializerMethodField()

    class Meta:
        model = LossReport
        fields = [
            "id",
            "code",
            "item",
            "kind",
            "note",
            "amount_minor",
            "currency",
            "borrower",
            "corrects",
            "corrected",
            "created_at",
        ]

    @staticmethod
    @extend_schema_field(BorrowerSerializer(allow_null=True))
    def get_borrower(report: LossReport) -> dict | None:
        return _borrower(report.loan) if report.loan_id else None

    @staticmethod
    def get_corrected(report: LossReport) -> bool:
        return hasattr(report, "corrected_by")


class ReportCorrectionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=200, help_text="Pourquoi le constat était une erreur.")


# Liste de l'appareil du guichet


class DeskQuerySerializer(serializers.Serializer):
    after = serializers.IntegerField(required=False, help_text="Dernier numéro de la page reçue.")
    version = serializers.CharField(required=False, help_text="Version de la liste de l'appareil.")


class DeskCopySerializer(serializers.ModelSerializer):
    code = serializers.CharField()
    item = serializers.CharField(source="item.name")
    author = serializers.CharField(source="item.author")
    kind = serializers.CharField(source="item.kind")
    reference_only = serializers.BooleanField(source="item.reference_only")
    loan = serializers.SerializerMethodField()

    class Meta:
        model = Copy
        fields = ["id", "number", "code", "item", "author", "kind", "reference_only", "loan"]

    get_loan = staticmethod(CopySerializer.get_loan)


class DeskSerializer(serializers.Serializer):
    version = serializers.CharField()
    unchanged = serializers.BooleanField(help_text="Vrai : la liste de l'appareil est à jour.")
    copies = DeskCopySerializer(many=True)
    next = serializers.IntegerField(allow_null=True, help_text="`after` de la page suivante.")
    rules = LendingRulesSerializer()


# Opérations hors ligne (`sync/operations.py`)


class _StaffField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Membership.objects.filter(is_active=True).select_related("user")


class OfflineLoanSerializer(serializers.Serializer):
    """Prêt fait au guichet : l'exemplaire (étiquette lue) et l'élève ou le membre du personnel."""

    id = serializers.UUIDField(help_text="UUID v7 du prêt, donné par l'appareil.")
    copy = serializers.PrimaryKeyRelatedField(queryset=Copy.objects)
    lent_at = serializers.DateTimeField(help_text="Heure de l'appareil au prêt.")
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects, required=False)
    member = _StaffField(required=False)

    def validate(self, data):
        if ("student" in data) == ("member" in data):
            raise serializers.ValidationError(_("Give the student or the staff member."))
        return data

    def to_service(self) -> dict:
        return {**self.validated_data, "permissions": self.context["permissions"]}


class OfflineReturnSerializer(serializers.Serializer):
    """Retour au guichet : l'exemplaire et son état."""

    copy = serializers.PrimaryKeyRelatedField(queryset=Copy.objects)
    returned_at = serializers.DateTimeField(help_text="Heure de l'appareil au retour.")
    condition = serializers.ChoiceField(
        choices=[
            (Loan.Condition.GOOD, "Good"),
            (Loan.Condition.WORN, "Worn"),
            (Loan.Condition.DAMAGED, "Damaged"),
        ],
        default=Loan.Condition.GOOD,
    )

    def to_service(self) -> dict:
        return {**self.validated_data, "permissions": self.context["permissions"]}
