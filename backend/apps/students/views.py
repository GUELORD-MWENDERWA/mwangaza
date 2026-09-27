"""API des élèves, familles et inscriptions (D2-D4) : `students.view` pour lire,
`students.edit` pour écrire, vérifiés par le serveur sur chaque requête."""

from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.roles import STUDENTS_EDIT, STUDENTS_VIEW
from apps.accounts.views import SchoolViewSet
from apps.core.errors import ErrorSerializer
from apps.schools.organisation import current_year
from apps.students import services
from apps.students.models import Enrollment, Family, Guardian, Student
from apps.students.serializers import (
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
    FamilyDetailSerializer,
    FamilyFilterSerializer,
    FamilyWriteSerializer,
    StudentFilterSerializer,
    StudentListSerializer,
    StudentSerializer,
    StudentWriteSerializer,
)

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, **ERRORS}
_CLASS = ("class_group__level", "class_group__track", "academic_year")


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
    """Élèves de l'école (D2) : liste paginée avec recherche, fiche, création, modification."""

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
        même date de naissance qu'un autre élève : 409 `possible_duplicate`, à renvoyer avec
        `allow_duplicate` après confirmation. Même `id` renvoyé : 200 avec l'élève déjà créé."""
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
                digits = "".join(char for char in search if char.isdigit())
                condition = Q(code__iexact=search) | Q(
                    pk__in=Guardian.objects.filter(
                        _words(search, "full_name")
                        | (Q(phone__contains=digits.removeprefix("0")) if digits else Q(pk=None))
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
