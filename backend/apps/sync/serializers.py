from rest_framework import serializers

from apps.sync.models import Device


class DeviceSerializer(serializers.ModelSerializer):
    """Un appareil du compte dans l'école (« Appareils connectés » de Mon compte)."""

    is_current = serializers.SerializerMethodField(help_text="Appareil de cette session.")

    class Meta:
        model = Device
        fields = ["id", "label", "prefix", "created_at", "last_seen_at", "is_current"]
        read_only_fields = fields

    def get_is_current(self, device: Device) -> bool:
        return str(device.pk) == self.context.get("current_device")


class DeviceRegisterSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=80, help_text="Ex. « Windows · Edge ».")
    public_key = serializers.CharField(
        max_length=400, help_text="Clé publique ECDSA P-256 (SPKI, base64) créée par WebCrypto."
    )
