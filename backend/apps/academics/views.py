from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import (
    courses,
    gradebook,
    grades,
    official,
    report_card_documents,
    report_cards,
)
from apps.academics.models import Course, GradeDeadline
from apps.academics.serializers import (
    CoursesCopiedSerializer,
    CoursesCopySerializer,
    CourseSerializer,
    CoursesUpdateSerializer,
    DeadlineSerializer,
    GradeSheetPrintSerializer,
    GradingFilterSerializer,
    GradingSerializer,
    OfficialGridSerializer,
    ReopenSerializer,
    ReportCardSerializer,
    ReportCardStatusSerializer,
    SheetSerializer,
    SheetUpdateSerializer,
    TeachingLoadsFilterSerializer,
    TeachingLoadsSerializer,
    ValidationSerializer,
)
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import (
    COURSES_CONFIGURE,
    GRADES_ENTER,
    GRADES_ENTER_ANY,
    GRADES_VALIDATE,
)
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import PRINT_RESPONSE, print_options, render
from apps.core.errors import ApiError, BusinessError, ErrorSerializer
from apps.core.kept import Keep
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

    def may_validate(self) -> bool:
        return GRADES_VALIDATE in school_access(self.request).permissions

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
        courses.set_courses(
            group, serializer.items(), actor=request.user, may_validate=self.may_validate()
        )
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
            source,
            serializer.validated_data["class_groups"],
            actor=request.user,
            may_validate=self.may_validate(),
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
                group.pk,
                {
                    "id": group.pk,
                    "name": group.name,
                    "courses": [],
                    "is_homeroom": group.homeroom_teacher_id == request.user.pk,
                },
            )
            entry["courses"].append(course)
        data = {
            "academic_year": year.pk,
            "terms": term_tree(year),
            "classes": list(classes.values()),
        }
        return Response(GradingSerializer(data).data)


class _SheetView(_GradesView):
    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)

    def objects(self, pk, term_pk, *, read: bool = False) -> tuple[Course, Term]:
        # Manager de l'école de l'adresse : un cours ou une période d'une autre école est
        # introuvable ; un cours de l'école que le compte ne note pas : 403 (qui valide les notes
        # les lit toutes).
        course = get_object_or_404(
            Course.objects.select_related("class_group__level", "class_group__track"), pk=pk
        )
        if read and GRADES_VALIDATE in school_access(self.request).permissions:
            pass
        elif not self.gradable().filter(pk=course.pk).exists():
            raise PermissionDenied(
                _("You do not enter the grades of this course."), code="not_your_course"
            )
        return course, get_object_or_404(Term.objects.select_related("parent"), pk=term_pk)


@extend_schema(tags=["grades"])
class GradeSheetView(_SheetView):
    serializer_class = SheetUpdateSerializer

    @extend_schema(responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS})
    def get(self, request: Request, pk, term) -> Response:
        """Feuille de notes du cours dans une période ou des examens : évaluations, élèves de la
        classe, notes, note de la période."""
        return Response(SheetSerializer(grades.sheet(*self.objects(pk, term, read=True))).data)

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
        saved = grades.save_sheet(
            course,
            period,
            actor=request.user,
            may_validate=GRADES_VALIDATE in school_access(request).permissions,
            **serializer.inputs(),
        )
        return Response(SheetSerializer(saved).data)


@extend_schema(tags=["grades"], request=None)
class GradeSubmitView(_SheetView):
    @extend_schema(responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS})
    def post(self, request: Request, pk, term) -> Response:
        """Envoie la feuille au directeur des études : complète (400 `incomplete_sheet`), pas
        déjà envoyée (409 `sheet_not_draft`)."""
        saved = grades.submit_sheet(*self.objects(pk, term), actor=request.user)
        return Response(SheetSerializer(saved).data)


class _ValidationView(_SheetView):
    """Droit `grades.validate` (double authentification), sur toutes les feuilles de l'école."""

    required_permission = GRADES_VALIDATE

    def objects(self, pk, term_pk, *, read: bool = True) -> tuple[Course, Term]:
        return super().objects(pk, term_pk, read=True)


@extend_schema(tags=["grades"], request=None)
class GradeValidateView(_ValidationView):
    @extend_schema(responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS})
    def post(self, request: Request, pk, term) -> Response:
        """Valide une feuille envoyée : elle est fermée (409 `sheet_not_sent` sinon)."""
        saved = grades.validate_sheet(*self.objects(pk, term), actor=request.user)
        return Response(SheetSerializer(saved).data)


