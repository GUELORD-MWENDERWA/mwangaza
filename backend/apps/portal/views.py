from django.conf import settings
from django.utils.text import slugify
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import login
from apps.accounts.views import AuthView
from apps.core.documents import PDF, render
from apps.core.errors import ErrorSerializer
from apps.notifications import push
from apps.notifications.attachments import attachment_response
from apps.notifications.serializers import (
    NotificationPreferencesSerializer,
    NotificationReadSerializer,
    PushSubscriptionSerializer,
    PushUnsubscribeSerializer,
)
from apps.portal import announcements, children, families, notifications, receipts, services
from apps.portal.serializers import (
    AnnouncementsQuerySerializer,
    ChildPaymentsSerializer,
    FamilyCodeSerializer,
    LinkedFamilySerializer,
    LinkSerializer,
    PortalAnnouncementSerializer,
    PortalLoginSerializer,
    PortalMeSerializer,
    PortalNotificationSerializer,
    PortalProfileSerializer,
    ReadSerializer,
)
from apps.students import contact_changes
from apps.students.photos import photo_response
from apps.students.serializers import ContactDetailsSerializer

READ_ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
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
    """Le compte connecté au portail. Lu à chaque ouverture du portail et à chaque retour au
    premier plan : c'est ici, et seulement ici, que la session est prolongée."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(responses={200: PortalMeSerializer, 403: ErrorSerializer, 404: ErrorSerializer})
    def get(self, request: Request) -> Response:
        login.renew_portal_session(request)
        return Response(PortalMeSerializer(request.user).data)


@extend_schema(tags=["portal"])
class ProfileView(APIView):
    """Coordonnées du parent (H5) ; un envoi est transmis à chaque école de ses enfants, qui
    l'applique à sa propre fiche."""

    permission_classes = [PortalAddress, IsAuthenticated]

    def _profile(self, user) -> Response:
        values, schools = contact_changes.profile(user)
        names = [school.name for school in schools]
        return Response(PortalProfileSerializer({**values, "pending_schools": names}).data)

    @extend_schema(responses={200: PortalProfileSerializer, 403: ErrorSerializer})
    def get(self, request: Request) -> Response:
        return self._profile(request.user)

    @extend_schema(
        request=ContactDetailsSerializer,
        responses={200: PortalProfileSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = ContactDetailsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact_changes.submit(request.user, serializer.validated_data)
        return self._profile(request.user)


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


@extend_schema(tags=["portal"])
class ChildView(APIView):
    """Paiements d'un enfant (H3) : frais dus, solde, paiements ; 404 s'il n'est pas d'une
    famille reliée au compte, ou si l'accès ou l'école est suspendu."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(responses={200: ChildPaymentsSerializer, **READ_ERRORS})
    def get(self, request: Request, pk) -> Response:
        return Response(ChildPaymentsSerializer(children.child_payments(request.user, pk)).data)


@extend_schema(tags=["portal"])
class ChildPhotoView(APIView):
    """Photo de l'enfant, seulement avec le consentement du parent (`photo_consent`)."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(
        responses={
            (200, "image/*"): OpenApiResponse(OpenApiTypes.BINARY, description="PNG ou JPEG."),
            **READ_ERRORS,
        }
    )
    def get(self, request: Request, pk):
        student = children.find_student(request.user, pk)
        response = photo_response(student) if student.photo_consent else None
        if response is None:
            raise NotFound
        return response


@extend_schema(tags=["portal"])
class ReceiptView(APIView):
    """Reçu d'un paiement en PDF A5 ; 404 pour un paiement annulé ou d'une autre famille."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(
        responses={
            (200, PDF): OpenApiResponse(OpenApiTypes.BINARY, description="Reçu PDF."),
            **READ_ERRORS,
        }
    )
    def get(self, request: Request, pk):
        payment = receipts.find_payment(request.user, pk)
        with children.in_school(payment.school):
            context = receipts.receipt_document(payment)
            name = f"recu-{slugify(context['number'])}.pdf"
            return render("portal/receipt.html", context, "pdf", name)


@extend_schema(tags=["portal"])
class AnnouncementsView(ListAPIView):
    """Annonces des écoles reliées qui visent la famille (H4), les plus récentes d'abord."""

    permission_classes = [PortalAddress, IsAuthenticated]
    serializer_class = PortalAnnouncementSerializer

    @extend_schema(
        parameters=[AnnouncementsQuerySerializer],
        responses={200: PortalAnnouncementSerializer(many=True), 403: ErrorSerializer},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    def list(self, request: Request, *args, **kwargs) -> Response:
        query = AnnouncementsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        found = announcements.readers(request.user, query.validated_data.get("family"))
        page = self.paginate_queryset(announcements.visible(request.user, found))
        announcements.describe(page, found)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


@extend_schema(tags=["portal"])
class AnnouncementsReadView(APIView):
    """Marque lues les annonces affichées (« lue par N familles » dans la Gestion)."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(request=ReadSerializer, responses={204: None, 400: ErrorSerializer})
    def post(self, request: Request) -> Response:
        serializer = ReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcements.mark_read(request.user, serializer.validated_data["ids"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["portal"])
class AnnouncementAttachmentView(APIView):
    """PDF joint à une annonce qui vise la famille ; 404 sinon ou sans pièce jointe."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(
        responses={
            (200, PDF): OpenApiResponse(OpenApiTypes.BINARY, description="PDF."),
            **READ_ERRORS,
        }
    )
    def get(self, request: Request, pk):
        response = attachment_response(announcements.find(request.user, pk))
        if response is None:
            raise NotFound
        return response


@extend_schema(tags=["portal"])
class NotificationsView(ListAPIView):
    """Centre de notifications du parent (5.5.2), toutes ses écoles mêlées, les plus récentes
    d'abord ; `unread` : seulement les non lues (leur nombre : `count`)."""

    permission_classes = [PortalAddress, IsAuthenticated]
    serializer_class = PortalNotificationSerializer

    @extend_schema(
        parameters=[OpenApiParameter("unread", bool, description="Seulement les non lues.")],
        responses={200: PortalNotificationSerializer(many=True), 403: ErrorSerializer},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        found = notifications.inbox(self.request.user)
        if self.request.query_params.get("unread") in ("1", "true"):
            found = found.filter(read_at__isnull=True)
        return found


@extend_schema(tags=["portal"])
class NotificationsReadView(APIView):
    """Noter comme lues celles données, ou toutes."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(request=NotificationReadSerializer, responses={204: None, 400: ErrorSerializer})
    def post(self, request: Request) -> Response:
        serializer = NotificationReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notifications.mark_read(request.user, serializer.validated_data.get("ids"))
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["portal"])
class NotificationsTestView(APIView):
    """Notification d'essai, envoyée sur les écrans abonnés de ce compte."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(
        request=None, responses={201: PortalNotificationSerializer, 409: ErrorSerializer}
    )
    def post(self, request: Request) -> Response:
        notification = notifications.send_test(request.user)
        data = PortalNotificationSerializer(notification).data
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["portal"])
class NotificationPreferencesView(APIView):
    """Préférences du compte (sortes coupées sur l'écran) et clé publique pour s'abonner."""

    permission_classes = [PortalAddress, IsAuthenticated]
    kinds = push.offered_kinds(notifications.APP)

    def _response(self, muted: list[str]) -> Response:
        key = settings.WEBPUSH_VAPID_PUBLIC_KEY if push.is_configured() else ""
        return Response({"vapid_public_key": key, "kinds": self.kinds, "muted": muted})

    @extend_schema(request=None, responses={200: NotificationPreferencesSerializer})
    def get(self, request: Request) -> Response:
        return self._response(push.muted_kinds(request.user, self.kinds))

    @extend_schema(
        request=NotificationPreferencesSerializer,
        responses={200: NotificationPreferencesSerializer, 400: ErrorSerializer},
    )
    def put(self, request: Request) -> Response:
        serializer = NotificationPreferencesSerializer(
            data=request.data, context={"kinds": self.kinds}
        )
        serializer.is_valid(raise_exception=True)
        muted = push.set_muted_kinds(request.user, self.kinds, serializer.validated_data["muted"])
        return self._response(muted)


@extend_schema(tags=["portal"])
class PushSubscribeView(APIView):
    """Abonner ce navigateur aux notifications sur l'écran de ce compte (Web Push)."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(request=PushSubscriptionSerializer, responses={204: None, 400: ErrorSerializer})
    def post(self, request: Request) -> Response:
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        push.subscribe(
            request.user,
            app=notifications.APP,
            school=None,
            endpoint=data["endpoint"],
            p256dh=data["keys"]["p256dh"],
            auth=data["keys"]["auth"],
            ua=request.headers.get("User-Agent", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["portal"])
class PushUnsubscribeView(APIView):
    """Ce navigateur ne reçoit plus rien sur l'écran (désactivation, déconnexion)."""

    permission_classes = [PortalAddress, IsAuthenticated]

    @extend_schema(request=PushUnsubscribeSerializer, responses={204: None, 400: ErrorSerializer})
    def post(self, request: Request) -> Response:
        serializer = PushUnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        push.unsubscribe(
            request.user,
            app=notifications.APP,
            school=None,
            endpoint=serializer.validated_data["endpoint"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
