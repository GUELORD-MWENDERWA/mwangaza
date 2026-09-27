"""API des élèves, familles et inscriptions (D2-D4) : `students.view` pour lire,
`students.edit` pour écrire, vérifiés par le serveur sur chaque requête."""

from pathlib import Path

from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, HttpResponse
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.roles import STUDENTS_EDIT, STUDENTS_IMPORT, STUDENTS_VIEW
from apps.accounts.views import SchoolViewSet
from apps.audit.models import AuditLog
from apps.core.errors import ApiError, ErrorSerializer
from apps.schools.organisation import current_year
from apps.students import imports, services
from apps.students.models import Enrollment, Family, Guardian, Student, StudentImport
from apps.students.photos import CONTENT_TYPES
from apps.students.serializers import (
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
    FamilyDetailSerializer,
    FamilyFilterSerializer,
    FamilyWriteSerializer,
    ImportLineFilterSerializer,
    ImportLineSerializer,
    PhotoUploadSerializer,
    StudentFilterSerializer,
    StudentHistorySerializer,
    StudentImportCreateSerializer,
    StudentImportSerializer,
    StudentImportUpdateSerializer,
    StudentListSerializer,
    StudentSerializer,
    StudentWriteSerializer,
)

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, **ERRORS}
_CLASS = ("class_group__level", "class_group__track", "academic_year")
NO_PHOTO = ApiError("no_photo", _("This student has no photo."), 404)


class StudentsViewSet(SchoolViewSet):
    http_method_names = ["get", "post", "patch", "head", "options"]

    @property
    def required_permission(self) -> str:
        return STUDENTS_VIEW if self.request.method in SAFE_METHODS else STUDENTS_EDIT


def _words(text: str, *fields: str) -> Q:
    """Chaque mot dans un des champs, sans accents ni casse (« elie » trouve « Élie »)."""
    condition = Q()
    for word in text.split():
        match = Q()
        for field in fields:
            match |= Q(**{f"{field}__unaccent__icontains": word})
        condition &= match
    return condition


