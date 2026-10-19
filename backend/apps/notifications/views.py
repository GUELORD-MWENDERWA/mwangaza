from django.conf import settings
from django.db.models import Count, Prefetch
from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from drf_spectacular.helpers import forced_singular_serializer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts import platform_roles as team
from apps.accounts.permissions import HasPlatformPermission, HasSchoolAccess, school_access
from apps.accounts.roles import ANNOUNCEMENTS_PUBLISH
from apps.accounts.views import SchoolViewSet
from apps.core.documents import PRINT_RESPONSE, print_options, render
from apps.core.errors import ApiError, BusinessError, ErrorSerializer
from apps.notifications import communication, platform, push, services
from apps.notifications.attachments import attachment_response
from apps.notifications.models import (
    Announcement,
    Notification,
    PlatformAnnouncement,
    PushSubscription,
    SchoolEvent,
    Summons,
)
from apps.notifications.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    CalendarQuerySerializer,
    ConsoleAlertsSerializer,
    ConsolePlatformAnnouncementCreateSerializer,
    ConsolePlatformAnnouncementSerializer,
    NotificationPreferencesSerializer,
    NotificationReadSerializer,
    NotificationSerializer,
    PlatformNewsReadSerializer,
    PlatformNewsSerializer,
    PrintQuerySerializer,
    PushSubscriptionSerializer,
    PushUnsubscribeSerializer,
    RecipientsQuerySerializer,
    RecipientsSerializer,
    SchoolEventSerializer,
    StaffAnnouncementSerializer,
    SummonsCreateSerializer,
    SummonsQuerySerializer,
    SummonsSerializer,
)
from apps.schools.models import ClassGroup, School

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
SUPPORT_SESSION = ApiError("support_session", _("Not available during a support session."), 403)
NO_ATTACHMENT = ApiError("no_attachment", _("This announcement has no attachment."), 404)


