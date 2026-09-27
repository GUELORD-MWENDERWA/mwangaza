from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PhoneField
from apps.schools.models import AcademicYear, ClassGroup, Track
from apps.students.models import Enrollment, Family, Guardian, Student


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
        fields = ["id", "code", "guardians", "student_count", "activated_at"]


class FamilyStudentSerializer(serializers.ModelSerializer):
    # Classe de l'année en cours, ou vide.
    class_group_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "last_name", "middle_name", "first_name", "class_group_name"]

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

    class Meta(_StudentFields.Meta):
        fields = [
            *_StudentFields.Meta.fields,
            "family",
            "family_code",
            "enrollment",
            "primary_guardian",
        ]

    @extend_schema_field(EnrollmentSerializer(allow_null=True))
    def get_enrollment(self, student: Student) -> dict | None:
        enrollments = getattr(student, "year_enrollments", [])
        return EnrollmentSerializer(enrollments[0]).data if enrollments else None

    @extend_schema_field(GuardianSerializer(allow_null=True))
    def get_primary_guardian(self, student: Student) -> dict | None:
        guardians = student.family.guardians.all()
        return GuardianSerializer(guardians[0]).data if guardians else None


class StudentSerializer(_StudentFields):
    address = AddressSerializer(read_only=True)
    family = FamilySerializer(read_only=True)
    enrollments = EnrollmentSerializer(many=True, read_only=True)

    class Meta(_StudentFields.Meta):
        fields = [
            *_StudentFields.Meta.fields,
            "birth_place",
            "nationality",
            "origin_province",
            "origin_territory",
            "address",
            "photo_consent",
            "previous_school",
            "family",
            "enrollments",
            "created_at",
        ]


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
    status = serializers.ChoiceField(
        choices=["active", "left", "not_enrolled"],
        required=False,
        help_text="Cette année : inscrit et présent, inscrit puis parti (transfert, abandon, "
        "exclusion, fin d'études) ou pas inscrit. Absent : tous.",
    )
