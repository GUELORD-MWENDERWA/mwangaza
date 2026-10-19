from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import platform_roles as team
from apps.accounts.models import Membership
from apps.accounts.permissions import (
    HasPlatformPermission,
    HasSchoolAccess,
    HasSchoolPermission,
    ensure_platform_permission,
    school_access,
)
from apps.accounts.roles import (
    ANNOUNCEMENTS_PUBLISH,
    CLASSES_MANAGE,
    COURSES_CONFIGURE,
    FEES_READ,
    FINANCE_CONFIGURE_FEES,
    SCHOOL_CONFIGURE,
    STUDENTS_VIEW,
)
from apps.accounts.views import SchoolViewSet
from apps.core.documents import PRINT_RESPONSE, render
from apps.core.errors import SCHOOL_NOT_FOUND, ApiError, ErrorSerializer
from apps.core.http import serve_image
from apps.schools import console, demonstrations, organisation, services, setup
from apps.schools.console_serializers import (
    AccessSheetQuerySerializer,
    ConsoleSchoolCreatedSerializer,
    ConsoleSchoolCreateSerializer,
    ConsoleSchoolDetailSerializer,
    ConsoleSchoolSerializer,
    DemonstrationCreateSerializer,
    SchoolDeleteSerializer,
    SchoolStopSerializer,
)
from apps.schools.matricule import validate_matricule_format
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from apps.schools.serializers import (
    AcademicYearCreateSerializer,
    AcademicYearSerializer,
    AcademicYearUpdateSerializer,
    ClassGroupCreateSerializer,
    ClassGroupFilterSerializer,
    ClassGroupSerializer,
    ClassGroupUpdateSerializer,
    ConsoleDashboardSerializer,
    CurrentSchoolSerializer,
    LevelReorderSerializer,
    LevelSerializer,
    LevelUpdateSerializer,
    LogoUploadSerializer,
    MatriculeFormatInputSerializer,
    MatriculeFormatSerializer,
    MatriculeSettingsInputSerializer,
    MatriculeSettingsSerializer,
    PersonSerializer,
    SchoolSettingsSerializer,
    SetupSerializer,
    SignatureUploadSerializer,
    TermsUpdateSerializer,
    TrackSerializer,
    TrackUpdateSerializer,
)

NO_LOGO = ApiError("no_logo", _("This school has no logo."), 404)
ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}


