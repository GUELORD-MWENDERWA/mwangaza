from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.audit.actions import DOMAINS, PLATFORM_DOMAINS, Action, PlatformAction, domain_of
from apps.audit.models import AuditLog, PlatformAuditLog
from apps.sync.models import Device


class AuditActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "last_name", "middle_name", "first_name"]


def _by_support(log: AuditLog) -> bool:
    return log.impersonated_by_id is not None or (
        log.actor is not None and log.actor.is_platform_admin
    )


class AuditDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "prefix", "label"]


class AuditLogSerializer(serializers.ModelSerializer):
    """Une entrée du journal (M6). `before` / `after` : seulement les champs changés."""

    action = serializers.ChoiceField(choices=Action.choices, read_only=True)
    domain = serializers.SerializerMethodField(help_text="Domaine de l'action (filtre de M6).")
    actor = serializers.SerializerMethodField(
        help_text="Qui ; vide pour le support de la plateforme (`by_support`) ou le système."
    )
    by_support = serializers.SerializerMethodField(
        help_text="Action du support de la plateforme : l'interface affiche « Support {nom} »."
    )
    entity_label = serializers.SerializerMethodField(
        help_text="Nom de l'objet au moment de l'action. Rôle noté sans nom (l'école ne l'avait "
        "pas renommé) : son nom d'aujourd'hui dans l'école."
    )

    device = AuditDeviceSerializer(
        read_only=True, allow_null=True, help_text="Appareil enregistré de la session, s'il y en a."
    )
    device_time = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="Heure de l'appareil pour une action faite hors ligne ; `created_at` est alors "
        "l'heure de réception.",
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
            "device",
            "device_time",
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

    def _role_names(self) -> dict:
        # Les rôles de l'école (quelques lignes), lus une fois pour la page ou l'export.
        names = self.context.get("role_names")
        if names is None:
            names = {str(role.pk): role.name for role in Role.objects.all()}
            self.context["role_names"] = names
        return names

    @extend_schema_field(serializers.CharField())
    def get_entity_label(self, log: AuditLog) -> str:
        if log.entity_label or log.entity_type != "accounts.role" or log.entity_id is None:
            return log.entity_label
        # Entrée d'avant M.3.2 sur un rôle sans nom propre : son nom d'aujourd'hui. Un rôle
        # supprimé n'est plus là : son nom est noté dans l'entrée de sa suppression.
        return self._role_names().get(str(log.entity_id), "")

    def to_representation(self, log: AuditLog) -> dict:
        data = super().to_representation(log)
        for side in ("before", "after"):
            roles = (data[side] or {}).get("roles")
            # Rôles d'une personne notés sans nom avant M.3.2 (le journal ne se réécrit pas) :
            # nom d'aujourd'hui, vide si le rôle a été supprimé depuis.
            if roles and any(not role.get("name") for role in roles):
                names = self._role_names()
                data[side] = {
                    **data[side],
                    "roles": [
                        {"id": role["id"], "name": role.get("name") or names.get(role["id"], "")}
                        for role in roles
                    ],
                }
        return data


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


class PlatformLogFilterSerializer(serializers.Serializer):
    """Filtres du journal de la plateforme (console, 5.4.2) ; mêmes dates que M6."""

    domain = serializers.ChoiceField(choices=PLATFORM_DOMAINS, required=False)
    since = serializers.DateField(required=False, help_text="À partir de ce jour.")
    until = serializers.DateField(required=False, help_text="Jusqu'à ce jour.")
    search = serializers.CharField(
        required=False, max_length=100, help_text="Dans le nom de l'objet."
    )

    validate = AuditLogFilterSerializer.validate


class PlatformLogSerializer(serializers.ModelSerializer):
    """Une entrée du journal de la plateforme (console, 5.4.2)."""

    action = serializers.ChoiceField(choices=PlatformAction.choices, read_only=True)
    actor = AuditActorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = PlatformAuditLog
        fields = [
            "id",
            "created_at",
            "action",
            "actor",
            "entity_type",
            "entity_id",
            "entity_label",
            "before",
            "after",
        ]
        read_only_fields = fields


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