@extend_schema(tags=["grades"])
class GradeReopenView(_ValidationView):
    serializer_class = ReopenSerializer

    @extend_schema(
        request=ReopenSerializer,
        responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request, pk, term) -> Response:
        """Renvoie une feuille envoyée ou validée en brouillon, avec le motif ; la date limite ne
        la ferme plus."""
        course, period = self.objects(pk, term)
        serializer = ReopenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved = grades.reopen_sheet(
            course, period, reason=serializer.validated_data["reason"], actor=request.user
        )
        return Response(SheetSerializer(saved).data)


@extend_schema(tags=["grades"])
class GradingValidationView(APIView):
    """Droit `grades.validate`, module `academics` (8.2.2)."""

    permission_classes = [HasSchoolPermission]
    required_permission = GRADES_VALIDATE
    required_module = "academics"

    @extend_schema(
        parameters=[GradingFilterSerializer], responses={200: ValidationSerializer, **ERRORS}
    )
    def get(self, request: Request) -> Response:
        """Feuilles envoyées de l'année à valider, et la date limite de saisie de chaque période."""
        params = GradingFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        year = params.validated_data.get("academic_year") or organisation.current_year()
        if year is None:
            return Response({"academic_year": None, "terms": [], "deadlines": [], "sheets": []})
        deadlines = GradeDeadline.objects.filter(term__academic_year=year).values(
            "term_id", "due_on"
        )
        data = {
            "academic_year": year.pk,
            "terms": term_tree(year),
            "deadlines": [{"term": row["term_id"], "due_on": row["due_on"]} for row in deadlines],
            "sheets": grades.awaiting_validation(year),
        }
        return Response(ValidationSerializer(data).data)


