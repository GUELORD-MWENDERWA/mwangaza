from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.errors import SCHOOL_NOT_FOUND, ErrorSerializer
from apps.schools.serializers import CurrentSchoolSerializer


@extend_schema(responses={200: CurrentSchoolSerializer, 404: ErrorSerializer}, tags=["schools"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def current_school(request: Request) -> Response:
    """École du sous-domaine (public : l'écran de connexion affiche son nom)."""
    if request.school is None:
        return Response(SCHOOL_NOT_FOUND.body(), status=SCHOOL_NOT_FOUND.status)
    return Response(CurrentSchoolSerializer(request.school).data)
