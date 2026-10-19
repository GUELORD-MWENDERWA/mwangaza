"""API des examens de repêchage (8.4.1) : tableau de la classe (cours échoués, issue proposée) et
note de repêchage d'un cours, saisie et signée par son enseignant (ou `grades.enter_any`).
Seconde session (NB.6) : date de l'examen et convocations des élèves envoyés au repêchage."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import deliberation, report_cards, resits
from apps.academics.grades import gradable_courses
from apps.academics.models import Course, Deliberation
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE
from apps.core.documents import (
    PRINT_RESPONSE,
    PrintOptionsSerializer,
    print_options,
    render,
    school_header,
)
from apps.core.errors import ErrorSerializer
from apps.core.tenancy import require_current_school
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


class ResitCourseSerializer(serializers.Serializer):
    course = serializers.UUIDField(source="course.pk")
    course_name = serializers.CharField(source="course.name")
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, help_text="Année du cours.")
    eligible = serializers.BooleanField(help_text="Le cours ouvre un repêchage.")
    resit_percent = serializers.SerializerMethodField()
    signed_by = serializers.SerializerMethodField()
    passed = serializers.SerializerMethodField()
    can_enter = serializers.BooleanField()

    def get_resit_percent(self, row) -> str | None:
        return str(row.resit.percent) if row.resit else None

    def get_signed_by(self, row) -> str:
        return row.resit.signed_by.get_full_name() if row.resit else ""

    def get_passed(self, row) -> bool | None:
        return row.passed(self.context["rules"])


class StudentResitsSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(source="enrollment.pk")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    percent = serializers.DecimalField(
        max_digits=5, decimal_places=1, allow_null=True, help_text="Pourcentage de l'année."
    )
    outcome = serializers.ChoiceField(
        choices=[
            resits.INCOMPLETE,
            resits.PASSED,
            resits.RESIT,
            resits.FAILED,
            resits.UNRANKED,
            resits.ORIENT,
            resits.EXCLUDE,
        ],
        help_text="Issue proposée d'après les règles de l'école.",
    )
    rule = serializers.ChoiceField(
        choices=resits.RULES, help_text="Règle du règlement de l'école qui donne l'issue."
    )
    rule_params = serializers.DictField(source="params", help_text="Valeurs citées avec la règle.")
    courses = ResitCourseSerializer(source="failed", many=True)


class RulesSerializer(serializers.Serializer):
    pass_percent = serializers.IntegerField()
    course_pass_percent = serializers.IntegerField()
    resit_percent = serializers.IntegerField()
    resit_failures_to_fail = serializers.IntegerField()


class SecondSessionSerializer(serializers.Serializer):
    students = serializers.IntegerField(
        help_text="Élèves que la dernière proclamation de fin d'année envoie au repêchage."
    )
    exam_on = serializers.DateField(allow_null=True, help_text="Date de l'examen de repêchage.")
    status = serializers.ChoiceField(choices=Deliberation.Status.choices)
    version = serializers.IntegerField(help_text="Dernière version proclamée (0 : aucune).")
    can_manage = serializers.BooleanField(help_text="Droit `grades.validate` : date, convocations.")


class ClassResitsSerializer(serializers.Serializer):
    class_name = serializers.CharField()
    rules = RulesSerializer()
    students = StudentResitsSerializer(many=True)
    second_session = SecondSessionSerializer()


class ExamDateSerializer(serializers.Serializer):
    exam_on = serializers.DateField()


class ConvocationQuerySerializer(PrintOptionsSerializer):
    output = serializers.ChoiceField(choices=["pdf", "html"], default="pdf")
    enrollment = serializers.UUIDField(
        required=False, help_text="Un seul élève ; absent : toute la classe."
    )


class ResitGradeSerializer(serializers.Serializer):
    percent = serializers.DecimalField(
        max_digits=4,
        decimal_places=1,
        min_value=0,
        max_value=100,
        help_text="Pourcentage, 0 à 100.",
    )


class _ResitView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)


def _class_data(group: ClassGroup, request: Request) -> dict:
    """Élèves ayant un cours échoué, ou dont l'issue est l'échec. Après la proclamation de fin
    d'année, seuls ses élèves « repêchage » reçoivent une note ; plus aucun une fois la seconde
    session proclamée."""
    permissions = school_access(request).permissions
    rules = resits.rules_of(group)
    sent = resits.proclaimed_resits(group)
    rows = resits.class_overview(
        report_cards.class_report(group),
        user=request.user,
        permissions=permissions,
        resit_decided=sent,
    )
    current = deliberation.session_of(group, None, second=True)
    closed = current is not None and current.status == Deliberation.Status.PROCLAIMED
    for row in rows:
        if closed or (sent is not None and row.enrollment.pk not in sent):
            for course in row.failed:
                course.can_enter = False
    return {
        "class_name": group.name,
        "rules": rules,
        "students": [
            r for r in rows if r.failed or r.outcome not in (resits.PASSED, resits.INCOMPLETE)
        ],
        "second_session": {
            "students": len(sent or ()),
            "exam_on": current.exam_on if current else None,
            "status": current.status if current else Deliberation.Status.DRAFT,
            "version": current.version if current else 0,
            "can_manage": GRADES_VALIDATE in permissions,
        },
    }


@extend_schema(tags=["resits"])
class ClassResitsView(_ResitView):
    @extend_schema(responses={200: ClassResitsSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Élèves de la classe qui ont un cours échoué : cours, pourcentage de l'année, repêchage
        ouvert ou non, note de repêchage signée et issue proposée. `can_enter` : la personne peut
        saisir la note de ce cours."""
        group = get_object_or_404(ClassGroup.objects.select_related("school", "level"), pk=pk)
        permissions = school_access(request).permissions
        if (
            GRADES_ENTER_ANY not in permissions
            and GRADES_VALIDATE not in permissions
            and not gradable_courses(request.user, permissions).filter(class_group=group).exists()
        ):
            raise PermissionDenied(gettext("You cannot see the resit exams of this class."))
        data = _class_data(group, request)
        context = {"rules": data["rules"]}
        return Response(ClassResitsSerializer(data, context=context).data)


