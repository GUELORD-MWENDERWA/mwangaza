from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Membership, Role, User
from apps.accounts.phone import INVALID_PHONE_MESSAGE, InvalidPhoneError, normalize_phone
from apps.accounts.roles import PERMISSION_CHOICES, SYSTEM_ROLES
from apps.schools.models import School


class PermissionListField(serializers.ListField):
    child = serializers.ChoiceField(choices=PERMISSION_CHOICES)


def role_code_field() -> serializers.ChoiceField:
    return serializers.ChoiceField(
        choices=[(code, role.label) for code, role in SYSTEM_ROLES.items()],
        allow_blank=True,
        read_only=True,
        help_text="Code du rôle système ; vide pour un rôle créé par l'école.",
    )


class RoleSerializer(serializers.ModelSerializer):
    """Rôle de l'école. `name` vide pour un rôle système : l'interface affiche le nom traduit de
    son `code`."""

    code = role_code_field()
    is_system = serializers.BooleanField(read_only=True)
    permissions = PermissionListField(required=False)
    member_count = serializers.SerializerMethodField(
        help_text="Comptes actifs qui ont ce rôle dans l'école."
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name", "is_system", "permissions", "member_count"]
        read_only_fields = ["id", "code"]
        extra_kwargs = {"name": {"required": False, "allow_blank": True}}

    @extend_schema_field(serializers.IntegerField())
    def get_member_count(self, role: Role) -> int:
        if hasattr(role, "active_member_count"):
            return role.active_member_count
        return role.memberships.filter(is_active=True).count()


class RoleSummarySerializer(serializers.ModelSerializer):
    code = role_code_field()

    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class StaffUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "last_name", "middle_name", "first_name"]


class StaffSerializer(serializers.ModelSerializer):
    """Une personne dans l'école (son appartenance) ; `id` est celui de l'appartenance. Rien sur
    ses autres écoles."""

    user = StaffUserSerializer(read_only=True)
    roles = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "roles", "is_active", "created_at"]


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        try:
            return normalize_phone(super().to_internal_value(data))
        except InvalidPhoneError:
            raise serializers.ValidationError(INVALID_PHONE_MESSAGE, code="invalid_phone") from None


class StaffCreateSerializer(serializers.Serializer):
    """Nouveau numéro : `last_name` obligatoire. Numéro déjà connu : noms ignorés."""

    phone = PhoneField(help_text="Ex. 0971234567 ou +243971234567.")
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    # `Role.objects` (le manager) : lu à chaque requête, seulement les rôles de l'école courante.
    roles = serializers.PrimaryKeyRelatedField(many=True, queryset=Role.objects, allow_empty=False)


class StaffCreatedSerializer(StaffSerializer):
    existing_account = serializers.BooleanField(
        help_text="Le numéro avait déjà un compte : ajouté à l'école sans nouveau mot de passe."
    )
    temporary_password = serializers.CharField(
        allow_null=True,
        help_text="Nouveau compte seulement : affiché une seule fois, à changer à la connexion.",
    )

    class Meta(StaffSerializer.Meta):
        fields = [*StaffSerializer.Meta.fields, "existing_account", "temporary_password"]


class StaffUpdateSerializer(serializers.Serializer):
    roles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Role.objects, allow_empty=False, required=False
    )
    is_active = serializers.BooleanField(required=False)


class MySchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["code", "name", "status"]


class CurrentSchoolAccessSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    roles = RoleSummarySerializer(many=True)
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSION_CHOICES))


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField()
    first_name = serializers.CharField()
    language = serializers.ChoiceField(choices=User.Language.choices)
    must_change_password = serializers.BooleanField()
    schools = MySchoolSerializer(
        many=True, help_text="Écoles où le compte a une appartenance active (choix de l'école)."
    )
    school = CurrentSchoolAccessSerializer(
        allow_null=True,
        help_text="Rôles et permissions dans l'école de l'adresse ; null sans accès à cette école.",
    )