@extend_schema_view(
    list=extend_schema(responses={200: AnnouncementSerializer(many=True), **ERRORS}),
    create=extend_schema(
        request={"multipart/form-data": AnnouncementCreateSerializer},
        responses={201: AnnouncementSerializer, 400: ErrorSerializer, **ERRORS},
    ),
)
@extend_schema(tags=["announcements"])
class AnnouncementViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, SchoolViewSet):
    """Annonces de l'école aux familles (H4) ou à son personnel (5.7), les plus récentes d'abord :
    publiées tout de suite, jamais modifiées, seulement archivées (retirées du portail ou de la
    Gestion)."""

    required_permission = ANNOUNCEMENTS_PUBLISH
    serializer_class = AnnouncementSerializer
    http_method_names = ["get", "post", "head", "options"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Announcement.all_schools.none()
        groups = ClassGroup.objects.select_related("level", "track")
        return (
            Announcement.objects.select_related("created_by")
            .prefetch_related(Prefetch("class_groups", queryset=groups))
            .annotate(read_by=Count("reads"))
            .order_by("-published_at", "-id")  # GROUP BY : l'ordre du modèle ne compte plus
        )

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def _announcement(self, announcement: Announcement, code=status.HTTP_200_OK) -> Response:
        announcement = self.get_queryset().get(pk=announcement.pk)
        return Response(AnnouncementSerializer(announcement).data, status=code)

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = services.publish(actor=request.user, **serializer.validated_data)
        return self._announcement(announcement, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: AnnouncementSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk=None) -> Response:
        """Retire l'annonce du portail des familles."""
        announcement = services.archive(self.get_object(), actor=request.user)
        return self._announcement(announcement)

    @extend_schema(
        responses={
            (200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY, description="PDF."),
            **ERRORS,
        },
    )
    @action(detail=True, methods=["get"])
    def attachment(self, request: Request, pk=None):
        """PDF joint à l'annonce, jamais public."""
        response = attachment_response(self.get_object())
        if response is None:
            return Response(NO_ATTACHMENT.body(), status=NO_ATTACHMENT.status)
        return response

    @extend_schema(
        parameters=[RecipientsQuerySerializer],
        responses={200: RecipientsSerializer, 400: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["get"])
    def recipients(self, request: Request) -> Response:
        """Nombre de familles, ou de personnes de l'école, qu'une annonce toucherait (« Publier
        pour 156 familles »)."""
        query = RecipientsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        audience = query.validated_data["audience"]
        families = services.recipient_families(
            audience, query.validated_data.get("class_groups", [])
        )
        to_staff = audience == Announcement.Audience.STAFF
        counts = {
            "families": families.count(),
            "staff": services.staff_members().count() if to_staff else 0,
        }
        return Response(RecipientsSerializer(counts).data)

    @extend_schema(
        parameters=[PrintQuerySerializer],
        responses={**PRINT_RESPONSE, **ERRORS, 400: ErrorSerializer},
    )
    @action(detail=True, methods=["get"])
    def circular(self, request: Request, pk=None) -> HttpResponse:
        """L'annonce en lettre circulaire à l'en-tête de l'école (5.7), à imprimer pour les
        familles qui n'ont pas le portail."""
        params = PrintQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        announcement = self.get_object()
        name = f"circulaire-{slugify(announcement.title)[:60] or 'annonce'}.pdf"
        context = communication.circular_context(announcement)
        data = params.validated_data
        return render(
            "notifications/circular.html", context, data["output"], name, print_options(data)
        )


@extend_schema(tags=["announcements"])
class StaffAnnouncementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Annonces de l'école à son personnel (5.7), les plus récentes d'abord : tout compte de
    l'école les lit, quel que soit son rôle ; une annonce archivée n'y est plus."""

    permission_classes = [HasSchoolAccess]
    serializer_class = StaffAnnouncementSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Announcement.all_schools.none()
        return Announcement.objects.filter(
            audience=Announcement.Audience.STAFF, archived_at__isnull=True
        ).select_related("created_by")

    @extend_schema(
        responses={
            (200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY, description="PDF."),
            **ERRORS,
        },
    )
    @action(detail=True, methods=["get"])
    def attachment(self, request: Request, pk=None):
        """PDF joint à l'annonce, jamais public."""
        response = attachment_response(self.get_object())
        if response is None:
            return Response(NO_ATTACHMENT.body(), status=NO_ATTACHMENT.status)
        return response


@extend_schema_view(
    list=extend_schema(
        parameters=[CalendarQuerySerializer],
        responses={200: SchoolEventSerializer(many=True), **ERRORS},
    ),
    create=extend_schema(responses={201: SchoolEventSerializer, 400: ErrorSerializer, **ERRORS}),
    partial_update=extend_schema(
        responses={200: SchoolEventSerializer, 400: ErrorSerializer, **ERRORS}
    ),
    destroy=extend_schema(responses={204: None, **ERRORS}),
)
@extend_schema(tags=["communication"])
class SchoolEventViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    SchoolViewSet,
):
    """Calendrier de l'école (5.7) : tout le personnel le lit (événements à venir, les plus
    proches d'abord) ; l'écrire demande le droit de publier les annonces."""

    required_permission = ANNOUNCEMENTS_PUBLISH
    serializer_class = SchoolEventSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [HasSchoolAccess()]
        return super().get_permissions()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SchoolEvent.all_schools.none()
        if self.action != "list":
            return SchoolEvent.objects.all()
        query = CalendarQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        return communication.calendar(past=query.validated_data["past"])

    def perform_create(self, serializer) -> None:
        serializer.instance = communication.save_event(
            actor=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer) -> None:
        serializer.instance = communication.save_event(
            serializer.instance, actor=self.request.user, **serializer.validated_data
        )


@extend_schema_view(
    list=extend_schema(
        parameters=[SummonsQuerySerializer],
        responses={200: SummonsSerializer(many=True), **ERRORS},
    ),
    create=extend_schema(
        request=SummonsCreateSerializer,
        responses={201: SummonsSerializer, 400: ErrorSerializer, **ERRORS},
    ),
)
@extend_schema(tags=["communication"])
class SummonsViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, SchoolViewSet):
    """Convocations des parents (5.7), les plus récentes d'abord : jamais modifiées, seulement
    annulées ; lettre PDF à remettre à l'élève, et le parent la voit dans le portail."""

    required_permission = ANNOUNCEMENTS_PUBLISH
    serializer_class = SummonsSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Summons.all_schools.none()
        summons = Summons.objects.select_related("student", "created_by")
        if self.action != "list":
            return summons
        query = SummonsQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        if student := query.validated_data.get("student"):
            summons = summons.filter(student=student)
        return communication.search_summons(summons, query.validated_data.get("search", ""))

    def create(self, request: Request) -> Response:
        serializer = SummonsCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        summons = communication.issue_summons(actor=request.user, **serializer.validated_data)
        return Response(SummonsSerializer(summons).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: SummonsSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        """Annule la convocation : elle quitte le portail du parent."""
        summons = communication.cancel_summons(self.get_object(), actor=request.user)
        return Response(SummonsSerializer(summons).data)

    @extend_schema(
        parameters=[PrintQuerySerializer],
        responses={**PRINT_RESPONSE, **ERRORS, 400: ErrorSerializer},
    )
    @action(detail=True, methods=["get"])
    def letter(self, request: Request, pk=None) -> HttpResponse:
        """Lettre de convocation à l'en-tête de l'école, avec le coupon à renvoyer signé."""
        params = PrintQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        summons = self.get_object()
        name = f"convocation-{slugify(summons.student.full_name)}.pdf"
        context = communication.summons_context(summons)
        data = params.validated_data
        return render(
            "notifications/summons.html", context, data["output"], name, print_options(data)
        )


CONSOLE_ERRORS = {400: ErrorSerializer, **ERRORS}


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        responses={200: ConsolePlatformAnnouncementSerializer(many=True), **CONSOLE_ERRORS}
    ),
    create=extend_schema(
        request=ConsolePlatformAnnouncementCreateSerializer,
        responses={201: ConsolePlatformAnnouncementSerializer, **CONSOLE_ERRORS},
    ),
)
class ConsolePlatformAnnouncementViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Annonces de la plateforme aux écoles (5.4.3), les plus récentes d'abord : super-admin
    seulement, à l'adresse de la console. Publiées tout de suite, jamais modifiées, seulement
    archivées ; chaque publication et archivage va dans le journal de la plateforme."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.NEWS_PUBLISH
    serializer_class = ConsolePlatformAnnouncementSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        schools = Prefetch("schools", queryset=School.objects.order_by("name"))
        return (
            PlatformAnnouncement.objects.select_related("created_by")
            .prefetch_related(schools)
            .annotate(read_by=Count("reads"))
            .order_by("-published_at", "-id")  # GROUP BY : l'ordre du modèle ne compte plus
        )

    def _announcement(self, announcement, code=status.HTTP_200_OK) -> Response:
        announcement = self.get_queryset().get(pk=announcement.pk)
        return Response(ConsolePlatformAnnouncementSerializer(announcement).data, status=code)

    def create(self, request: Request) -> Response:
        serializer = ConsolePlatformAnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = platform.publish(actor=request.user, **serializer.validated_data)
        return self._announcement(announcement, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: ConsolePlatformAnnouncementSerializer, **ERRORS})
    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk=None) -> Response:
        """Retire l'annonce de la Gestion des écoles."""
        announcement = platform.archive(self.get_object(), actor=request.user)
        return self._announcement(announcement)


