from django.contrib.auth import logout, update_session_auth_hash
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.middleware.csrf import get_token
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ErrorDetail, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import console, login, services, support, totp
from apps.accounts.console_serializers import (
    ConsoleAccountDetailSerializer,
    ConsoleAccountSerializer,
    ConsoleSupportSessionSerializer,
)
from apps.accounts.login import MFA_SESSION_KEY, Step
from apps.accounts.models import Membership, Role, User
from apps.accounts.permissions import (
    HasSchoolAccess,
    HasSchoolPermission,
    IsPlatformAdmin,
    school_access,
)
from apps.accounts.roles import ROLES_MANAGE, sorted_permissions
from apps.accounts.serializers import (
    CodeSerializer,
    LoginCodeSerializer,
    LoginSerializer,
    LoginStepSerializer,
    MeSerializer,
    MeUpdateSerializer,
    PasswordSerializer,
    RecoveryCodesSerializer,
    RoleSerializer,
    StaffCreatedSerializer,
    StaffCreateSerializer,
    StaffFilterSerializer,
    StaffSerializer,
    StaffUpdateSerializer,
    SupportSessionSerializer,
    SupportStartSerializer,
    TemporaryPasswordSerializer,
    TotpActivatedSerializer,
    TotpKeySerializer,
    TotpSetupSerializer,
)
from apps.core.errors import BusinessError, ErrorSerializer
from apps.core.middleware import is_console_host
from apps.core.tenancy import use_all_schools
from apps.schools import signatures
from apps.schools.models import School
from apps.schools.serializers import SignatureUploadSerializer

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
# Étapes de connexion : saisie refusée, trop d'essais, étape expirée ou pas la bonne.
STEP_ERRORS = {
    400: ErrorSerializer,
    403: ErrorSerializer,
    409: ErrorSerializer,
    429: ErrorSerializer,
}

_REQUIRED = ErrorDetail(_("This field is required."), code="required")


