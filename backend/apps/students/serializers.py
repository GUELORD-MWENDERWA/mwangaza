from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PhoneField
from apps.audit.serializers import AuditLogSerializer
from apps.finance import services as finance
from apps.finance.serializers import BalanceSerializer
from apps.schools.models import AcademicYear, ClassGroup, Track
from apps.students import documents, imports
from apps.students.models import (
    ContactChange,
    Enrollment,
    Family,
    Guardian,
    Student,
    StudentImport,
)
from apps.students.photos import photo_version, validate_photo


class AddressSerializer(serializers.Serializer):
    commune = serializers.CharField(max_length=80, required=False, allow_blank=True)
    quartier = serializers.CharField(max_length=80, required=False, allow_blank=True)
    avenue = serializers.CharField(max_length=120, required=False, allow_blank=True)
    number = serializers.CharField(max_length=20, required=False, allow_blank=True)


class GuardianSerializer(serializers.ModelSerializer):
    # Présent : ce tuteur est modifié ; absent : un nouveau tuteur.
    id = serializers.UUIDField(required=False)
    phone = PhoneField(required=False, allow_blank=True, help_text="Ex. 0971234567.")

    class Meta:
        model = Guardian
        fields = [
            "id",
            "full_name",
            "relationship",
            "phone",
            "email",
            "is_primary",
            "is_emergency_contact",
        ]


class FamilySerializer(serializers.ModelSerializer):
    guardians = GuardianSerializer(many=True, read_only=True)
    student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Family
        fields = [
            "id",
            "code",
            "guardians",
            "student_count",
            "activated_at",
            "code_expires_at",
            "portal_suspended_at",
        ]


class FamilyStudentSerializer(serializers.ModelSerializer):
    # Classe de l'année en cours, ou vide.
    class_group_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "matricule", "last_name", "middle_name", "first_name", "class_group_name"]

    def get_class_group_name(self, student: Student) -> str:
        enrollments = getattr(student, "year_enrollments", [])
        return enrollments[0].class_group.name if enrollments else ""


class FamilyDetailSerializer(FamilySerializer):
    """Famille avec ses enfants : pour la reconnaître en inscrivant un élève (D4)."""

    students = FamilyStudentSerializer(many=True, read_only=True)

    class Meta(FamilySerializer.Meta):
        fields = [*FamilySerializer.Meta.fields, "students"]


class FamilyWriteSerializer(serializers.Serializer):
    guardians = GuardianSerializer(many=True)


class PortalAccessSerializer(serializers.Serializer):
    suspended = serializers.BooleanField(help_text="`true` : suspendre ; `false` : rétablir.")


class FamilyFilterSerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False, max_length=100, help_text="Code famille, nom ou téléphone d'un tuteur."
    )


class EnrollmentSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    class_group_name = serializers.CharField(source="class_group.name", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "academic_year",
            "academic_year_name",
            "class_group",
            "class_group_name",
            "status",
            "enrolled_on",
            "left_on",
        ]


class EnrollmentCreateSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, help_text="UUID v7 donné par l'appareil.")
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects)
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects)
    enrolled_on = serializers.DateField(required=False)


class EnrollmentUpdateSerializer(serializers.Serializer):
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects, required=False)
    status = serializers.ChoiceField(choices=Enrollment.Status.choices, required=False)
    left_on = serializers.DateField(required=False)


class _StudentFields(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "id",
            "matricule",
            "last_name",
            "middle_name",
            "first_name",
            "sex",
            "birth_date",
        ]


class StudentListSerializer(_StudentFields):
    family_code = serializers.CharField(source="family.code", read_only=True)
    # Inscription de l'année demandée (par défaut l'année en cours), ou `null`.
    enrollment = serializers.SerializerMethodField()
    # Contact principal de la famille (le premier à défaut), ou `null`.
    primary_guardian = serializers.SerializerMethodField()
    finance = serializers.SerializerMethodField()

    class Meta(_StudentFields.Meta):
        fields = [
            *_StudentFields.Meta.fields,
            "family",
            "family_code",
            "enrollment",
            "primary_guardian",
            "finance",
        ]

    @extend_schema_field(EnrollmentSerializer(allow_null=True))
    def get_enrollment(self, student: Student) -> dict | None:
        enrollments = getattr(student, "year_enrollments", [])
        return EnrollmentSerializer(enrollments[0]).data if enrollments else None

    @extend_schema_field(GuardianSerializer(allow_null=True))
    def get_primary_guardian(self, student: Student) -> dict | None:
        guardians = student.family.guardians.all()
        return GuardianSerializer(guardians[0]).data if guardians else None

    @extend_schema_field(BalanceSerializer(allow_null=True))
    def get_finance(self, student: Student) -> dict | None:
        """Solde de l'inscription affichée (« Échu non payé » par devise, situation des
        paiements), avec un droit de lecture des frais ; sinon, ou sans inscription, `null`."""
        balances = self.context.get("balances")
        enrollments = getattr(student, "year_enrollments", [])
        if balances is None or not enrollments:
            return None
        return BalanceSerializer(balances.get(enrollments[0].pk) or finance.balance([])).data