@extend_schema(tags=["announcements"])
@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("unread", bool, description="Seulement les non lues.")],
        responses={200: PlatformNewsSerializer(many=True), **ERRORS},
    )
)
class PlatformNewsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Annonces de la plateforme que lit le personnel de l'école (5.4.3) : bandeau et liste de la
    Gestion, les plus récentes d'abord. Tout compte de l'école les lit ; « lue » est noté par
    compte (rien pendant une session support)."""

    permission_classes = [HasSchoolAccess]
    serializer_class = PlatformNewsSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PlatformAnnouncement.objects.none()
        announcements = platform.for_school(self.request.school, self.request.user)
        if self.request.query_params.get("unread") in ("1", "true"):
            announcements = announcements.filter(is_read=False)
        return announcements

    @extend_schema(request=PlatformNewsReadSerializer, responses={204: None, **ERRORS})
    @action(detail=False, methods=["post"])
    def read(self, request: Request) -> Response:
        """Noter des annonces comme lues par ce compte (bandeau fermé, liste ouverte)."""
        serializer = PlatformNewsReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if school_access(request).membership is not None:
            platform.mark_read(request.school, request.user, serializer.validated_data["ids"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["console"])
class ConsoleAlertViewSet(viewsets.GenericViewSet):
    """Alertes sur l'écran du super-admin (S.3.2) : ce navigateur s'abonne, dans la console, aux
    alertes sur l'usage des comptes super-admin et sur les sessions support ouvertes. Super-admin
    seulement, à l'adresse de la console."""

    permission_classes = [HasPlatformPermission]
    # Chacun reçoit les alertes de son travail (`notifications/console.py`).
    platform_permission = (team.AUDIT_VIEW, team.LEADS_MANAGE)
    serializer_class = ConsoleAlertsSerializer
    pagination_class = None

    @extend_schema(responses={200: forced_singular_serializer(ConsoleAlertsSerializer), **ERRORS})
    def list(self, request: Request) -> Response:
        """Clé publique pour abonner ce navigateur."""
        key = settings.WEBPUSH_VAPID_PUBLIC_KEY if push.is_configured() else ""
        return Response({"vapid_public_key": key})

    @extend_schema(request=PushSubscriptionSerializer, responses={204: None, **CONSOLE_ERRORS})
    @action(detail=False, methods=["post"])
    def subscribe(self, request: Request) -> Response:
        """Abonner ce navigateur aux alertes de ce compte."""
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        push.subscribe(
            request.user,
            app=PushSubscription.CONSOLE,
            school=None,
            endpoint=data["endpoint"],
            p256dh=data["keys"]["p256dh"],
            auth=data["keys"]["auth"],
            ua=request.headers.get("User-Agent", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=PushUnsubscribeSerializer, responses={204: None, **CONSOLE_ERRORS})
    @action(detail=False, methods=["post"])
    def unsubscribe(self, request: Request) -> Response:
        """Ce navigateur ne reçoit plus les alertes."""
        serializer = PushUnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        push.unsubscribe(
            request.user,
            app=PushSubscription.CONSOLE,
            school=None,
            endpoint=serializer.validated_data["endpoint"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("unread", OpenApiTypes.BOOL, description="Non lues.")],
        responses={200: NotificationSerializer(many=True), **ERRORS},
    )
)
@extend_schema(tags=["notifications"])
class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Notifications de ce compte dans la Gestion de l'école (5.5) : centre de notifications,
    abonnement de ce navigateur (Web Push), préférences. Pendant une session support : rien à
    lire, aucune écriture (le super-admin n'est pas du personnel de l'école)."""

    permission_classes = [HasSchoolAccess]
    serializer_class = NotificationSerializer
    app = Notification.App.GESTION

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.all_schools.none()
        notifications = push.inbox(self.request.user, self.app)
        if self.request.query_params.get("unread") in ("1", "true"):
            notifications = notifications.filter(read_at__isnull=True)
        return notifications

    def _member_only(self) -> None:
        if school_access(self.request).membership is None:
            raise BusinessError(SUPPORT_SESSION)

    @extend_schema(request=NotificationReadSerializer, responses={204: None, **ERRORS})
    @action(detail=False, methods=["post"])
    def read(self, request: Request) -> Response:
        """Noter comme lues celles données, ou toutes."""
        serializer = NotificationReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        push.mark_read(request.user, self.app, serializer.validated_data.get("ids"))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={201: NotificationSerializer, **ERRORS})
    @action(detail=False, methods=["post"])
    def test(self, request: Request) -> Response:
        """Notification d'essai, envoyée sur les écrans abonnés de ce compte."""
        self._member_only()
        [notification] = push.notify(
            [request.user],
            school=request.school,
            app=self.app,
            kind=Notification.Kind.TEST,
            title=_("Notifications are working"),
            body=_("Notifications from %(school)s will appear here, even with the app closed.")
            % {"school": request.school.name},
            url="/notifications",
        )
        return Response(NotificationSerializer(notification).data, status=status.HTTP_201_CREATED)

    def _preferences(self, kinds: list[str], muted: list[str]) -> Response:
        return Response(
            {
                "vapid_public_key": settings.WEBPUSH_VAPID_PUBLIC_KEY
                if push.is_configured()
                else "",
                "kinds": kinds,
                "muted": muted,
            }
        )

    @extend_schema(
        methods=["get"], request=None, responses={200: NotificationPreferencesSerializer, **ERRORS}
    )
    @extend_schema(
        methods=["put"],
        request=NotificationPreferencesSerializer,
        responses={200: NotificationPreferencesSerializer, 400: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["get", "put"])
    def preferences(self, request: Request) -> Response:
        """Préférences du compte (toutes ses écoles) et clé publique pour s'abonner. Sortes
        offertes : celles qu'il peut recevoir avec ses droits dans cette école."""
        kinds = push.offered_kinds(self.app, school_access(request).permissions)
        if request.method == "GET":
            return self._preferences(kinds, push.muted_kinds(request.user, kinds))
        self._member_only()
        serializer = NotificationPreferencesSerializer(data=request.data, context={"kinds": kinds})
        serializer.is_valid(raise_exception=True)
        muted = push.set_muted_kinds(request.user, kinds, serializer.validated_data["muted"])
        return self._preferences(kinds, muted)

    @extend_schema(
        request=PushSubscriptionSerializer, responses={204: None, 400: ErrorSerializer, **ERRORS}
    )
    @action(detail=False, methods=["post"])
    def subscribe(self, request: Request) -> Response:
        """Abonner ce navigateur aux notifications sur l'écran de ce compte, pour cette école."""
        self._member_only()
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        push.subscribe(
            request.user,
            app=self.app,
            school=request.school,
            endpoint=data["endpoint"],
            p256dh=data["keys"]["p256dh"],
            auth=data["keys"]["auth"],
            ua=request.headers.get("User-Agent", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=PushUnsubscribeSerializer, responses={204: None, **ERRORS})
    @action(detail=False, methods=["post"])
    def unsubscribe(self, request: Request) -> Response:
        """Ce navigateur ne reçoit plus rien sur l'écran (désactivation, déconnexion)."""
        serializer = PushUnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        push.unsubscribe(
            request.user,
            app=self.app,
            school=request.school,
            endpoint=serializer.validated_data["endpoint"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