@extend_schema(tags=["grades"])
class GradeDeadlineView(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = GRADES_VALIDATE
    required_module = "academics"
    serializer_class = DeadlineSerializer

    @extend_schema(
        request=DeadlineSerializer,
        responses={200: DeadlineSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request, term) -> Response:
        """Date limite de saisie des notes d'une période ou des examens ; vide : plus de limite."""
        period = get_object_or_404(Term, pk=term)
        serializer = DeadlineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grades.set_deadline(period, serializer.validated_data["due_on"], actor=request.user)
        return Response(serializer.validated_data)


@extend_schema(tags=["grades"])
class ReportCardStatusView(APIView):
    """Le bulletin de la classe peut-il s'imprimer ? (8.3.4) : mêmes droits que le bulletin."""

    permission_classes = [HasSchoolPermission]
    required_permission = (GRADES_ENTER_ANY, GRADES_VALIDATE)
    required_module = "academics"

    @extend_schema(responses={200: ReportCardStatusSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Feuilles de notes pas encore validées pour les périodes commencées de la classe : tant
        qu'il en reste, le PDF du bulletin est refusé (409 `report_incomplete`)."""
        group = get_object_or_404(ClassGroup.objects.select_related("academic_year"), pk=pk)
        missing = report_cards.missing_sheets(group)
        return Response(
            {
                "missing_count": len(missing),
                "missing": [
                    {"course": course.name, "term": grades.term_label(term)}
                    for course, term in missing[:MAX_MISSING_LISTED]
                ],
            }
        )


REPORT_INCOMPLETE = ApiError(
    "report_incomplete",
    _("Some courses have no validated grades yet: the report card cannot be printed."),
    409,
)
MAX_MISSING_LISTED = 20


@extend_schema(tags=["grades"])
class ReportCardView(APIView):
    """Bulletin d'un élève ou de toute la classe (8.3.2, 8.3.5) : `grades.enter_any` ou
    `grades.validate`."""

    permission_classes = [HasSchoolPermission]
    required_permission = (GRADES_ENTER_ANY, GRADES_VALIDATE)
    required_module = "academics"

    @extend_schema(
        parameters=[ReportCardSerializer],
        responses={**PRINT_RESPONSE, 409: ErrorSerializer, **ERRORS},
    )
    def get(self, request: Request, pk) -> HttpResponse:
        """Bulletin imprimable : PDF A4 ou son aperçu HTML, avec les places de la classe et un
        QR code d'authenticité ; sans `enrollment`, toute la classe (un élève par feuille) ;
        `mode=grades_only` pour le formulaire pré-imprimé ; chaque élève imprimé est noté dans le
        journal d'audit."""
        params = ReportCardSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        group = get_object_or_404(ClassGroup.objects.select_related("academic_year"), pk=pk)
        enrollment = params.validated_data.get("enrollment")
        report = report_cards.class_report(group)
        students = [s for s in report.students if not enrollment or s.enrollment.pk == enrollment]
        if not students:
            raise Http404
        output = params.validated_data["output"]
        missing = report_cards.missing_sheets(group)
        if output == "pdf" and missing:
            raise BusinessError(
                REPORT_INCOMPLETE,
                missing=[
                    {"course": course.name, "term": grades.term_label(term)}
                    for course, term in missing[:MAX_MISSING_LISTED]
                ],
                missing_count=len(missing),
            )
        if output == "pdf":
            audit.record_many(
                Action.GRADES_REPORT_CARD_PRINTED,
                [(s.enrollment, {}) for s in students],
                actor=request.user,
                label=lambda enrollment: f"{enrollment.student.full_name} · {group.name}",
            )
        extra = {
            "missing_count": len(missing),
            "grades_only": params.validated_data["mode"] == "grades_only",
            "dx": params.validated_data["dx"],
            "dy": params.validated_data["dy"],
        }
        # PERF.2 : chaque bulletin est un PDF gardé ; le QR code signé et la date changent à chaque
        # tirage, ils ne comptent pas dans l'empreinte (les notes, elles, comptent).
        keep = Keep(
            kind="report_card",
            subjects=[s.enrollment.pk for s in students],
            variant="grades_only" if extra["grades_only"] else "full",
            volatile={"qr": "", "day": None, "printed_at": None},
        )
        contexts = [
            {
                **report_card_documents.report_card_document(
                    report, student, actor=request.user, absolute=request.build_absolute_uri
                ),
                **extra,
            }
            for student in students
        ]
        name = (
            slugify(students[0].enrollment.student.full_name) if enrollment else slugify(group.name)
        )
        return render(
            "academics/report_card.html",
            contexts[0],
            output,
            f"bulletin-{name}.pdf",
            more=contexts[1:],
            keep=keep,
        )


@extend_schema(tags=["grades"])
class GradeSheetPrintView(_GradesView):
    """Fiche de cotes imprimable (8.3.6) : d'un cours, vierge, ou tableau de la classe."""

    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)

    @extend_schema(
        parameters=[GradeSheetPrintSerializer],
        responses={**PRINT_RESPONSE, 400: ErrorSerializer, **ERRORS},
    )
    def get(self, request: Request, pk) -> HttpResponse:
        """Fiche de cotes en PDF ou en aperçu HTML. Fiche d'un cours ou vierge : le compte note
        ce cours (qui valide les notes les lit toutes). Tableau de la classe : `grades.enter_any`,
        `grades.validate` ou titulaire de la classe. Notes pas encore validées : le document le
        dit (« provisoire »). Chaque PDF est noté dans le journal d'audit."""
        params = GradeSheetPrintSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        group = get_object_or_404(
            ClassGroup.objects.select_related("academic_year", "homeroom_teacher"), pk=pk
        )
        permissions = school_access(request).permissions
        kind, course = data["kind"], data.get("course")
        if kind == "class":
            if not (
                permissions & {GRADES_ENTER_ANY, GRADES_VALIDATE}
                or group.homeroom_teacher_id == request.user.pk
            ):
                raise PermissionDenied(_("You cannot print the table of this class."))
        else:
            if course.class_group_id != group.pk:
                raise Http404
            if GRADES_VALIDATE not in permissions and not self.gradable().filter(pk=course.pk):
                raise PermissionDenied(
                    _("You do not enter the grades of this course."), code="not_your_course"
                )
        report = report_cards.class_report(group)
        missing = [
            item for item in report_cards.missing_sheets(group) if not course or item[0] == course
        ]
        columns = set(data.get("columns", ()))
        if kind == "class":
            keys = {column.key for column in report.columns}
            if data["column"] not in keys:
                raise ValidationError({"column": "Unknown column."})
            context = gradebook.class_table(
                report, data["column"], columns=columns, missing=bool(missing)
            )
            name = f"cotes-{slugify(group.name)}"
        else:
            context = gradebook.course_sheet(
                report,
                course,
                columns=columns,
                missing=bool(missing),
                blank=data["blank_columns"] if kind == "blank" else None,
            )
            name = f"cotes-{slugify(group.name)}-{slugify(course.name)}"
        output = data["output"]
        if output == "pdf":
            audit.record(
                Action.GRADES_SHEET_PRINTED,
                group,
                actor=request.user,
                label=f"{course.name if course else ''} · {group.name} · {kind}".strip(" ·"),
            )
        return render(
            "academics/grade_sheet.html",
            context,
            output,
            f"{name}.pdf",
            print_options(data, context["orientation_default"]),
        )