@extend_schema_view(
    list=extend_schema(
        parameters=[StudentFilterSerializer], responses={200: StudentListSerializer}
    ),
    retrieve=extend_schema(responses={200: StudentSerializer, **ERRORS}),
)
@extend_schema(tags=["students"])
class StudentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, StudentsViewSet):
    """Élèves de l'école (D2) : liste paginée avec recherche, fiche, création, modification,
    photo, historique."""

    http_method_names = [*StudentsViewSet.http_method_names, "delete"]

    def get_serializer_class(self):
        if self.request.method in {"POST", "PATCH"}:
            return StudentWriteSerializer
        return StudentListSerializer if self.action == "list" else StudentSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Student.all_schools.none()
        queryset = Student.objects.select_related("family")
        if self.action == "list":
            return self._filter(queryset.prefetch_related("family__guardians"))
        return queryset.prefetch_related(
            "family__guardians",
            Prefetch("enrollments", queryset=Enrollment.objects.select_related(*_CLASS)),
        )

    def _filter(self, queryset):
        params = StudentFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        group = data.get("class_group")
        year = group.academic_year if group else data.get("academic_year") or current_year()
        if data.get("search"):
            search = data["search"].strip()
            queryset = queryset.filter(
                _words(search, "last_name", "middle_name", "first_name", "matricule")
                | Q(family__code__iexact=search)
            )
        year_enrollments = Enrollment.objects.filter(academic_year=year)
        enrollments = year_enrollments
        if group:
            enrollments = enrollments.filter(class_group=group)
        if data.get("track"):
            enrollments = enrollments.filter(class_group__track=data["track"])
        status_filter = data.get("status")
        if status_filter == "active":
            enrollments = enrollments.filter(status=Enrollment.Status.ACTIVE)
        elif status_filter == "left":
            enrollments = enrollments.exclude(status=Enrollment.Status.ACTIVE)
        if enrollments is not year_enrollments:
            queryset = queryset.filter(pk__in=enrollments.values("student"))
        if status_filter == "not_enrolled":
            queryset = queryset.exclude(pk__in=year_enrollments.values("student"))
        return queryset.prefetch_related(
            Prefetch(
                "enrollments",
                queryset=Enrollment.objects.filter(academic_year=year).select_related(*_CLASS),
                to_attr="year_enrollments",
            )
        )

    def _student(self, student: Student, status_code=status.HTTP_200_OK) -> Response:
        student = self.get_queryset().get(pk=student.pk)
        return Response(StudentSerializer(student).data, status=status_code)

    @extend_schema(
        request=StudentWriteSerializer,
        responses={200: StudentSerializer, 201: StudentSerializer, **WRITE_ERRORS},
    )
    def create(self, request: Request) -> Response:
        """Élève avec une famille existante (`family`) ou nouvelle (`guardians`). Même nom et
        même date de naissance qu'un autre élève : 409 `possible_duplicate` avec `duplicates` (id,
        noms, matricule : lien vers leur fiche), à renvoyer avec `allow_duplicate` après
        confirmation. Même `id` renvoyé : 200 avec l'élève déjà créé."""
        serializer = StudentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("matricule", None)
        student, created = services.create_student(
            actor=request.user, student_id=data.pop("id", None), **data
        )
        return self._student(student, status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(
        request=StudentWriteSerializer, responses={200: StudentSerializer, **WRITE_ERRORS}
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        student = self.get_object()
        serializer = StudentWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        for ignored in ("id", "guardians", "allow_duplicate"):
            data.pop(ignored, None)
        services.update_student(student, actor=request.user, **data)
        return self._student(student)

    @extend_schema(
        methods=["GET"],
        request=None,
        responses={
            (200, "image/*"): OpenApiResponse(OpenApiTypes.BINARY, description="PNG ou JPEG."),
            **ERRORS,
        },
    )
    @extend_schema(
        methods=["POST"],
        request={"multipart/form-data": PhotoUploadSerializer},
        responses={200: StudentSerializer, **WRITE_ERRORS},
    )
    @extend_schema(methods=["DELETE"], request=None, responses={200: StudentSerializer, **ERRORS})
    @action(
        detail=True,
        methods=["get", "post", "delete"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def photo(self, request: Request, pk=None):
        """Photo de l'élève (M9), jamais publique : lue avec `students.view`, changée ou
        retirée avec `students.edit`."""
        student = self.get_object()
        if request.method == "POST":
            serializer = PhotoUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            photo = serializer.validated_data["photo"]
            services.set_photo(student, photo, actor=request.user)
            return self._student(student)
        if request.method == "DELETE":
            services.set_photo(student, None, actor=request.user)
            return self._student(student)
        if not student.photo:
            return Response(NO_PHOTO.body(), status=NO_PHOTO.status)
        try:
            file = student.photo.open("rb")
        except FileNotFoundError:
            return Response(NO_PHOTO.body(), status=NO_PHOTO.status)
        kind = Path(student.photo.name).suffix.removeprefix(".")
        response = FileResponse(file, content_type=CONTENT_TYPES.get(kind, "image/jpeg"))
        response["X-Content-Type-Options"] = "nosniff"
        # L'adresse donnée par l'API change avec chaque photo ; jamais dans un cache partagé.
        response["Cache-Control"] = "private, max-age=86400"
        return response

    @extend_schema(request=None, responses={200: StudentHistorySerializer(many=True), **ERRORS})
    @action(detail=True, methods=["get"])
    def history(self, request: Request, pk=None) -> Response:
        """Ce qui s'est passé pour l'élève (M9, Historique) : lui, ses inscriptions et sa
        famille, le plus récent d'abord. Paiements : avec la caisse (3.x)."""
        student = self.get_object()
        entities = [student.pk, student.family_id, *(e.pk for e in student.enrollments.all())]
        logs = (
            AuditLog.objects.filter(entity_id__in=entities)
            .select_related("actor")
            .order_by("-created_at", "-id")
        )
        page = self.paginate_queryset(logs)
        return self.get_paginated_response(StudentHistorySerializer(page, many=True).data)


@extend_schema_view(
    list=extend_schema(
        parameters=[FamilyFilterSerializer], responses={200: FamilyDetailSerializer}
    ),
    retrieve=extend_schema(responses={200: FamilyDetailSerializer, **ERRORS}),
)
@extend_schema(tags=["students"])
class FamilyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, StudentsViewSet):
    """Familles et tuteurs (D4) : recherche pour relier un élève, création, tuteurs remplacés
    d'un seul envoi."""

    def get_serializer_class(self):
        if self.request.method in {"POST", "PATCH"}:
            return FamilyWriteSerializer
        return FamilyDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Family.all_schools.none()
        year_enrollments = Enrollment.objects.filter(academic_year=current_year()).select_related(
            *_CLASS
        )
        queryset = (
            Family.objects.annotate(student_count=Count("students"))
            .prefetch_related(
                "guardians",
                Prefetch(
                    "students",
                    queryset=Student.objects.prefetch_related(
                        Prefetch("enrollments", year_enrollments, to_attr="year_enrollments")
                    ),
                ),
            )
            .order_by("code")
        )
        if self.action == "list":
            params = FamilyFilterSerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            search = params.validated_data.get("search", "").strip()
            if search:
                # Téléphone : seulement une saisie faite de chiffres (un code famille en a aussi).
                digits = search.replace(" ", "").removeprefix("+").removeprefix("0")
                phone = len(digits) >= 4 and digits.isdigit()
                condition = Q(code__iexact=search) | Q(
                    pk__in=Guardian.objects.filter(
                        _words(search, "full_name")
                        | (Q(phone__contains=digits) if phone else Q(pk=None))
                    ).values("family")
                )
                queryset = queryset.filter(condition)
        return queryset

    def _family(self, family: Family, status_code=status.HTTP_200_OK) -> Response:
        return Response(
            FamilyDetailSerializer(self.get_queryset().get(pk=family.pk)).data, status=status_code
        )

    @extend_schema(
        request=FamilyWriteSerializer, responses={201: FamilyDetailSerializer, **WRITE_ERRORS}
    )
    def create(self, request: Request) -> Response:
        serializer = FamilyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family = services.create_family(actor=request.user, **serializer.validated_data)
        return self._family(family, status.HTTP_201_CREATED)

    @extend_schema(
        request=FamilyWriteSerializer, responses={200: FamilyDetailSerializer, **WRITE_ERRORS}
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        family = self.get_object()
        serializer = FamilyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_family(family, actor=request.user, **serializer.validated_data)
        return self._family(family)


@extend_schema(tags=["students"])
class EnrollmentViewSet(StudentsViewSet):
    """Inscriptions (D3) : inscrire un élève dans une classe (matricule donné à la première),
    changer de classe dans l'année, noter un départ."""

    serializer_class = EnrollmentSerializer

    def get_serializer_class(self):
        return {"POST": EnrollmentCreateSerializer, "PATCH": EnrollmentUpdateSerializer}.get(
            self.request.method, EnrollmentSerializer
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Enrollment.all_schools.none()
        return Enrollment.objects.select_related("student", *_CLASS)

    def _enrollment(self, enrollment: Enrollment, status_code=status.HTTP_200_OK) -> Response:
        enrollment = self.get_queryset().get(pk=enrollment.pk)
        return Response(EnrollmentSerializer(enrollment).data, status=status_code)

    @extend_schema(
        request=EnrollmentCreateSerializer,
        responses={200: EnrollmentSerializer, 201: EnrollmentSerializer, **WRITE_ERRORS},
    )
    def create(self, request: Request) -> Response:
        """Même `id` renvoyé : 200 avec l'inscription déjà créée."""
        serializer = EnrollmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        enrollment, created = services.enroll(
            data.pop("student"), actor=request.user, enrollment_id=data.pop("id", None), **data
        )
        return self._enrollment(
            enrollment, status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @extend_schema(
        request=EnrollmentUpdateSerializer, responses={200: EnrollmentSerializer, **WRITE_ERRORS}
    )
    def partial_update(self, request: Request, pk=None) -> Response:
        enrollment = self.get_object()
        serializer = EnrollmentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_enrollment(enrollment, actor=request.user, **serializer.validated_data)
        return self._enrollment(enrollment)


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NO_CURRENT_YEAR = _("No current school year: choose one.")


def _xlsx(content: bytes, name: str) -> HttpResponse:
    response = HttpResponse(content, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


XLSX_RESPONSE = {(200, XLSX): OpenApiResponse(OpenApiTypes.BINARY, description="Classeur Excel.")}


@extend_schema_view(
    retrieve=extend_schema(responses={200: StudentImportSerializer, **ERRORS}),
    create=extend_schema(
        request={"multipart/form-data": StudentImportCreateSerializer},
        responses={201: StudentImportSerializer, **WRITE_ERRORS},
    ),
    partial_update=extend_schema(
        request=StudentImportUpdateSerializer,
        responses={200: StudentImportSerializer, **WRITE_ERRORS},
    ),
)
@extend_schema(tags=["students"])
class StudentImportViewSet(mixins.RetrieveModelMixin, SchoolViewSet):
    """Import d'une liste d'élèves (D1) : envoi du fichier (vérifié aussitôt, rien n'est créé),
    colonnes et classes choisies à la main, lignes vérifiées, puis import en tâche de fond."""

    required_permission = STUDENTS_IMPORT
    http_method_names = ["get", "post", "patch", "head", "options"]
    serializer_class = StudentImportSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudentImport.all_schools.none()
        queryset = StudentImport.objects.all()
        # Les lignes du fichier ne servent qu'à vérifier de nouveau et au rapport.
        if self.action in {"retrieve", "lines", "confirm"}:
            queryset = queryset.defer("rows")
        return queryset

    def create(self, request: Request) -> Response:
        serializer = StudentImportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data.get("academic_year") or current_year()
        if year is None:
            raise ValidationError({"academic_year": [NO_CURRENT_YEAR]})
        imp = imports.create_import(
            actor=request.user, file=serializer.validated_data["file"], academic_year=year
        )
        return Response(StudentImportSerializer(imp).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, pk=None) -> Response:
        imp = self.get_object()
        serializer = StudentImportUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        imp = imports.update_import(imp, **serializer.validated_data)
        return Response(StudentImportSerializer(imp).data)

    @extend_schema(
        parameters=[ImportLineFilterSerializer],
        responses={200: ImportLineSerializer(many=True), **ERRORS},
    )
    @action(detail=True)
    def lines(self, request: Request, pk=None) -> Response:
        """Lignes vérifiées, dans l'ordre du fichier (aperçu)."""
        imp = self.get_object()
        filters = ImportLineFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        lines = imp.report.get("lines", [])
        if filters.validated_data["problems"]:
            lines = [line for line in lines if line["status"] != "ready"]
        page = self.paginate_queryset(lines)
        return self.get_paginated_response(ImportLineSerializer(page, many=True).data)

    @extend_schema(request=None, responses={202: StudentImportSerializer, **WRITE_ERRORS})
    @action(detail=True, methods=["post"])
    def confirm(self, request: Request, pk=None) -> Response:
        """Importe les lignes prêtes et en avertissement, en tâche de fond : suivre `status`."""
        imp = imports.confirm(self.get_object(), actor=request.user)
        imp.refresh_from_db()
        return Response(StudentImportSerializer(imp).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses={**XLSX_RESPONSE, **ERRORS})
    @action(detail=True)
    def report(self, request: Request, pk=None) -> HttpResponse:
        """Lignes à reprendre, avec les colonnes du fichier et leurs problèmes."""
        imp = self.get_object()
        name = _("import-report")
        return _xlsx(imports.report_workbook(imp), f"{name}.xlsx")

    @extend_schema(responses={**XLSX_RESPONSE, **ERRORS})
    @action(detail=False)
    def template(self, request: Request) -> HttpResponse:
        """Modèle à remplir : une colonne par champ, titres reconnus à l'import."""
        name = _("students-template")
        return _xlsx(imports.template_workbook(), f"{name}.xlsx")
