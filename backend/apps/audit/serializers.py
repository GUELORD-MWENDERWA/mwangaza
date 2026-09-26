from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
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
        "propre : l'interface affiche le nom traduit de son code (rôle `entity_id`).",
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