def photo_url(student: Student) -> str | None:
    """Adresse de la photo (servie par l'API) ; elle change avec chaque photo (cache)."""
    if not student.photo:
        return None
    return f"/api/students/{student.pk}/photo/?v={photo_version(student)}"


class StudentSerializer(_StudentFields):
    address = AddressSerializer(read_only=True)
    family = FamilySerializer(read_only=True)
    enrollments = EnrollmentSerializer(many=True, read_only=True)
    photo = serializers.SerializerMethodField(
        help_text="Adresse de la photo (`GET /api/students/{id}/photo/`) ; null sans photo."
    )

    class Meta(_StudentFields.Meta):
        fields = [
            *_StudentFields.Meta.fields,
            "birth_place",
            "nationality",
            "origin_province",
            "origin_territory",
            "address",
            "photo",
            "photo_consent",
            "previous_school",
            "family",
            "enrollments",
            "created_at",
        ]

    def get_photo(self, student: Student) -> str | None:
        return photo_url(student)


class PhotoUploadSerializer(serializers.Serializer):
    photo = serializers.FileField(
        validators=[validate_photo], help_text="PNG ou JPEG, 1 Mo au plus."
    )


class StudentHistorySerializer(AuditLogSerializer):
    """Une entrée du journal sur l'élève, ses inscriptions ou sa famille (onglet Historique) ;
    sans adresse IP ni navigateur, réservés au journal de l'école (`audit.view`)."""

    class Meta(AuditLogSerializer.Meta):
        fields = [
            name for name in AuditLogSerializer.Meta.fields if name not in {"ip", "user_agent"}
        ]
        read_only_fields = fields


class StudentWriteSerializer(serializers.ModelSerializer):
    """Création : `family` (famille existante de l'école) ou `guardians` (nouvelle famille).
    Modification : les mêmes champs, tous facultatifs ; `family` relie l'élève à une autre
    famille (D4)."""

    id = serializers.UUIDField(required=False, help_text="UUID v7 donné par l'appareil.")
    address = AddressSerializer(required=False)
    family = serializers.PrimaryKeyRelatedField(queryset=Family.objects, required=False)
    guardians = GuardianSerializer(many=True, required=False, write_only=True)
    allow_duplicate = serializers.BooleanField(
        required=False,
        default=False,
        write_only=True,
        help_text="Créer même si un élève a les mêmes noms et la même date de naissance.",
    )

    class Meta:
        model = Student
        fields = [
            "id",
            "matricule",
            "last_name",
            "middle_name",
            "first_name",
            "sex",
            "birth_date",
            "birth_place",
            "nationality",
            "origin_province",
            "origin_territory",
            "address",
            "photo_consent",
            "previous_school",
            "family",
            "guardians",
            "allow_duplicate",
        ]
        # Le matricule est donné à l'inscription ; seulement corrigé à la main ensuite.
        extra_kwargs = {"matricule": {"required": False}}

    def validate(self, attrs):
        if attrs.get("family") and attrs.get("guardians"):
            raise serializers.ValidationError(
                {"guardians": _("Either an existing family or new guardians, not both.")},
                code="family_and_guardians",
            )
        return attrs


class StudentFilterSerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False, max_length=100, help_text="Noms, matricule ou code famille."
    )
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects,
        required=False,
        help_text="Année de l'inscription affichée (par défaut l'année en cours).",
    )
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects, required=False)
    track = serializers.PrimaryKeyRelatedField(
        queryset=Track.objects, required=False, help_text="Option de la classe de l'année."
    )
    payment = serializers.ChoiceField(
        choices=[finance.UP_TO_DATE, finance.PARTIAL, finance.OVERDUE],
        required=False,
        help_text="Situation des paiements de l'année (droit de lecture des frais) : à jour, "
        "partielle (en retard, mais des paiements) ou en retard (rien payé).",
    )
    status = serializers.ChoiceField(
        choices=["active", "left", "not_enrolled"],
        required=False,
        help_text="Cette année : inscrit et présent, inscrit puis parti (transfert, abandon, "
        "exclusion, fin d'études) ou pas inscrit. Absent : tous.",
    )


