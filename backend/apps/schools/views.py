from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import CLASSES_MANAGE, SCHOOL_CONFIGURE
from apps.accounts.views import SchoolViewSet
from apps.core.errors import SCHOOL_NOT_FOUND, ApiError, ErrorSerializer
from apps.schools import organisation, services
from apps.schools.logos import CONTENT_TYPES
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
    CurrentSchoolSerializer,
    LevelReorderSerializer,
    LevelSerializer,
    LevelUpdateSerializer,
    LogoUploadSerializer,
    MatriculeFormatInputSerializer,
    MatriculeFormatSerializer,
    PersonSerializer,
    SchoolSettingsSerializer,
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


@require_GET
def school_logo(request: HttpRequest) -> HttpResponse:
    """Logo de l'école de l'adresse (public : écran de connexion). Hors de l'API typée : c'est
    une image. Un SVG ne peut rien exécuter, même ouvert seul dans le navigateur."""
    school = request.school
    if school is None:
        return JsonResponse(SCHOOL_NOT_FOUND.body(), status=SCHOOL_NOT_FOUND.status)
    if not school.logo:
        return JsonResponse(NO_LOGO.body(), status=NO_LOGO.status)
    try:
        file = school.logo.open("rb")
    except FileNotFoundError:
        return JsonResponse(NO_LOGO.body(), status=NO_LOGO.status)
    kind = Path(school.logo.name).suffix.removeprefix(".")
    response = FileResponse(file, content_type=CONTENT_TYPES.get(kind, "application/octet-stream"))
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    # L'adresse donnée par l'API change avec chaque logo.
    response["Cache-Control"] = "public, max-age=86400"
    return response


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
    """Logo de l'école (M5) : PNG, JPEG ou SVG, 1 Mo au plus."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = LogoUploadSerializer

    @extend_schema(
        request={"multipart/form-data": LogoUploadSerializer},
        responses={200: SchoolSettingsSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = LogoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = self.school()
        services.update_school(school, actor=request.user, logo=serializer.validated_data["logo"])
        return self.settings_response(school)

    @extend_schema(request=None, responses={200: SchoolSettingsSerializer, **ERRORS})
    def delete(self, request: Request) -> Response:
        school = self.school()
        services.update_school(school, actor=request.user, logo=None)
        return self.settings_response(school)


# Organisation scolaire (C1-C3) : droit `classes.manage`. Listes de configuration (des dizaines de
# lignes, jamais des milliers) : sans pagination.

CONFLICT = {409: ErrorSerializer}


class _OrganisationViewSet(SchoolViewSet):
    required_permission = CLASSES_MANAGE
    pagination_class = None
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
        année."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
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

    def _response(self, value: str) -> Response:
        return Response(
            {"matricule_format": value, "example": organisation.matricule_example(value)}
        )


@extend_schema(tags=["organisation"])
class MatriculeFormatView(_MatriculeView):
    """Format du matricule de l'école (C3) et « Prochain matricule »."""

    @extend_schema(responses={200: MatriculeFormatSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        school = School.objects.get(pk=request.school.pk)
        return self._response(school.matricule_format)

    @extend_schema(
        request=MatriculeFormatInputSerializer,
        responses={200: MatriculeFormatSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def patch(self, request: Request) -> Response:
        """Vaut pour les matricules donnés ensuite ; les anciens ne changent pas."""
        serializer = MatriculeFormatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = organisation.set_matricule_format(
            serializer.validated_data["matricule_format"], actor=request.user
        )
        return self._response(school.matricule_format)


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
