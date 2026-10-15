from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import courses, grades, official
from apps.academics.models import Course
from apps.academics.serializers import (
    CoursesCopiedSerializer,
    CoursesCopySerializer,
    CourseSerializer,
    CoursesUpdateSerializer,
    GradingFilterSerializer,
    GradingSerializer,
    OfficialGridSerializer,
    SheetSerializer,
    SheetUpdateSerializer,
    TeachingLoadsFilterSerializer,
    TeachingLoadsSerializer,
)
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import COURSES_CONFIGURE, GRADES_ENTER, GRADES_ENTER_ANY
from apps.core.errors import ErrorSerializer
from apps.schools import organisation
from apps.schools.models import ClassGroup, Term
from apps.schools.serializers import term_tree

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
# Cours sans enseignant renvoyés en entier : les autres se voient classe par classe (une école de
# 800 élèves en a des centaines en début d'année ; la liste sert aussi à l'écran des cours).
UNASSIGNED_LISTED = 20


class _CoursesView(APIView):
    """Module `academics`, droit `courses.configure` (8.1) ; en ligne seulement."""

    permission_classes = [HasSchoolPermission]
    required_permission = COURSES_CONFIGURE
    required_module = "academics"

    def group(self, pk) -> ClassGroup:
        # Manager de l'école de l'adresse : une classe d'une autre école est introuvable.
        return get_object_or_404(ClassGroup.objects.select_related("level", "track"), pk=pk)


@extend_schema(tags=["courses"])
class ClassCoursesView(_CoursesView):
    serializer_class = CoursesUpdateSerializer

    @extend_schema(responses={200: CourseSerializer(many=True), **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Grille de cours de la classe, dans l'ordre du bulletin."""
        return Response(CourseSerializer(courses.courses_of(self.group(pk)), many=True).data)

    @extend_schema(
        request=CoursesUpdateSerializer,
        responses={
            200: CourseSerializer(many=True),
            400: ErrorSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def put(self, request: Request, pk) -> Response:
        """Toute la grille d'un seul envoi : cours gardés (`id`), ajoutés, modifiés, retirés."""
        group = self.group(pk)
        serializer = CoursesUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        courses.set_courses(group, serializer.items(), actor=request.user)
        return Response(CourseSerializer(courses.courses_of(group), many=True).data)


@extend_schema(tags=["courses"])
class ClassCoursesCopyView(_CoursesView):
    serializer_class = CoursesCopySerializer

    @extend_schema(
        request=CoursesCopySerializer,
        responses={
            200: CoursesCopiedSerializer,
            400: ErrorSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def post(self, request: Request, pk) -> Response:
        """Donne la grille de la classe à d'autres classes de l'école (de cette année ou d'une
        autre) : un cours du même nom garde son enseignant ; les autres cours sont retirés."""
        source = self.group(pk)
        serializer = CoursesCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        copied = courses.copy_courses(
            source, serializer.validated_data["class_groups"], actor=request.user
        )
        return Response({"copied": copied})


@extend_schema(tags=["courses"])
class OfficialGridsView(_CoursesView):
    @extend_schema(responses={200: OfficialGridSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Grilles officielles qui pré-remplissent celle d'une classe (formulaires de bulletin
        IGE/P.S, barème Électronique) ; l'école ajuste avant d'enregistrer."""
        return Response(OfficialGridSerializer(official.GRIDS, many=True).data)


@extend_schema(tags=["courses"])
class TeachingLoadsView(_CoursesView):
    @extend_schema(
        parameters=[TeachingLoadsFilterSerializer],
        responses={200: TeachingLoadsSerializer, **ERRORS},
    )
    def get(self, request: Request) -> Response:
        """Charge horaire de chaque membre du personnel actif dans l'année (heures par semaine
        de ses cours), et les cours sans enseignant. Sert aussi de liste des enseignants
        possibles : tout le personnel, quel que soit son rôle."""
        params = TeachingLoadsFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        year = params.validated_data.get("academic_year") or organisation.current_year()
        if year:
            loads, unassigned = courses.teaching_loads(year)
        else:
            loads, unassigned = [courses.Load(user) for user in courses.active_staff()], []
        data = {
            "loads": loads,
            "unassigned": unassigned[:UNASSIGNED_LISTED],
            "unassigned_count": len(unassigned),
            "unassigned_hours": sum(course.weekly_hours or 0 for course in unassigned),
        }
        return Response(TeachingLoadsSerializer(data).data)


class _GradesView(APIView):
    """Module `academics`, droit `grades.enter` (ses cours, sa classe de titulaire) ou
    `grades.enter_any` (toutes les classes) (8.2.1) ; en ligne (hors ligne : 8.2.3)."""

    permission_classes = [HasSchoolPermission]
    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY)
    required_module = "academics"

    def gradable(self):
        return grades.gradable_courses(self.request.user, school_access(self.request).permissions)


@extend_schema(tags=["grades"])
class GradingView(_GradesView):
    @extend_schema(
        parameters=[GradingFilterSerializer], responses={200: GradingSerializer, **ERRORS}
    )
    def get(self, request: Request) -> Response:
        """Ce que le compte peut noter dans l'année : son découpage (périodes, examens) et, par
        classe, les cours qu'il donne, ceux de la classe dont il est titulaire, ou tous."""
        params = GradingFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        year = params.validated_data.get("academic_year") or organisation.current_year()
        if year is None:
            return Response({"academic_year": None, "terms": [], "classes": []})
        listed = (
            self.gradable()
            .filter(class_group__academic_year=year)
            .select_related("class_group__level", "class_group__track")
            .order_by(
                "class_group__level__order",
                "class_group__level__name",
                "class_group__track__name",
                "class_group__section",
                "order",
            )
        )
        classes: dict = {}
        for course in listed:
            group = course.class_group
            entry = classes.setdefault(
                group.pk, {"id": group.pk, "name": group.name, "courses": []}
            )
            entry["courses"].append(course)
        data = {
            "academic_year": year.pk,
            "terms": term_tree(year),
            "classes": list(classes.values()),
        }
        return Response(GradingSerializer(data).data)


@extend_schema(tags=["grades"])
class GradeSheetView(_GradesView):
    serializer_class = SheetUpdateSerializer

    def objects(self, pk, term_pk) -> tuple[Course, Term]:
        # Manager de l'école de l'adresse : un cours ou une période d'une autre école est
        # introuvable ; un cours de l'école que le compte ne note pas : 403.
        course = get_object_or_404(
            Course.objects.select_related("class_group__level", "class_group__track"), pk=pk
        )
        if not self.gradable().filter(pk=course.pk).exists():
            raise PermissionDenied(
                _("You do not enter the grades of this course."), code="not_your_course"
            )
        return course, get_object_or_404(Term.objects.select_related("parent"), pk=term_pk)

    @extend_schema(responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS})
    def get(self, request: Request, pk, term) -> Response:
        """Feuille de notes du cours dans une période ou des examens : évaluations, élèves de la
        classe, notes, note de la période."""
        return Response(SheetSerializer(grades.sheet(*self.objects(pk, term))).data)

    @extend_schema(
        request=SheetUpdateSerializer,
        responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request, pk, term) -> Response:
        """Enregistre la feuille d'un seul envoi : évaluations ajoutées, modifiées ou retirées,
        cases changées ; renvoie la feuille à jour."""
        course, period = self.objects(pk, term)
        serializer = SheetUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved = grades.save_sheet(course, period, actor=request.user, **serializer.inputs())
        return Response(SheetSerializer(saved).data)
