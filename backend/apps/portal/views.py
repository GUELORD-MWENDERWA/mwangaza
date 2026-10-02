from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import login
from apps.accounts.views import AuthView
from apps.core.errors import ErrorSerializer
from apps.portal import families, services
from apps.portal.serializers import (
    FamilyCodeSerializer,
    LinkedFamilySerializer,
    LinkSerializer,
    PortalLoginSerializer,
    PortalMeSerializer,
)

ERRORS = {
    400: ErrorSerializer,
    403: ErrorSerializer,
    404: ErrorSerializer,
    409: ErrorSerializer,
    429: ErrorSerializer,
}


class PortalAddress(BasePermission):
    """Le portail n'a pas d'école (`parents.mwangaza.school`) : à l'adresse d'une école, ces
    points d'API n'existent pas (une session du portail n'y est jamais ouverte)."""

    def has_permission(self, request, view) -> bool:
        if request.school is not None:
            raise NotFound
        return True


@extend_schema(tags=["portal"])
class PortalAuthView(AuthView):
    """Sans compte connecté ; CSRF vérifié (`AuthView`). Réponse : le compte, connecté."""

    permission_classes = [PortalAddress]
    serializer_class = FamilyCodeSerializer
    service = None

    @extend_schema(responses={200: PortalMeSerializer, **ERRORS})
    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = type(self).service(request, **serializer.validated_data)
        return Response(PortalMeSerializer(user).data)


class LoginView(PortalAuthView):
    """Connexion : numéro et mot de passe."""

    serializer_class = PortalLoginSerializer
    service = login.log_in_portal


class ActivateView(PortalAuthView):
    """Activation (H1) : numéro du tuteur principal, code famille, mot de passe choisi."""

    service = services.activate


class ResetView(PortalAuthView):
    """Mot de passe oublié : numéro, nouveau code donné par l'école, nouveau mot de passe."""

    service = services.reset_password


@extend_schema(tags=["portal"])
class MeView(APIView):
    """Le compte connecté au portail."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(responses={200: PortalMeSerializer, 403: ErrorSerializer, 404: ErrorSerializer})
    def get(self, request: Request) -> Response:
        return Response(PortalMeSerializer(request.user).data)


@extend_schema(tags=["portal"])
class FamiliesView(APIView):
    """Accueil (H2) : les familles reliées au compte, une par école, avec leurs enfants."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(
        responses={
            200: LinkedFamilySerializer(many=True),
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    )
    def get(self, request: Request) -> Response:
        items = families.linked_families(request.user)
        return Response(LinkedFamilySerializer(items, many=True).data)


@extend_schema(tags=["portal"])
class LinkView(APIView):
    """« Ajouter un enfant d'une autre école » : le code famille remis par cette école."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(request=LinkSerializer, responses={200: LinkedFamilySerializer, **ERRORS})
    def post(self, request: Request) -> Response:
        serializer = LinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family = services.link_family(request, **serializer.validated_data)
        return Response(LinkedFamilySerializer(families.linked(family)).data)
