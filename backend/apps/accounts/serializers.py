from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts import services
from apps.accounts.login import Step
from apps.accounts.models import Membership, Role, User
from apps.accounts.modules import MODULE_CHOICES
from apps.accounts.phone import INVALID_PHONE_MESSAGE, InvalidPhoneError, normalize_phone
from apps.accounts.roles import PERMISSION_CHOICES, TOTP_PERMISSIONS
from apps.schools.models import School
from apps.schools.serializers import DocumentSignersSerializer, logo_url


class PermissionListField(serializers.ListField):
    child = serializers.ChoiceField(choices=PERMISSION_CHOICES)


class RoleSerializer(serializers.ModelSerializer):
    """Rôle de l'école : un nom et des permissions."""

    permissions = PermissionListField(required=False)
    member_count = serializers.SerializerMethodField(
        help_text="Comptes actifs qui ont ce rôle dans l'école."
    )

    class Meta:
        model = Role
        fields = ["id", "name", "permissions", "member_count"]
        read_only_fields = ["id"]
        # Nom manquant ou vide : refusé par le service (`role_name_required`).
        extra_kwargs = {"name": {"required": False, "allow_blank": True}}

    @extend_schema_field(serializers.IntegerField())
    def get_member_count(self, role: Role) -> int:
        if hasattr(role, "active_member_count"):
            return role.active_member_count
        return role.memberships.filter(is_active=True).count()


class RoleSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]


class StaffUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "last_name", "middle_name", "first_name"]


TOTP_STATUS_CHOICES = [
    ("enabled", "Turned on"),
    ("to_enable", "Required by their roles in this school, not turned on yet"),
    ("not_required", "Not required"),
]


class StaffSerializer(serializers.ModelSerializer):
    """Une personne dans l'école (son appartenance) ; `id` est celui de l'appartenance. Rien sur
    ses autres écoles."""

    user = StaffUserSerializer(read_only=True)
    roles = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    totp = serializers.SerializerMethodField(help_text="Double authentification (colonne de M3).")
    last_login_at = serializers.DateTimeField(
        read_only=True, allow_null=True, help_text="Dernière connexion à cette école."
    )
    account_managed_here = serializers.SerializerMethodField(
        help_text="L'école peut changer les noms, le téléphone, le mot de passe et la double "
        "authentification : le compte ne sert dans aucune autre école."
    )

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "roles",
            "is_active",
            "totp",
            "last_login_at",
            "account_managed_here",
            "created_at",
        ]

    @extend_schema_field(serializers.ChoiceField(choices=TOTP_STATUS_CHOICES))
    def get_totp(self, membership: Membership) -> str:
        if membership.user.totp_enabled:
            return "enabled"
        permissions = {code for role in membership.roles.all() for code in role.permissions}
        return "to_enable" if permissions & TOTP_PERMISSIONS else "not_required"

    @extend_schema_field(serializers.BooleanField())
    def get_account_managed_here(self, membership: Membership) -> bool:
        if hasattr(membership, "used_elsewhere"):
            return not (membership.used_elsewhere or membership.user.is_platform_admin)
        return services.account_managed_by(membership.user, membership.school)


class StaffFilterSerializer(serializers.Serializer):
    """Filtres de la liste du personnel (M3)."""

    search = serializers.CharField(
        required=False,
        max_length=100,
        help_text="Dans le nom, le post-nom, le prénom ou le téléphone.",
    )
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects, required=False, help_text="Personnes qui ont ce rôle."
    )
    is_active = serializers.BooleanField(
        required=False, allow_null=True, default=None, help_text="Actives ou désactivées."
    )


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
    """Rôles et état dans l'école ; noms et téléphone seulement si `account_managed_here`."""

    roles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Role.objects, allow_empty=False, required=False
    )
    is_active = serializers.BooleanField(required=False)
    phone = PhoneField(required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class TemporaryPasswordSerializer(serializers.Serializer):
    temporary_password = serializers.CharField(
        help_text="Affiché une seule fois, à changer à la prochaine connexion."
    )


class MySchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["code", "name", "status"]


class MeSchoolSerializer(serializers.Serializer):
    """Une école du compte (appartenance active) : choix et changement d'école (M2). Les rôles
    sont ceux du compte dans cette école seulement."""

    code = serializers.CharField(source="school.code")
    name = serializers.CharField(source="school.name")
    status = serializers.ChoiceField(source="school.status", choices=School.Status.choices)
    url = serializers.CharField(
        source="school.url", help_text="Adresse de l'école : on s'y connecte pour y travailler."
    )
    primary_color = serializers.CharField(source="school.primary_color")
    text_color = serializers.CharField(source="school.text_color")
    logo = serializers.SerializerMethodField(
        help_text="Adresse complète du logo, à l'adresse de l'école ; null sans logo."
    )
    roles = RoleSummarySerializer(many=True, source="role_list")
    last_login_at = serializers.DateTimeField(
        allow_null=True, help_text="Dernière connexion du compte à cette école."
    )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_logo(self, membership: Membership) -> str | None:
        path = logo_url(membership.school)
        return None if path is None else membership.school.url + path


class CurrentSchoolAccessSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    roles = RoleSummarySerializer(many=True)
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSION_CHOICES))
    modules = serializers.ListField(
        child=serializers.ChoiceField(choices=MODULE_CHOICES),
        help_text="Fonctions que la plateforme a données à l'école (M.1) ; vide : aucune.",
    )
    documents = DocumentSignersSerializer(
        help_text="Cachet et signatures posés sur les documents que la Gestion imprime (DOC.1)."
    )
    homeroom = serializers.BooleanField(
        help_text="Titulaire d'une classe de l'année en cours : menu « Ma classe » (NB.3)."
    )