class _ManageView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = GRADES_VALIDATE


def _group(pk) -> ClassGroup:
    return get_object_or_404(
        ClassGroup.objects.select_related("school", "level", "academic_year"), pk=pk
    )


@extend_schema(tags=["resits"])
class ExamDateView(_ManageView):
    @extend_schema(request=ExamDateSerializer, responses={200: ClassResitsSerializer, **ERRORS})
    def put(self, request: Request, pk) -> Response:
        """Date de l'examen de repêchage de la classe (seconde session, NB.6), imprimée sur les
        convocations ; `no_second_session` sans élève envoyé au repêchage par la proclamation."""
        group = _group(pk)
        data = ExamDateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        deliberation.set_exam_date(group, data.validated_data["exam_on"], actor=request.user)
        data = _class_data(group, request)
        return Response(ClassResitsSerializer(data, context={"rules": data["rules"]}).data)


@extend_schema(tags=["resits"])
class ConvocationsView(_ManageView):
    @extend_schema(parameters=[ConvocationQuerySerializer], responses={**PRINT_RESPONSE, **ERRORS})
    def get(self, request: Request, pk) -> HttpResponse:
        """Convocations à l'examen de repêchage, en PDF ou en aperçu : une par élève envoyé en
        seconde session (cours à repasser et leur pourcentage, pourcentage de l'année, gardé,
        date de l'examen), deux par feuille A4. `exam_date_required` sans date fixée."""
        group = _group(pk)
        params = ConvocationQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        exam_on, rows = deliberation.convocations(group)
        if data.get("enrollment"):
            rows = [r for r in rows if r.enrollment.pk == data["enrollment"]]
        context = {
            **school_header(require_current_school()),
            "class_group": group,
            "year": group.academic_year,
            "exam_on": exam_on,
            "rows": rows,
            "signer": request.user.get_full_name(),
        }
        return render(
            "academics/resit_convocations.html",
            context,
            data["output"],
            f"convocations-repechage-{slugify(group.name)}.pdf",
            print_options(data, "portrait"),
        )


@extend_schema(tags=["resits"])
class ResitGradeView(_ResitView):
    def _target(self, request: Request, pk, course_pk) -> tuple[Enrollment, Course]:
        enrollment = get_object_or_404(
            Enrollment.objects.select_related(
                "student", "class_group__school", "class_group__level"
            ),
            pk=pk,
        )
        course = get_object_or_404(Course, pk=course_pk)
        permissions = school_access(request).permissions
        if not gradable_courses(request.user, permissions).filter(pk=course.pk).exists():
            raise PermissionDenied(
                gettext("Only the teacher of the course enters its resit grade.")
            )
        return enrollment, course

    def _answer(self, enrollment: Enrollment, request: Request) -> Response:
        data = _class_data(enrollment.class_group, request)
        student = next(s for s in data["students"] if s.enrollment.pk == enrollment.pk)
        return Response(StudentResitsSerializer(student, context={"rules": data["rules"]}).data)

    @extend_schema(
        request=ResitGradeSerializer,
        responses={200: StudentResitsSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request, pk, course_pk) -> Response:
        """Saisit la note de repêchage d'un cours échoué ; l'enseignant la signe (son nom reste)."""
        enrollment, course = self._target(request, pk, course_pk)
        data = ResitGradeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        resits.record(
            enrollment,
            course,
            actor=request.user,
            permissions=school_access(request).permissions,
            percent=data.validated_data["percent"],
        )
        return self._answer(enrollment, request)

    @extend_schema(responses={200: StudentResitsSerializer, 400: ErrorSerializer, **ERRORS})
    def delete(self, request: Request, pk, course_pk) -> Response:
        """Reprend la note de repêchage saisie."""
        enrollment, course = self._target(request, pk, course_pk)
        resits.clear(
            enrollment, course, actor=request.user, permissions=school_access(request).permissions
        )
        return self._answer(enrollment, request)
