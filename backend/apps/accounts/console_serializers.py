"""Comptes dans la console de la plateforme (5.4.1) : liste, fiche, noms, téléphone et accès
(super-admin seulement). Mot de passe provisoire et double authentification passent par leurs
actions."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Membership, User
from apps.accounts.platform_roles import PLATFORM_ROLES, ROLE_CHOICES
from apps.accounts.serializers import PhoneField
from apps.accounts.support import SESSION_STATES
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.audit.serializers import AuditActorSerializer
from apps.core.serializers import PlatformChangeSerializer
from apps.schools.models import School
from apps.students.models import Family


class ConsoleSchoolRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "code", "name"]


class ConsoleMembershipSerializer(serializers.ModelSerializer):
    """Le compte dans une école : ses rôles, actif ou non, dernière connexion à son adresse."""

    school = ConsoleSchoolRefSerializer()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "school", "roles", "is_active", "last_login_at"]

    def get_roles(self, membership: Membership) -> list[str]:
        return [str(role) for role in membership.roles.all()]


class ConsoleFamilySerializer(serializers.ModelSerializer):
    """Une famille du portail reliée au compte (parent)."""

    school = ConsoleSchoolRefSerializer()

    class Meta:
        model = Family
        fields = ["id", "code", "school", "activated_at", "portal_suspended_at"]


class ConsoleAccountSerializer(serializers.ModelSerializer):
    """Un compte vu par le super-admin. Il change les noms, le téléphone (l'identifiant de
    connexion) et l'accès ; un compte super-admin, seulement dans l'administration Django."""

    phone = PhoneField(required=False, help_text="Ex. 0971234567 ou +243971234567.")
    totp_enabled = serializers.BooleanField(read_only=True)
    memberships = ConsoleMembershipSerializer(many=True, read_only=True)
    families = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "last_name",
            "middle_name",
            "first_name",
            "is_active",
            "is_platform_admin",
            "totp_enabled",
            "must_change_password",
            "last_login",
            "memberships",
            "families",
        ]
        read_only_fields = ["is_platform_admin", "must_change_password", "last_login"]

    @extend_schema_field(ConsoleFamilySerializer(many=True))
    def get_families(self, user: User) -> list[dict]:
        families = self.context.get("families", {}).get(user.pk, [])
        return ConsoleFamilySerializer(families, many=True).data


class ConsoleAccountDetailSerializer(ConsoleAccountSerializer):
    HISTORY = 10

    history = serializers.SerializerMethodField(
        help_text="Les derniers changements faits par le support, du plus récent au plus ancien."
    )

    class Meta(ConsoleAccountSerializer.Meta):
        fields = [*ConsoleAccountSerializer.Meta.fields, "created_at", "history"]

    @extend_schema_field(PlatformChangeSerializer(many=True))
    def get_history(self, user: User) -> list[dict]:
        changes = PlatformAuditLog.objects.filter(
            entity_type=user._meta.label_lower, entity_id=str(user.pk)
        ).select_related("actor")[: self.HISTORY]
        return PlatformChangeSerializer(changes, many=True).data


class ConsoleSupportSessionSerializer(serializers.ModelSerializer):
    """Une session support « en tant qu'école » (5.4.2), reconstituée depuis le journal de
    l'école (`support.sessions`)."""

    school = ConsoleSchoolRefSerializer()
    admin = AuditActorSerializer(source="actor", help_text="Super-admin de la session.")
    reason = serializers.CharField(source="after.reason")
    started_at = serializers.DateTimeField(source="created_at")
    expires_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    state = serializers.ChoiceField(
        choices=SESSION_STATES, help_text="`expired` : l'heure est passée sans fermeture."
    )
    actions = serializers.IntegerField(help_text="Actions faites dans l'école pendant la session.")

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "school",
            "admin",
            "reason",
            "started_at",
            "expires_at",
            "ended_at",
            "state",
            "actions",
        ]
        read_only_fields = fields


# Équipe de la plateforme (EQ.1)


class PlatformRoleSerializer(serializers.Serializer):
    """Rôle fixe de l'équipe et ses droits (`platform_roles.py`)."""

    code = serializers.ChoiceField(choices=ROLE_CHOICES)
    label = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())

    @staticmethod
    def roles() -> list[dict]:
        return [
            {"code": code, "label": str(label), "permissions": sorted(rights)}
            for code, (label, rights) in PLATFORM_ROLES.items()
        ]


class PlatformRolesField(serializers.ListField):
    child = serializers.ChoiceField(choices=ROLE_CHOICES)

    def __init__(self, **kwargs):
        super().__init__(min_length=1, **kwargs)


class TeamMemberSerializer(serializers.ModelSerializer):
    """Membre de l'équipe ; `must_change_password` : invitation pas encore utilisée."""

    roles = PlatformRolesField(source="platform_roles")
    totp_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "last_name",
            "middle_name",
            "first_name",
            "roles",
            "totp_enabled",
            "must_change_password",
            "last_login",
            "created_at",
        ]
        read_only_fields = [field for field in fields if field != "roles"]


class TeamInviteSerializer(serializers.Serializer):
    phone = PhoneField(help_text="Son propre numéro, ex. 0971234567 ou +243971234567.")
    last_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    roles = PlatformRolesField()


class TeamInvitedSerializer(serializers.Serializer):
    member = TeamMemberSerializer()
    temporary_password = serializers.CharField(
        help_text="Renvoyé une seule fois, à changer à la première connexion."
    )
