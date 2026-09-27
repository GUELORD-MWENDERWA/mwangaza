from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.accounts.roles import SYSTEM_ROLES
from apps.audit.actions import DOMAINS, Action, domain_of
from apps.audit.models import AuditLog


class AuditActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "last_name", "middle_name", "first_name"]


def _by_support(log: AuditLog) -> bool:
    return log.impersonated_by_id is not None or (
        log.actor is not None and log.actor.is_platform_admin
    )


class AuditLogSerializer(serializers.ModelSerializer):
    """Une entrée du journal (M6). `before` / `after` : seulement les champs changés."""

    action = serializers.ChoiceField(choices=Action.choices, read_only=True)
    domain = serializers.SerializerMethodField(help_text="Domaine de l'action (filtre de M6).")
    actor = serializers.SerializerMethodField(
        help_text="Qui ; vide pour le support Mwangaza (`by_support`) ou le système."
    )
    by_support = serializers.SerializerMethodField(
        help_text="Action du support Mwangaza : l'interface affiche « Support Mwangaza »."
    )
    entity_label = serializers.CharField(
        read_only=True,
        help_text="Nom de l'objet au moment de l'action. Vide pour un rôle système sans nom "
        "propre : l'interface affiche le nom traduit de `role_code`.",
    )
    role_code = serializers.SerializerMethodField(
        help_text="Code du rôle système quand l'objet est un rôle sans nom propre ; sinon null."
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "action",
            "domain",
            "actor",
            "by_support",
            "entity_type",
            "entity_id",
            "entity_label",
            "role_code",
            "before",
            "after",
            "ip",
            "user_agent",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=DOMAINS))
    def get_domain(self, log: AuditLog) -> str:
        return domain_of(log.action)

    @extend_schema_field(AuditActorSerializer(allow_null=True))
    def get_actor(self, log: AuditLog) -> dict | None:
        # Le super-admin n'est pas nommé à l'école.
        if log.actor is None or _by_support(log):
            return None
        return AuditActorSerializer(log.actor).data

    @extend_schema_field(serializers.BooleanField())
    def get_by_support(self, log: AuditLog) -> bool:
        return _by_support(log)

    @extend_schema_field(serializers.ChoiceField(choices=list(SYSTEM_ROLES), allow_null=True))
    def get_role_code(self, log: AuditLog) -> str | None:
        if log.entity_type != "accounts.role" or log.entity_label or log.entity_id is None:
            return None
        # Un rôle supprimé n'est plus là : seul un rôle de l'école (avec un nom) se supprime.
        codes = self.context.setdefault("role_codes", {})
        if log.entity_id not in codes:
            codes[log.entity_id] = (
                Role.objects.filter(pk=log.entity_id).values_list("code", flat=True).first()
            )
        return codes[log.entity_id] or None


class AuditLogFilterSerializer(serializers.Serializer):
    """Filtres de la liste (M6). Dates : jours de l'heure de Goma, bornes comprises."""

    actor = serializers.UUIDField(required=False, help_text="Qui (`id` du compte).")
    action = serializers.ChoiceField(choices=Action.choices, required=False)
    domain = serializers.ChoiceField(choices=DOMAINS, required=False)
    entity = serializers.UUIDField(required=False, help_text="Historique d'un objet (`entity_id`).")
    since = serializers.DateField(required=False, help_text="À partir de ce jour.")
    until = serializers.DateField(required=False, help_text="Jusqu'à ce jour.")
    search = serializers.CharField(
        required=False, max_length=100, help_text="Dans le nom de l'objet."
    )

    def validate(self, data):
        if "since" in data and "until" in data and data["since"] > data["until"]:
            raise serializers.ValidationError(
                {"until": [_("The end date is before the start date.")]}
            )
        return data


# Une année scolaire, avec un peu de marge : au-delà, exporter en plusieurs fois.
EXPORT_MAX_DAYS = 366


class AuditLogExportSerializer(AuditLogFilterSerializer):
    """Export Excel (M6) : mêmes filtres que la liste, période obligatoire et limitée."""

    since = serializers.DateField(help_text="À partir de ce jour.")
    until = serializers.DateField(help_text="Jusqu'à ce jour.")

    def validate(self, data):
        data = super().validate(data)
        if (data["until"] - data["since"]).days >= EXPORT_MAX_DAYS:
            raise serializers.ValidationError(
                {"until": [_("Export at most one year at a time.")]}, code="period_too_long"
            )
        return data