@extend_schema(responses={200: CurrentSchoolSerializer, 404: ErrorSerializer}, tags=["schools"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def current_school(request: Request) -> Response:
    """École du sous-domaine (public : l'écran de connexion affiche son nom, sa couleur, son
    logo)."""
    if request.school is None:
        return Response(SCHOOL_NOT_FOUND.body(), status=SCHOOL_NOT_FOUND.status)
    return Response(CurrentSchoolSerializer(request.school).data)


def _serve_logo(request: HttpRequest, field: str) -> HttpResponse:
    school = request.school
    if school is None:
        return JsonResponse(SCHOOL_NOT_FOUND.body(), status=SCHOOL_NOT_FOUND.status)
    response = serve_image(getattr(school, field))
    return response or JsonResponse(NO_LOGO.body(), status=NO_LOGO.status)


@require_GET
def school_logo(request: HttpRequest) -> HttpResponse:
    """Logo de l'école de l'adresse (public : écran de connexion). Hors de l'API typée : c'est
    une image. Un SVG ne peut rien exécuter, même ouvert seul dans le navigateur."""
    return _serve_logo(request, "logo")


@require_GET
def school_logo_monochrome(request: HttpRequest) -> HttpResponse:
    """Logo noir et blanc de l'école de l'adresse (reçus thermiques), public comme le logo."""
    return _serve_logo(request, "logo_monochrome")


class _SchoolSettingsBase(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = SCHOOL_CONFIGURE

    def school(self) -> School:
        return School.objects.get(pk=self.request.school.pk)

    def settings_response(self, school: School) -> Response:
        return Response(SchoolSettingsSerializer(school).data)


@extend_schema(tags=["schools"])
class SchoolSettingsView(_SchoolSettingsBase):
    """Paramètres de l'école de l'adresse (M5) : nom, nom officiel, couleur (texte lisible
    vérifié, Q8), fuseau horaire, devises. Chaque changement va dans le journal de l'école."""

    serializer_class = SchoolSettingsSerializer

    @extend_schema(responses={200: SchoolSettingsSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        return self.settings_response(self.school())

    @extend_schema(
        request=SchoolSettingsSerializer,
        responses={200: SchoolSettingsSerializer, **ERRORS},
    )
    def patch(self, request: Request) -> Response:
        school = self.school()
        serializer = SchoolSettingsSerializer(school, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_school(school, actor=request.user, **serializer.validated_data)
        return self.settings_response(school)


@extend_schema(tags=["schools"])
class SchoolLogoView(_SchoolSettingsBase):
    """Logo de l'école (M5) : PNG ou JPEG, 1 Mo et 2 048 pixels de côté au plus, ré-encodé à
    l'envoi (S.4)."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = LogoUploadSerializer
    field = "logo"

    @extend_schema(
        request={"multipart/form-data": LogoUploadSerializer},
        responses={200: SchoolSettingsSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = LogoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = self.school()
        logo = serializer.validated_data["logo"]
        services.update_school(school, actor=request.user, **{self.field: logo})
        return self.settings_response(school)

    @extend_schema(request=None, responses={200: SchoolSettingsSerializer, **ERRORS})
    def delete(self, request: Request) -> Response:
        school = self.school()
        services.update_school(school, actor=request.user, **{self.field: None})
        return self.settings_response(school)


@extend_schema(tags=["schools"])
class SchoolMonochromeLogoView(SchoolLogoView):
    """Logo noir et blanc des reçus thermiques (M5) ; sans lui, le logo s'imprime en niveaux de
    gris. Mêmes règles que le logo."""

    field = "logo_monochrome"


NO_IMAGE = ApiError("no_image", _("No image."), 404)


def _private_image(file) -> HttpResponse:
    return serve_image(file, private=True) or JsonResponse(NO_IMAGE.body(), status=NO_IMAGE.status)


@extend_schema(exclude=True)
class SchoolSignatureImageView(APIView):
    """Cachet de l'école ou signature du chef (DOC.1), posés sur les reçus que la Gestion imprime :
    au seul personnel connecté de l'école, jamais public. Hors de l'API typée : c'est une image."""

    permission_classes = [HasSchoolAccess]
    field = "stamp"

    def get(self, request: Request) -> HttpResponse:
        return _private_image(getattr(request.school, self.field))


@extend_schema(exclude=True)
class MemberSignatureView(APIView):
    """Signature d'une personne de l'école (DOC.1) : celle du caissier sur un reçu réimprimé par
    un autre. Au seul personnel connecté de l'école ; la personne d'une autre école n'existe pas
    ici (404)."""

    permission_classes = [HasSchoolAccess]

    def get(self, request: Request, user_id) -> HttpResponse:
        membership = Membership.objects.filter(school=request.school, user_id=user_id).first()
        return _private_image(membership.signature if membership else None)


@extend_schema(tags=["schools"])
class SchoolStampView(_SchoolSettingsBase):
    """Cachet de l'école (DOC.1) : PNG ou JPEG, 1 Mo au plus, enregistré en PNG, le fond blanc
    rendu transparent. Au journal de l'école."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = SignatureUploadSerializer
    field = "stamp"

    @extend_schema(
        request={"multipart/form-data": SignatureUploadSerializer},
        responses={200: SchoolSettingsSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = SignatureUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = self.school()
        image = serializer.validated_data["image"]
        services.update_school(school, actor=request.user, **{self.field: image})
        return self.settings_response(school)

    @extend_schema(request=None, responses={200: SchoolSettingsSerializer, **ERRORS})
    def delete(self, request: Request) -> Response:
        school = self.school()
        services.update_school(school, actor=request.user, **{self.field: None})
        return self.settings_response(school)


@extend_schema(tags=["schools"])
class SchoolHeadSignatureView(SchoolStampView):
    """Signature du chef d'établissement (DOC.1), sous son nom et son titre. Mêmes règles que le
    cachet."""

    field = "head_signature"


# Organisation scolaire (C1-C3) : droit `classes.manage`. Listes de configuration (des dizaines de
# lignes, jamais des milliers) : sans pagination.

CONFLICT = {409: ErrorSerializer}


@extend_schema(tags=["schools"])
class SchoolSetupView(_SchoolSettingsBase):
    """Liste « Mise en route » d'une école neuve (C4) : chaque étape cochée d'après ce que
    l'école a déjà saisi, rien de gardé. Vide, sans rien lire, une fois terminée : `/api/school/`
    dit alors `setup_done` et le tableau de bord ne l'appelle plus."""

    @extend_schema(responses={200: SetupSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        return Response(SetupSerializer(setup.status(self.school())).data)


@extend_schema(tags=["schools"])
class SchoolSetupFinishView(_SchoolSettingsBase):
    """Le directeur termine la mise en route : la date est gardée sur l'école, une fois pour
    toutes. 409 `setup_incomplete` tant qu'une étape obligatoire manque."""

    @extend_schema(request=None, responses={200: SetupSerializer, **ERRORS, **CONFLICT})
    def post(self, request: Request) -> Response:
        return Response(SetupSerializer(setup.finish(self.school())).data)


class _OrganisationViewSet(SchoolViewSet):
    pagination_class = None
    # Années, niveaux, options et classes : lus aussi avec `students.view` (filtres de la liste
    # des élèves, inscription), les droits des frais (barèmes, E2) et `courses.configure` (cours
    # de chaque classe, 8.1) ; tout le reste demande `classes.manage`.
    shared_reads = False

    @property
    def required_permission(self) -> str | tuple[str, ...]:
        if self.shared_reads and self.action in {"list", "retrieve"}:
            return (
                CLASSES_MANAGE,
                STUDENTS_VIEW,
                ANNOUNCEMENTS_PUBLISH,
                COURSES_CONFIGURE,
                *FEES_READ,
            )
        return CLASSES_MANAGE

    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]


@extend_schema_view(
    list=extend_schema(responses={200: AcademicYearSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: AcademicYearSerializer, **ERRORS}),
    destroy=extend_schema(responses={204: None, **CONFLICT, **ERRORS}),
)
@extend_schema(tags=["organisation"])
class AcademicYearViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, _OrganisationViewSet
):
    """Années scolaires de l'école, la plus récente d'abord, avec leur découpage (C1)."""

    shared_reads = True

    serializer_class = AcademicYearSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AcademicYear.all_schools.none()
        return AcademicYear.objects.prefetch_related("terms")

    def get_serializer_class(self):
        return {
            "create": AcademicYearCreateSerializer,
            "partial_update": AcademicYearUpdateSerializer,
            "terms": TermsUpdateSerializer,
        }.get(self.action, AcademicYearSerializer)

    def _year(self, year: AcademicYear) -> Response:
        return Response(AcademicYearSerializer(self.get_queryset().get(pk=year.pk)).data)

    @extend_schema(
        request=AcademicYearCreateSerializer,
        responses={201: AcademicYearSerializer, 400: ErrorSerializer, **CONFLICT, **ERRORS},
    )
    def create(self, request: Request) -> Response:
        """Nouvelle année depuis un modèle de découpage, avec en option les classes d'une autre
        année, et ses barèmes (`copy_fees`, droit `finance.configure_fees` en plus)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permissions = school_access(request).permissions
        if serializer.validated_data["copy_fees"] and FINANCE_CONFIGURE_FEES not in permissions:
            raise PermissionDenied()
        year = organisation.create_year(actor=request.user, **serializer.validated_data)
        response = self._year(year)
        response.status_code = status.HTTP_201_CREATED
        return response

    @extend_schema(
        request=AcademicYearUpdateSerializer,
        responses={200: AcademicYearSerializer, 400: ErrorSerializer, **CONFLICT, **ERRORS},
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        year = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organisation.update_year(year, actor=request.user, **serializer.validated_data)
        return self._year(year)

    def perform_destroy(self, instance: AcademicYear) -> None:
        organisation.delete_year(instance, actor=self.request.user)

    @extend_schema(request=None, responses={200: AcademicYearSerializer, **ERRORS})
    @action(detail=True, methods=["post"], url_path="make-current")
    def make_current(self, request: Request, pk=None) -> Response:
        """Année en cours : celle des inscriptions et des écrans par défaut."""
        year = organisation.make_current(self.get_object(), actor=request.user)
        return self._year(year)

    @extend_schema(
        request=TermsUpdateSerializer,
        responses={200: AcademicYearSerializer, 400: ErrorSerializer, **CONFLICT, **ERRORS},
    )
    @action(detail=True, methods=["put"])
    def terms(self, request: Request, pk=None) -> Response:
        """Tout le découpage de l'année : noms, dates, éléments ajoutés ou retirés."""
        year = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organisation.set_terms(year, serializer.nodes(), actor=request.user)
        return self._year(year)


class _CrudViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    _OrganisationViewSet,
):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


@extend_schema_view(
    list=extend_schema(responses={200: LevelSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: LevelSerializer, **ERRORS}),
    create=extend_schema(responses={201: LevelSerializer, **CONFLICT, **ERRORS}),
    partial_update=extend_schema(
        request=LevelUpdateSerializer, responses={200: LevelSerializer, **CONFLICT, **ERRORS}
    ),
    destroy=extend_schema(responses={204: None, **CONFLICT, **ERRORS}),
)
@extend_schema(tags=["organisation"])
class LevelViewSet(_CrudViewSet):
    """Niveaux de l'école (« 7e EB », « 3e »), dans l'ordre choisi (C2)."""

    shared_reads = True

    serializer_class = LevelSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Level.all_schools.none()
        return Level.objects.all()

    def get_serializer_class(self):
        if self.action == "partial_update":
            return LevelUpdateSerializer
        if self.action == "reorder":
            return LevelReorderSerializer
        return LevelSerializer

    def perform_create(self, serializer):
        serializer.instance = organisation.create_level(
            actor=self.request.user, **serializer.validated_data
        )

    def partial_update(self, request: Request, pk=None) -> Response:
        level = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organisation.update_level(level, actor=request.user, **serializer.validated_data)
        return Response(LevelSerializer(level).data)

    def perform_destroy(self, instance: Level) -> None:
        organisation.delete_level(instance, actor=self.request.user)

    @extend_schema(
        request=LevelReorderSerializer,
        responses={200: LevelSerializer(many=True), 400: ErrorSerializer, **ERRORS},
    )
    @action(detail=False, methods=["post"])
    def reorder(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        levels = organisation.reorder_levels(serializer.validated_data["ids"], actor=request.user)
        return Response(LevelSerializer(levels, many=True).data)


@extend_schema_view(
    list=extend_schema(responses={200: TrackSerializer(many=True), **ERRORS}),
    retrieve=extend_schema(responses={200: TrackSerializer, **ERRORS}),
    create=extend_schema(responses={201: TrackSerializer, **CONFLICT, **ERRORS}),
    partial_update=extend_schema(
        request=TrackUpdateSerializer, responses={200: TrackSerializer, **CONFLICT, **ERRORS}
    ),
    destroy=extend_schema(responses={204: None, **CONFLICT, **ERRORS}),
)
@extend_schema(tags=["organisation"])
class TrackViewSet(_CrudViewSet):
    """Options des humanités (« Électricité », code `ELEC`) (C2)."""

    shared_reads = True

    serializer_class = TrackSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Track.all_schools.none()
        return Track.objects.all()

    def get_serializer_class(self):
        return TrackUpdateSerializer if self.action == "partial_update" else TrackSerializer

    def perform_create(self, serializer):
        serializer.instance = organisation.create_track(
            actor=self.request.user, **serializer.validated_data
        )

    def partial_update(self, request: Request, pk=None) -> Response:
        track = self.get_object()
        serializer = self.get_serializer(track, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        organisation.update_track(track, actor=request.user, **serializer.validated_data)
        return Response(TrackSerializer(track).data)

    def perform_destroy(self, instance: Track) -> None:
        organisation.delete_track(instance, actor=self.request.user)


@extend_schema_view(
    list=extend_schema(
        parameters=[ClassGroupFilterSerializer],
        responses={200: ClassGroupSerializer(many=True), **ERRORS},
    ),
    retrieve=extend_schema(responses={200: ClassGroupSerializer, **ERRORS}),
    create=extend_schema(
        request=ClassGroupCreateSerializer,
        responses={201: ClassGroupSerializer, 400: ErrorSerializer, **CONFLICT, **ERRORS},
    ),
    partial_update=extend_schema(
        request=ClassGroupUpdateSerializer,
        responses={200: ClassGroupSerializer, 400: ErrorSerializer, **CONFLICT, **ERRORS},
    ),
    destroy=extend_schema(responses={204: None, **CONFLICT, **ERRORS}),
)
@extend_schema(tags=["organisation"])
class ClassGroupViewSet(_CrudViewSet):
    """Classes d'une année (« 3e Électricité A ») : niveau, option, section, capacité, titulaire
    (C2). Supprimée seulement sans élève."""

    shared_reads = True

    serializer_class = ClassGroupSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ClassGroup.all_schools.none()
        active = Q(enrollments__status="active")
        queryset = ClassGroup.objects.select_related("level", "track", "homeroom_teacher").annotate(
            student_count=Count("enrollments", filter=active)
        )
        if self.action == "list":
            params = ClassGroupFilterSerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            year = params.validated_data.get("academic_year") or organisation.current_year()
            queryset = queryset.filter(academic_year=year)
        return queryset

    def get_serializer_class(self):
        return {
            "create": ClassGroupCreateSerializer,
            "partial_update": ClassGroupUpdateSerializer,
            "homeroom_candidates": PersonSerializer,
        }.get(self.action, ClassGroupSerializer)

    def _group(self, group: ClassGroup, status_code: int = status.HTTP_200_OK) -> Response:
        group = self.get_queryset().get(pk=group.pk)
        return Response(ClassGroupSerializer(group).data, status=status_code)

    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = organisation.create_class_group(actor=request.user, **serializer.validated_data)
        return self._group(group, status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk=None) -> Response:
        group = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organisation.update_class_group(group, actor=request.user, **serializer.validated_data)
        return self._group(group)

    def perform_destroy(self, instance: ClassGroup) -> None:
        organisation.delete_class_group(instance, actor=self.request.user)

    @extend_schema(responses={200: PersonSerializer(many=True), **ERRORS})
    @action(detail=False, methods=["get"], url_path="homeroom-candidates")
    def homeroom_candidates(self, request: Request) -> Response:
        """Titulaires possibles : le personnel actif de l'école."""
        return Response(PersonSerializer(organisation.homeroom_candidates(), many=True).data)


class _MatriculeView(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = CLASSES_MANAGE
    serializer_class = MatriculeFormatInputSerializer

    def _response(self, value: str, **settings) -> Response:
        return Response(
            {
                "matricule_format": value,
                **settings,
                "example": organisation.matricule_example(value),
            }
        )


@extend_schema(tags=["organisation"])
class MatriculeFormatView(_MatriculeView):
    """Format du matricule de l'école (C3), « Prochain matricule » et choix d'en attribuer un
    automatiquement (C5)."""

    def _settings(self, school: School) -> Response:
        return self._response(school.matricule_format, auto_matricule=school.auto_matricule)

    @extend_schema(responses={200: MatriculeSettingsSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        return self._settings(School.objects.get(pk=request.school.pk))

    @extend_schema(
        request=MatriculeSettingsInputSerializer,
        responses={200: MatriculeSettingsSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def patch(self, request: Request) -> Response:
        """Un seul des deux champs suffit. Vaut pour les inscriptions et les imports suivants ;
        les matricules déjà donnés ne changent pas."""
        serializer = MatriculeSettingsInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        school = organisation.set_matricule_format(
            data.get("matricule_format"), actor=request.user, automatic=data.get("auto_matricule")
        )
        return self._settings(school)


@extend_schema(tags=["organisation"])
class MatriculePreviewView(_MatriculeView):
    """Aperçu d'un format pendant la saisie, sans l'enregistrer."""

    @extend_schema(
        request=MatriculeFormatInputSerializer,
        responses={200: MatriculeFormatSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = MatriculeFormatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["matricule_format"].strip()
        try:
            validate_matricule_format(value)
        except DjangoValidationError as exc:
            raise DjangoValidationError({"matricule_format": exc}) from None
        return self._response(value)


@extend_schema(tags=["console"])
class ConsoleDashboardView(APIView):
    """Tableau de bord de la console de la plateforme (5.2) : toutes les écoles, super-admin
    seulement, à l'adresse de la console."""

    permission_classes = [HasPlatformPermission]
    platform_permission = team.SCHOOLS_VIEW

    @extend_schema(
        responses={200: ConsoleDashboardSerializer, 403: ErrorSerializer, 404: ErrorSerializer}
    )
    def get(self, request: Request) -> Response:
        return Response(ConsoleDashboardSerializer(console.dashboard()).data)


CONSOLE_ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


@extend_schema(tags=["console"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("search", str, description="Nom, nom officiel ou code."),
            OpenApiParameter("status", str, enum=School.Status.values),
            OpenApiParameter("environment", str, enum=School.Environment.values),
        ],
        responses={200: ConsoleSchoolSerializer(many=True), **CONSOLE_ERRORS},
    ),
    retrieve=extend_schema(responses={200: ConsoleSchoolDetailSerializer, **CONSOLE_ERRORS}),
)
class ConsoleSchoolViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Écoles de la plateforme (5.3) : équipe selon ses droits, à la console. Chaque
    changement va dans le journal de la plateforme (et, pour l'identité, dans celui de l'école).
    Un espace réel ne se supprime jamais : on le suspend ou on l'arrête ; un espace d'essai ou de
    démonstration se supprime (4.16).

    Droits (EQ.1) : un espace réel demande `platform.schools.*`, un espace d'essai ou de
    démonstration `platform.demos.manage` ; sans `platform.schools.view`, les espaces réels
    n'apparaissent pas (404)."""

    permission_classes = [HasPlatformPermission]
    platform_permission = (team.SCHOOLS_VIEW, team.DEMOS_MANAGE)
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        schools = console.schools()
        if getattr(self, "swagger_fake_view", False):
            return schools
        if team.SCHOOLS_VIEW not in self.request.user.platform_permissions:
            schools = schools.exclude(environment=School.Environment.LIVE)
        if self.action != "list":
            return schools
        params = self.request.query_params
        if search := params.get("search", "").strip():
            schools = schools.filter(
                Q(name__icontains=search)
                | Q(official_name__icontains=search)
                | Q(code__icontains=search)
            )
        if (state := params.get("status")) in School.Status.values:
            schools = schools.filter(status=state)
        if (kind := params.get("environment")) in School.Environment.values:
            schools = schools.filter(environment=kind)
        return schools

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ConsoleSchoolDetailSerializer
        return ConsoleSchoolSerializer

    def _detail(self, school: School) -> Response:
        return Response(ConsoleSchoolDetailSerializer(console.schools().get(pk=school.pk)).data)

    def _allowed(self, environment: str, live_right: str) -> None:
        """Espace réel : `live_right` ; essai ou démonstration : `platform.demos.manage`."""
        live = environment == School.Environment.LIVE
        ensure_platform_permission(self.request, live_right if live else team.DEMOS_MANAGE)

    def _object(self, live_right: str = team.SCHOOLS_MANAGE) -> School:
        school = self.get_object()
        self._allowed(school.environment, live_right)
        return school

    @extend_schema(
        request=ConsoleSchoolCreateSerializer,
        responses={201: ConsoleSchoolCreatedSerializer, **CONSOLE_ERRORS},
    )
    def create(self, request: Request) -> Response:
        """Nouvelle école avec son premier directeur. Nouveau numéro : mot de passe provisoire
        renvoyé une seule fois (pas de SMS en V1) ; numéro connu : ajouté sans nouveau mot de
        passe."""
        environment = request.data.get("environment") or School.Environment.LIVE
        self._allowed(environment, team.SCHOOLS_MANAGE)
        serializer = ConsoleSchoolCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        head = data.pop("head")
        director = services.Director(
            phone=head["phone"],
            **{
                name: head.get(name, "").strip()
                for name in ("last_name", "middle_name", "first_name")
            },
        )
        membership, password = services.create_school(
            School(**data), actor=request.user, director=director
        )
        created = {
            "school": console.schools().get(pk=membership.school_id),
            "head": membership.user,
            "temporary_password": password,
        }
        return Response(ConsoleSchoolCreatedSerializer(created).data, status=201)

    @extend_schema(
        request=ConsoleSchoolSerializer,
        responses={200: ConsoleSchoolDetailSerializer, **CONSOLE_ERRORS},
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        """Noms, adresse (l'ancienne cesse de marcher) et abonnement."""
        school = self._object()
        serializer = ConsoleSchoolSerializer(school, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.change_school(school, actor=request.user, **serializer.validated_data)
        return self._detail(school)

    @extend_schema(request=None, responses={200: ConsoleSchoolDetailSerializer, **CONSOLE_ERRORS})
    @action(detail=True, methods=["post"])
    def suspend(self, request: Request, pk=None) -> Response:
        """Plus personne ne se connecte à l'école ; rien n'est supprimé."""
        return self._detail(services.suspend(self._object(), actor=request.user))

    @extend_schema(
        request=SchoolStopSerializer,
        responses={200: ConsoleSchoolDetailSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk=None) -> Response:
        """Espace arrêté, avec un motif : plus personne n'y entre, les données restent."""
        school = self._object(team.SCHOOLS_STOP)
        serializer = SchoolStopSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = services.stop(school, actor=request.user, **serializer.validated_data)
        return self._detail(school)

    @extend_schema(request=None, responses={200: ConsoleSchoolDetailSerializer, **CONSOLE_ERRORS})
    @action(detail=True, methods=["post"])
    def reactivate(self, request: Request, pk=None) -> Response:
        """Suspendue ou arrêtée, de nouveau ouverte : en essai gratuit s'il n'est pas fini, sinon
        active."""
        return self._detail(services.reactivate(self._object(), actor=request.user))

    @extend_schema(
        request=SchoolDeleteSerializer,
        responses={204: None, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=True, methods=["post"], url_path="delete")
    def delete_space(self, request: Request, pk=None) -> Response:
        """Espace d'essai ou de démonstration supprimé avec toutes ses données, en tâche de
        fond ; refusé pour un espace réel. `confirm` : le code de l'espace. Déjà en cours : la
        suppression est relancée."""
        school = self._object(team.SCHOOLS_STOP)
        serializer = SchoolDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.delete_space(school, actor=request.user, **serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=DemonstrationCreateSerializer,
        responses={201: ConsoleSchoolDetailSerializer, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=False, methods=["post"])
    def demo(self, request: Request) -> Response:
        """Nouvel espace de démonstration (A6) : ouvert tout de suite, rempli de données fictives
        en tâche de fond (`demonstration` de la fiche : avancement). Refusé si la plateforme en a
        déjà son maximum, ou pendant qu'un autre espace se crée ou s'efface."""
        ensure_platform_permission(request, team.DEMOS_MANAGE)
        serializer = DemonstrationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = demonstrations.create(actor=request.user, **serializer.validated_data)
        detail = ConsoleSchoolDetailSerializer(console.schools().get(pk=school.pk))
        return Response(detail.data, status=201)

    @extend_schema(
        request=SchoolDeleteSerializer,
        responses={200: ConsoleSchoolDetailSerializer, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=True, methods=["post"])
    def reset(self, request: Request, pk=None) -> Response:
        """« Remettre à zéro » un espace de démonstration créé depuis la console : supprimé puis
        recréé (même adresse, mêmes numéros, nouveau mot de passe), en tâche de fond. `confirm` :
        le code de l'espace."""
        school = self._object(team.SCHOOLS_STOP)
        serializer = SchoolDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        demonstrations.reset(school, actor=request.user, **serializer.validated_data)
        return self._detail(school)

    @extend_schema(
        parameters=[AccessSheetQuerySerializer],
        responses={**PRINT_RESPONSE, 409: ErrorSerializer, **CONSOLE_ERRORS},
    )
    @action(detail=True, url_path="access-sheet")
    def access_sheet(self, request: Request, pk=None) -> HttpResponse:
        """Fiche d'accès d'un espace de démonstration prêt (A6), à remettre à un visiteur :
        adresses, mot de passe, un compte par rôle, parents du portail avec leur code famille."""
        school = self._object()
        params = AccessSheetQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        context = demonstrations.access_sheet(school)
        name = f"fiche-acces-{school.code}.pdf"
        return render("schools/access_sheet.html", context, params.validated_data["output"], name)