class MeView(APIView):
    """Le compte connecté, ses écoles (choix de l'école), ses droits dans l'école de l'adresse
    (menu de la Gestion) et l'état de sa double authentification (Mon compte, M4)."""

    permission_classes = [IsAuthenticated]
    serializer_class = MeUpdateSerializer

    @extend_schema(responses={200: MeSerializer, 403: ErrorSerializer}, tags=["accounts"])
    def get(self, request: Request) -> Response:
        return Response(me_data(request))

    @extend_schema(
        request=MeUpdateSerializer,
        responses={200: MeSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
        tags=["accounts"],
    )
    def patch(self, request: Request) -> Response:
        serializer = MeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.language = serializer.validated_data["language"]
        request.user.save(update_fields=["language", "updated_at"])
        return Response(me_data(request))


@extend_schema(tags=["accounts"])
class MySignatureView(APIView):
    """Ma signature dans l'école de l'adresse (DOC.1, Mon compte), posée sur les documents que
    je donne (reçu, convocation…) : PNG ou JPEG, 1 Mo au plus, enregistrée en PNG, le fond blanc
    rendu transparent. Au journal de l'école."""

    permission_classes = [HasSchoolAccess]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = SignatureUploadSerializer

    def membership(self, request: Request) -> Membership:
        membership = Membership.objects.filter(
            school=request.school, user=request.user, is_active=True
        ).first()
        if membership is None:  # session support du super-admin : il ne signe rien
            raise PermissionDenied(_("Only the staff of the school can sign its documents."))
        return membership

    @extend_schema(
        request={"multipart/form-data": SignatureUploadSerializer},
        responses={200: MeSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = SignatureUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]
        services.set_signature(self.membership(request), image, actor=request.user)
        return Response(me_data(request))

    @extend_schema(request=None, responses={200: MeSerializer, 403: ErrorSerializer})
    def delete(self, request: Request) -> Response:
        services.set_signature(self.membership(request), None, actor=request.user)
        return Response(me_data(request))


def me_data(request: Request) -> dict:
    """Le compte connecté (`MeSerializer`)."""
    user = request.user
    # Rôles de chaque école du compte : lus hors de l'école de l'adresse, pour ce compte seul
    # (la base laisse voir toutes les écoles le temps de les lire, S.6).
    with use_all_schools():
        memberships = list(
            Membership.objects.filter(user=user, is_active=True)
            # Arrêté ou en cours de suppression : plus proposé.
            .exclude(school__status__in=(School.Status.STOPPED, School.Status.DELETING))
            .select_related("school")
            .prefetch_related(
                Prefetch("roles", queryset=Role.all_schools.order_by("id"), to_attr="role_list")
            )
            .order_by("school__name")
        )
    access = school_access(request)
    school = None
    if access is not None:
        here = next((m for m in memberships if m.school_id == request.school.pk), None)
        school = {
            "code": request.school.code,
            "name": request.school.name,
            "roles": access.roles,
            "permissions": sorted_permissions(access.permissions),
            "modules": request.school.modules,
            "documents": signatures.documents(request.school, here),
        }
    me = {
        "id": user.id,
        "phone": user.phone,
        "last_name": user.last_name,
        "middle_name": user.middle_name,
        "first_name": user.first_name,
        "language": user.language,
        "totp_enabled": user.totp_enabled,
        "totp_enabled_at": user.totp_enabled_at,
        "totp_required": services.totp_required(user),
        "recovery_codes_left": services.recovery_codes_left(user),
        "is_platform_admin": user.is_platform_admin,
        "schools": memberships,
        "school": school,
        "support": support.current(request),
    }
    return MeSerializer(me).data


class SchoolViewSet(viewsets.GenericViewSet):
    """Point d'API d'une école : permission `required_permission` vérifiée par le serveur."""

    permission_classes = [HasSchoolPermission]
    required_permission: str | tuple[str, ...]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


@extend_schema_view(
    list=extend_schema(responses={200: RoleSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: RoleSerializer, **ERRORS}),
    create=extend_schema(responses={201: RoleSerializer, 409: ErrorSerializer, **ERRORS}),
    partial_update=extend_schema(responses={200: RoleSerializer, 409: ErrorSerializer, **ERRORS}),
    destroy=extend_schema(responses={204: None, 409: ErrorSerializer, **ERRORS}),
)
@extend_schema(tags=["accounts"])
class RoleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    SchoolViewSet,
):
    """Rôles de l'école (B1 à B2) : ceux du modèle de départ et ceux qu'elle a créés, tous
    renommables, modifiables et supprimables (s'ils ne sont donnés à personne)."""

    serializer_class = RoleSerializer
    required_permission = ROLES_MANAGE

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Role.all_schools.none()
        # Le comptage (GROUP BY) fait oublier l'ordre du modèle : on le redonne.
        return Role.objects.annotate(
            active_member_count=Count("memberships", filter=Q(memberships__is_active=True))
        ).order_by("id")

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.create_role(
            actor=self.request.user,
            name=data.get("name", ""),
            permissions=data.get("permissions", []),
        )

    def perform_update(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.update_role(
            serializer.instance,
            actor=self.request.user,
            name=data.get("name"),
            permissions=data.get("permissions"),
        )

    def perform_destroy(self, instance):
        services.delete_role(instance, actor=self.request.user)


@extend_schema_view(
    list=extend_schema(
        parameters=[StaffFilterSerializer], responses={200: StaffSerializer(many=True), **ERRORS}
    ),
    retrieve=extend_schema(responses={200: StaffSerializer, **ERRORS}),
)
@extend_schema(tags=["accounts"])
class StaffViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SchoolViewSet):
    """Comptes du personnel de l'école (M3). On ne supprime pas un compte : on le désactive."""

    serializer_class = StaffSerializer
    required_permission = ROLES_MANAGE

    def get_serializer_class(self):
        if self.action in {"new_password", "reset_totp"}:
            return serializers.Serializer
        # Selon la méthode (et non l'action) : l'API navigable affiche ainsi le bon formulaire.
        return {"POST": StaffCreateSerializer, "PATCH": StaffUpdateSerializer}.get(
            self.request.method, StaffSerializer
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        # Le compte sert-il dans une autre école ? Oui ou non seulement : jamais laquelle.
        elsewhere = Membership.objects.filter(user=OuterRef("user")).exclude(
            school=OuterRef("school")
        )
        queryset = (
            Membership.objects.filter(school=self.request.school)
            .annotate(used_elsewhere=Exists(elsewhere))
            .select_related("user")
            .prefetch_related("roles")
            .order_by("user__last_name", "user__middle_name", "user__first_name")
        )
        if self.action == "list":
            queryset = self._filter(queryset)
        return queryset

    def _filter(self, queryset):
        params = StaffFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        if data.get("search"):
            queryset = queryset.filter(_person_search(data["search"]))
        if "role" in data:
            queryset = queryset.filter(roles=data["role"])
        if data.get("is_active") is not None:
            queryset = queryset.filter(is_active=data["is_active"])
        return queryset

    @extend_schema(
        request=StaffCreateSerializer,
        responses={
            201: StaffCreatedSerializer,
            400: ErrorSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership, temporary_password = services.add_staff_member(
            actor=request.user, **serializer.validated_data
        )
        data = {
            **StaffSerializer(membership).data,
            "existing_account": temporary_password is None,
            "temporary_password": temporary_password,
        }
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=StaffUpdateSerializer,
        responses={200: StaffSerializer, 409: ErrorSerializer, **ERRORS},
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        membership = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_staff_member(membership, actor=request.user, **serializer.validated_data)
        return Response(StaffSerializer(self.get_object()).data)

    @extend_schema(
        request=None,
        responses={200: TemporaryPasswordSerializer, 409: ErrorSerializer, **ERRORS},
    )
    @action(detail=True, methods=["post"], url_path="new-password")
    def new_password(self, request: Request, pk=None) -> Response:
        """« Nouveau mot de passe » (M3) : seulement pour un compte qui ne sert que dans cette
        école (`account_managed_here`)."""
        password = services.set_temporary_password(self.get_object(), actor=request.user)
        return Response({"temporary_password": password})

    @extend_schema(request=None, responses={200: StaffSerializer, 409: ErrorSerializer, **ERRORS})
    @action(detail=True, methods=["post"], url_path="reset-totp")
    def reset_totp(self, request: Request, pk=None) -> Response:
        """« Réinitialiser la double auth. » (M3) : même règle que le nouveau mot de passe."""
        services.reset_staff_totp(self.get_object(), actor=request.user)
        return Response(StaffSerializer(self.get_object()).data)


def _person_search(text: str) -> Q:
    """Chaque mot dans un des noms, ou chiffres dans le téléphone (« 0971 », « +243 97… »)."""
    condition = Q()
    for word in text.split():
        match = (
            Q(user__last_name__icontains=word)
            | Q(user__middle_name__icontains=word)
            | Q(user__first_name__icontains=word)
        )
        digits = "".join(char for char in word if char.isdigit())
        if digits:
            # Forme nationale (0971…) : le numéro est gardé en +243971…
            match |= Q(user__phone__contains=digits.removeprefix("0") or digits)
        condition &= match
    return condition


# Connexion et sécurité du compte


class AuthView(APIView):
    """Étapes de la connexion et sécurité du compte. Le jeton CSRF est vérifié même sans compte
    connecté : DRF ne le vérifie que pour une session connectée."""

    permission_classes = [AllowAny]

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        if request.method not in SAFE_METHODS:
            SessionAuthentication().enforce_csrf(request)

    def connected_or_pending(self, request: Request, step: Step) -> User:
        """Le compte connecté, ou celui de la connexion en cours si elle en est à `step`."""
        if request.user.is_authenticated:
            return request.user
        return login.expect(request, step)


class StepView(AuthView):
    """GET : l'étape en cours de la connexion (ex. après un rechargement de la page)."""

    @extend_schema(responses={200: LoginStepSerializer})
    def get(self, request: Request) -> Response:
        return Response({"step": login.current_step(request)})


@extend_schema(tags=["auth"])
class CsrfView(AuthView):
    """Donne le cookie CSRF à l'application avant la connexion (en-tête `X-CSRFToken`)."""

    @extend_schema(responses={204: None})
    def get(self, request: Request) -> Response:
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["auth"])
class LoginView(StepView):
    """Étape 1 : numéro et mot de passe. À l'adresse de la console (5.2), seulement le
    super-admin, comme dans l'administration Django."""

    serializer_class = LoginSerializer

    @extend_schema(request=LoginSerializer, responses={200: LoginStepSerializer, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_only = is_console_host(request.get_host())
        step = login.log_in(request, **serializer.validated_data, admin_only=admin_only)
        return Response({"step": step})


@extend_schema(tags=["auth"])
class LoginCodeView(StepView):
    """Étape `totp` : code de l'application ou code de secours."""

    serializer_class = LoginCodeSerializer

    @extend_schema(request=LoginCodeSerializer, responses={200: LoginStepSerializer, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        serializer = LoginCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = login.expect(request, Step.TOTP)
        with login.counting_failures(request, user):
            method = services.verify_second_factor(user, serializer.validated_data["code"])
        response = Response({"step": login.second_factor_passed(request, user, method)})
        # Jamais d'appareil de confiance pour la console : le code y est toujours demandé.
        if serializer.validated_data["trust_device"] and not is_console_host(request.get_host()):
            login.trust_device(response, user)
        return response


@extend_schema(tags=["auth"])
class PasswordView(StepView):
    """Étape `new_password` (mot de passe provisoire : `new_password` seul), ou changement du
    mot de passe d'un compte connecté (`current_password` aussi ; les autres sessions sont
    fermées)."""

    serializer_class = PasswordSerializer

    @extend_schema(request=PasswordSerializer, responses={200: LoginStepSerializer, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        user = self.connected_or_pending(request, Step.NEW_PASSWORD)
        serializer = PasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data["new_password"]
        if not request.user.is_authenticated:
            services.change_password(user, new_password)
            return Response({"step": login.advance(request, user)})
        current = serializer.validated_data.get("current_password")
        if current is None:
            raise ValidationError({"current_password": [_REQUIRED]})
        with login.counting_failures(request, user):
            services.change_password(user, new_password, current_password=current)
        update_session_auth_hash(request, user)
        return Response({"step": Step.DONE})


@extend_schema(tags=["auth"])
class TotpSetupView(StepView):
    """Nouvelle clé TOTP à scanner (M1) : étape `totp_setup`, ou compte connecté (changer de
    téléphone : code actuel ou de secours exigé si elle est déjà activée). Rien n'est enregistré
    avant `activate`."""

    serializer_class = TotpSetupSerializer

    @extend_schema(request=TotpSetupSerializer, responses={200: TotpKeySerializer, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        serializer = TotpSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.connected_or_pending(request, Step.TOTP_SETUP)
        if request.user.is_authenticated and user.totp_enabled:
            code = serializer.validated_data.get("code")
            if not code:
                raise ValidationError({"code": [_REQUIRED]})
            with login.counting_failures(request, user):
                services.verify_second_factor(user, code)
        secret = totp.new_secret()
        login.start_totp_setup(request, secret)
        return Response(
            {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, user.phone)}
        )


@extend_schema(tags=["auth"])
class TotpActivateView(StepView):
    """Premier code de l'application : la double authentification est activée ; les 8 codes de
    secours sont renvoyés une seule fois."""

    serializer_class = CodeSerializer

    @extend_schema(request=CodeSerializer, responses={200: TotpActivatedSerializer, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.connected_or_pending(request, Step.TOTP_SETUP)
        secret = login.totp_setup_secret(request)
        codes = services.enable_totp(user, secret, serializer.validated_data["code"])
        login.end_totp_setup(request)
        if request.user.is_authenticated:
            request.session[MFA_SESSION_KEY] = True
            step = Step.DONE
        else:
            step = login.second_factor_passed(request, user, "totp")
        return Response({"step": step, "recovery_codes": codes})


@extend_schema(tags=["auth"])
class RecoveryCodesView(AuthView):
    """8 nouveaux codes de secours (code actuel ou de secours exigé) ; les anciens ne servent
    plus."""

    permission_classes = [IsAuthenticated]
    serializer_class = CodeSerializer

    @extend_schema(request=CodeSerializer, responses={200: RecoveryCodesSerializer, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with login.counting_failures(request, request.user):
            codes = services.regenerate_recovery_codes(
                request.user, serializer.validated_data["code"]
            )
        return Response({"recovery_codes": codes})


@extend_schema(tags=["auth"])
class TotpDisableView(AuthView):
    """Désactiver la double authentification : refusé si un rôle du compte l'exige."""

    permission_classes = [IsAuthenticated]
    serializer_class = CodeSerializer

    @extend_schema(request=CodeSerializer, responses={204: None, **STEP_ERRORS})
    def post(self, request: Request) -> Response:
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with login.counting_failures(request, request.user):
            services.disable_totp(request.user, serializer.validated_data["code"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["auth"])
class LogoutView(AuthView):
    """Déconnexion ; ferme aussi la session support en cours (notée dans le journal)."""

    @extend_schema(request=None, responses={204: None, 403: ErrorSerializer})
    def post(self, request: Request) -> Response:
        support.end(request)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["support"])
class SupportView(APIView):
    """Session support « en tant qu'école » (A3), à l'adresse de l'école : super-admin connecté
    avec la double authentification. Une heure au plus ; droits de l'école sauf la caisse ;
    ouverture, fermeture et chaque action notées dans le journal de l'école."""

    permission_classes = [IsAuthenticated]
    serializer_class = SupportStartSerializer

    @extend_schema(responses={200: SupportSessionSerializer, 404: ErrorSerializer})
    def get(self, request: Request) -> Response:
        """La session support en cours dans cette école."""
        session = support.current(request)
        if session is None:
            raise BusinessError(support.NO_SUPPORT_SESSION)
        return Response(SupportSessionSerializer(session).data)

    @extend_schema(
        request=SupportStartSerializer,
        responses={201: SupportSessionSerializer, 403: ErrorSerializer, 404: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        """Ouvrir la session support, avec son motif."""
        serializer = SupportStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = support.start(request, serializer.validated_data["reason"])
        return Response(SupportSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None, 404: ErrorSerializer})
    def delete(self, request: Request) -> Response:
        """Fermer la session support (bouton du bandeau)."""
        if not support.end(request):
            raise BusinessError(support.NO_SUPPORT_SESSION)
        return Response(status=status.HTTP_204_NO_CONTENT)


CONSOLE_ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("search", str, description="Noms, ou chiffres du téléphone."),
        ],
        responses={200: ConsoleAccountSerializer(many=True), **CONSOLE_ERRORS},
    ),
    retrieve=extend_schema(responses={200: ConsoleAccountDetailSerializer, **CONSOLE_ERRORS}),
)
class ConsoleAccountViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Comptes de toutes les écoles (5.4.1) : super-admin seulement, à l'adresse de la console.
    Chaque changement va dans le journal de la plateforme et dans celui de chaque école où la
    personne est active. Un compte ne se supprime jamais : on le désactive."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = ConsoleAccountSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        search = self.request.query_params.get("search", "") if self.action == "list" else ""
        return console.accounts(search)

    def list(self, request: Request) -> Response:
        page = self.paginate_queryset(self.get_queryset())
        context = {**self.get_serializer_context(), "families": console.families_of(page)}
        return self.get_paginated_response(
            ConsoleAccountSerializer(page, many=True, context=context).data
        )

    def _detail(self, user: User) -> Response:
        context = {**self.get_serializer_context(), "families": console.families_of([user])}
        return Response(ConsoleAccountDetailSerializer(user, context=context).data)

    def retrieve(self, request: Request, pk=None) -> Response:
        return self._detail(self.get_object())

    def _changed(self, user: User) -> Response:
        # Rôles, familles et journal relus après le changement.
        return self._detail(console.accounts().get(pk=user.pk))

    @extend_schema(
        request=ConsoleAccountSerializer,
        responses={200: ConsoleAccountDetailSerializer, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        """Noms, téléphone et accès (désactivé : plus de connexion nulle part)."""
        user = self.get_object()
        serializer = ConsoleAccountSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.support_update_account(user, actor=request.user, **serializer.validated_data)
        return self._changed(user)

    @extend_schema(
        request=None,
        responses={200: TemporaryPasswordSerializer, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=True, methods=["post"], url_path="new-password")
    def new_password(self, request: Request, pk=None) -> Response:
        """Mot de passe provisoire, renvoyé une seule fois ; pas pour un compte qui ne sert
        qu'au portail des parents (son école donne un nouveau code famille)."""
        user = self.get_object()
        services.ensure_console_can_change(user)
        password = services.support_set_temporary_password(user, actor=request.user)
        return Response({"temporary_password": password})

    @extend_schema(
        request=None,
        responses={200: ConsoleAccountDetailSerializer, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=True, methods=["post"], url_path="reset-totp")
    def reset_totp(self, request: Request, pk=None) -> Response:
        """Téléphone perdu : la double authentification se réactive à la prochaine connexion si
        un rôle de la personne l'exige."""
        user = self.get_object()
        services.ensure_console_can_change(user)
        services.support_reset_totp(user, actor=request.user)
        return self._changed(user)


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("search", str, description="Nom ou code de l'école.")],
        responses={200: ConsoleSupportSessionSerializer(many=True), **CONSOLE_ERRORS},
    )
)
class ConsoleSupportSessionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Sessions support de toutes les écoles (5.4.2), ouvertes et passées, la plus récente
    d'abord : super-admin seulement, à l'adresse de la console."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = ConsoleSupportSessionSerializer

    def get_queryset(self):
        return support.sessions(self.request.query_params.get("search", ""))