class SupportSessionSerializer(serializers.Serializer):
    """Session support en cours (A3) : l'interface affiche un bandeau rouge permanent."""

    school = MySchoolSerializer()
    reason = serializers.CharField()
    started_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(help_text="Fermée d'elle-même à cette heure (1 h).")


class SupportStartSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=200,
        help_text="Motif, lu par l'école dans son journal (ex. demande du directeur).",
    )


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField()
    first_name = serializers.CharField()
    language = serializers.ChoiceField(choices=User.Language.choices)
    totp_enabled = serializers.BooleanField()
    totp_enabled_at = serializers.DateTimeField(allow_null=True)
    totp_required = serializers.BooleanField(
        help_text="Un rôle du compte l'exige : impossible de la désactiver."
    )
    recovery_codes_left = serializers.IntegerField(
        help_text="Codes de secours pas encore utilisés (alerte à 2 ou moins, M4)."
    )
    is_platform_admin = serializers.BooleanField(
        help_text="Super-admin : aucun droit dans une école hors session support (A3)."
    )
    schools = MeSchoolSerializer(
        many=True, help_text="Écoles où le compte a une appartenance active (choix de l'école)."
    )
    school = CurrentSchoolAccessSerializer(
        allow_null=True,
        help_text="Rôles et permissions dans l'école de l'adresse ; null sans accès à cette école.",
    )
    support = SupportSessionSerializer(
        allow_null=True,
        help_text="Session support du super-admin dans l'école de l'adresse (bandeau rouge).",
    )


class MeUpdateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=User.Language.choices)


# Connexion et sécurité du compte


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=64, help_text="Ex. 0971234567 ou +243971234567.")
    password = serializers.CharField(
        max_length=128, trim_whitespace=False, style={"input_type": "password"}
    )


class LoginStepSerializer(serializers.Serializer):
    step = serializers.ChoiceField(
        choices=Step.choices, help_text="Étape suivante de la connexion ; `done` : connecté."
    )


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=20,
        help_text="Code à 6 chiffres de l'application, ou code de secours (ex. 7KQ4-M2XP).",
    )


class LoginCodeSerializer(CodeSerializer):
    trust_device = serializers.BooleanField(
        default=False, help_text="Ne plus demander le code sur cet appareil pendant 7 jours."
    )


class TotpSetupSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Double authentification déjà activée (changer de téléphone) : code actuel ou "
        "code de secours.",
    )


class TotpKeySerializer(serializers.Serializer):
    secret = serializers.CharField(help_text="Clé à taper si on ne peut pas scanner le QR code.")
    otpauth_uri = serializers.CharField(help_text="Contenu du QR code à scanner.")


class RecoveryCodesSerializer(serializers.Serializer):
    recovery_codes = serializers.ListField(
        child=serializers.CharField(), help_text="Affichés une seule fois : à imprimer."
    )


class TotpActivatedSerializer(LoginStepSerializer, RecoveryCodesSerializer):
    pass


class PasswordSerializer(serializers.Serializer):
    """Connexion en cours avec un mot de passe provisoire : `new_password` seul. Compte connecté :
    `current_password` aussi."""

    current_password = serializers.CharField(
        max_length=128, required=False, trim_whitespace=False, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        max_length=128, trim_whitespace=False, style={"input_type": "password"}
    )

    def validate_new_password(self, value: str) -> str:
        user = self.context["user"]
        try:
            validate_password(value, user)
        except DjangoValidationError as exc:
            # Garde le code de chaque règle (`password_too_short`…) : l'interface le traduit.
            raise serializers.ValidationError(get_error_detail(exc)) from None
        if user.check_password(value):
            raise serializers.ValidationError(
                _("Choose a password different from the current one."), code="same_password"
            )
        return value
