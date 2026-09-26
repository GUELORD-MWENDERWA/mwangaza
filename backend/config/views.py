from django.db import connection
from django.db.utils import DatabaseError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

HealthSerializer = inline_serializer(
    name="Health",
    fields={"status": serializers.CharField(), "database": serializers.CharField()},
)


@extend_schema(responses={200: HealthSerializer, 503: HealthSerializer}, tags=["system"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Sonde de disponibilité : l'API répond et la base de données est joignable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return Response({"status": "error", "database": "error"}, status=503)
    return Response({"status": "ok", "database": "ok"})