# Import d'une liste d'élèves (D1)


class ImportMappingSerializer(serializers.Serializer):
    """Champ de l'élève → numéro de la colonne du fichier (à partir de 0), ou `null`."""

    last_name = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    middle_name = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    first_name = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    sex = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    birth_date = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    birth_place = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    class_name = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    matricule = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    guardian_name = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    guardian_phone = serializers.IntegerField(min_value=0, allow_null=True, required=False)


class ImportCountsSerializer(serializers.Serializer):
    rows = serializers.IntegerField()
    ready = serializers.IntegerField()
    warning = serializers.IntegerField(help_text="Importées, à vérifier.")
    error = serializers.IntegerField(help_text="Pas importées.")


class ImportClassSerializer(serializers.Serializer):
    label = serializers.CharField(help_text="Classe écrite dans le fichier.")
    class_group = serializers.UUIDField(allow_null=True, help_text="Classe de l'année ou `null`.")
    chosen = serializers.BooleanField(help_text="Choisie à la main.")
    rows = serializers.IntegerField()


class StudentImportSerializer(serializers.ModelSerializer):
    headers = serializers.ListField(
        child=serializers.CharField(allow_blank=True), help_text="Titres des colonnes du fichier."
    )
    mapping = ImportMappingSerializer()
    class_mapping = serializers.DictField(child=serializers.UUIDField())
    counts = ImportCountsSerializer(source="report.counts")
    missing_fields = serializers.ListField(
        child=serializers.ChoiceField(choices=imports.FIELDS),
        source="report.missing_fields",
        help_text="Champs obligatoires sans colonne.",
    )
    classes = ImportClassSerializer(many=True, source="report.classes")
    importable_count = serializers.SerializerMethodField()

    class Meta:
        model = StudentImport
        fields = [
            "id",
            "academic_year",
            "file_name",
            "sheet_name",
            "headers",
            "mapping",
            "class_mapping",
            "status",
            "counts",
            "missing_fields",
            "classes",
            "importable_count",
            "created_count",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_importable_count(self, imp: StudentImport) -> int:
        return imports.importable_count(imp)


class StudentImportCreateSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Excel (.xlsx) ou CSV, 5 Mo au plus.")
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects,
        required=False,
        help_text="Année des classes du fichier ; l'année en cours si absente.",
    )


class StudentImportUpdateSerializer(serializers.Serializer):
    mapping = ImportMappingSerializer(required=False)
    class_mapping = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True),
        required=False,
        help_text="Classe du fichier → identifiant d'une classe de l'année (vide : automatique).",
    )


class ImportIssueSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="Problème (`imports.ISSUES`) : `invalid_date`, `unknown_class`…"
    )
    line = serializers.IntegerField(required=False, help_text="Autre ligne concernée.")


class ImportValuesSerializer(serializers.Serializer):
    last_name = serializers.CharField()
    middle_name = serializers.CharField()
    first_name = serializers.CharField()
    sex = serializers.CharField()
    birth_date = serializers.CharField()
    birth_place = serializers.CharField()
    class_name = serializers.CharField()
    matricule = serializers.CharField()
    guardian_name = serializers.CharField()
    guardian_phone = serializers.CharField()


class ImportLineSerializer(serializers.Serializer):
    line = serializers.IntegerField(help_text="Numéro de la ligne dans le fichier.")
    status = serializers.ChoiceField(choices=["ready", "warning", "error"])
    issues = ImportIssueSerializer(many=True)
    values = ImportValuesSerializer(help_text="Valeurs du fichier, telles quelles.")


class ImportLineFilterSerializer(serializers.Serializer):
    problems = serializers.BooleanField(
        required=False, default=False, help_text="Seulement les erreurs et les avertissements."
    )


