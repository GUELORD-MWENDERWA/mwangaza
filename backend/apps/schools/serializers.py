from rest_framework import serializers

from apps.schools.models import School


class CurrentSchoolSerializer(serializers.ModelSerializer):
    """Informations publiques de l'école (écran de connexion) ; logo et couleur en 1.5."""

    class Meta:
        model = School
        fields = ["code", "name"]