class RegistrationFormQuerySerializer(serializers.Serializer):
    """Fiche d'inscription (D5, M11)."""

    output = serializers.ChoiceField(
        choices=["pdf", "html"],
        default="pdf",
        help_text="`html` : aperçu dans la page, code famille masqué ; `pdf` : à imprimer.",
    )
    paper = serializers.ChoiceField(choices=documents.PAPERS, default="a4")
    family_code = serializers.BooleanField(
        default=False,
        help_text="Imprimer le code famille (pour le tuteur principal) ; chaque PDF qui "
        "l'imprime est noté dans le journal d'audit. Décoché : fiche remise à un tiers.",
    )
    fees = serializers.BooleanField(
        default=False,
        help_text="Frais de l'année de l'élève, après réductions, par devise : avec un droit "
        "de lecture des frais (comme `/api/student-charges/`), sinon 403.",
    )


class ClassListQuerySerializer(serializers.Serializer):
    """Liste de classe (D5, M11) : élèves actifs de la classe."""

    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects)
    output = serializers.ChoiceField(choices=["pdf", "xlsx", "html"], default="pdf")
    columns = serializers.MultipleChoiceField(
        choices=documents.COLUMNS,
        required=False,
        help_text="Colonnes en plus du N° et du nom (paramètre répété) ; `payments` "
        "(situation des paiements) : avec `finance.view_reports`, sinon 403.",
    )
    blank_columns = serializers.IntegerField(
        min_value=0,
        max_value=documents.MAX_BLANK_COLUMNS,
        default=0,
        help_text="Colonnes vides à droite : appel, signatures, notes à la main.",
    )
    order = serializers.ChoiceField(
        choices=[documents.BY_NAME, documents.BY_MATRICULE], default=documents.BY_NAME
    )


# Coordonnées envoyées par les parents (H5, M18)


class ContactAddressSerializer(serializers.Serializer):
    commune = serializers.CharField(max_length=80, allow_blank=True, default="")
    quartier = serializers.CharField(max_length=80, allow_blank=True, default="")
    avenue = serializers.CharField(max_length=120, allow_blank=True, default="")
    number = serializers.CharField(max_length=20, allow_blank=True, default="")


class EmergencyContactSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, allow_blank=True, default="")
    phone = PhoneField(allow_blank=True, default="", help_text="Ex. 0971234567.")

    def validate(self, data):
        if bool(data["full_name"]) != bool(data["phone"]):
            raise serializers.ValidationError(
                _("Give the name and the phone number."), code="incomplete"
            )
        return data


class ContactDetailsSerializer(serializers.Serializer):
    """Coordonnées que le parent tient à jour : adresse (celle de ses enfants), e-mail (le
    sien), contact d'urgence. Le numéro de son compte ne change pas ici."""

    address = ContactAddressSerializer()
    email = serializers.EmailField(allow_blank=True)
    emergency_contact = EmergencyContactSerializer()


class AddressChangeSerializer(serializers.Serializer):
    before = ContactAddressSerializer()
    after = ContactAddressSerializer()


class EmailChangeSerializer(serializers.Serializer):
    before = serializers.CharField()
    after = serializers.CharField()


class EmergencyChangeSerializer(serializers.Serializer):
    before = EmergencyContactSerializer()
    after = EmergencyContactSerializer()


class ChangesSerializer(serializers.Serializer):
    """Seulement ce qui diffère de la fiche au moment de l'envoi."""

    address = AddressChangeSerializer(required=False)
    email = EmailChangeSerializer(required=False)
    emergency_contact = EmergencyChangeSerializer(required=False)


class ContactChangeFamilySerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = ["id", "code", "parent", "phone", "children"]

    def _primary(self, family: Family) -> Guardian | None:
        return next(iter(family.primary_guardians), None)

    def get_parent(self, family: Family) -> str:
        primary = self._primary(family)
        return primary.full_name if primary else ""

    def get_phone(self, family: Family) -> str:
        primary = self._primary(family)
        return primary.phone if primary else ""

    def get_children(self, family: Family) -> list[str]:
        return [student.full_name for student in family.students.all()]


class ContactChangeSerializer(serializers.ModelSerializer):
    family = ContactChangeFamilySerializer()
    changes = ChangesSerializer()
    handled_by = serializers.CharField(
        source="handled_by.__str__", default=None, allow_null=True, read_only=True
    )

    class Meta:
        model = ContactChange
        fields = ["id", "family", "changes", "status", "created_at", "handled_by", "handled_at"]


class ContactChangeFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["pending", "handled", "all"],
        default="pending",
        help_text="À traiter (par défaut), traitées (appliquées ou non) ou toutes.",
    )
