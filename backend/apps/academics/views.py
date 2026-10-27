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
    board,
    courses,
    gradebook,
    grades,
    official,
    report_card_documents,
    report_cards,
)
from apps.academics.models import Course, GradeDeadline
from apps.academics.serializers import (
    BoardFilterSerializer,
    CoursesCopiedSerializer,
    CoursesCopySerializer,
    CourseSerializer,
    CoursesUpdateSerializer,
    DeadlineSerializer,
    GradeSheetPrintSerializer,
    GradingFilterSerializer,
    GradingSerializer,
    OfficialGridSerializer,
    RemindersResultSerializer,
    RemindersSerializer,
    ReopenSerializer,
    ReportCardSerializer,
    ReportCardStatusSerializer,
    SheetSerializer,
    SheetUpdateSerializer,
    TeachingLoadsFilterSerializer,
    TeachingLoadsSerializer,
    TotalsSheetSerializer,
    ValidationSerializer,
)
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import (
    COURSES_CONFIGURE,
    GRADES_ENTER,
    GRADES_ENTER_ANY,
    GRADES_VALIDATE,
    TIMETABLE_MANAGE,
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
        items = serializer.items()
        # Le placement dans l'horaire appartient au module « Emploi du temps » (EDT.1b).
        if any(item.placement is not None for item in items) and not (
            request.school.has_module("timetable")
            and TIMETABLE_MANAGE in school_access(request).permissions
        ):
            raise PermissionDenied(
                _("Placing courses in the timetable needs the timetable right."),
                code="placement_forbidden",
            )
        courses.set_courses(group, items, actor=request.user, may_validate=self.may_validate())
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
    `grades.enter_any` (toutes les classes) (8.2.1) ; en ligne (hors ligne : 8.2.3). Les
    évaluations d'un cours : son enseignant seul (NB.1, `grades.notebook_access`)."""

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
        """Ce que le compte voit dans les notes de l'année : son découpage (périodes, examens) et,
        par classe, les cours qu'il donne, ceux de la classe dont il est titulaire, ou tous ;
        `teaches` : il tient le carnet du cours (ses évaluations)."""
        params = GradingFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        year = params.validated_data.get("academic_year") or organisation.current_year()
        if year is None:
            return Response({"academic_year": None, "terms": [], "classes": []})
        permissions = school_access(request).permissions
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
                    "is_homeroom": group.is_homeroom_of(request.user),
                },
            )
            course.teaches = course.teacher_id == request.user.pk
            course.access = grades.notebook_access(request.user, permissions, course)
            entry["courses"].append(course)
        data = {
            "academic_year": year.pk,
            "terms": term_tree(year),
            "classes": list(classes.values()),
        }
        return Response(GradingSerializer(data).data)


def _course_and_term(pk, term_pk) -> tuple[Course, Term]:
    # Manager de l'école de l'adresse : un cours ou une période d'une autre école est introuvable.
    course = get_object_or_404(
        Course.objects.select_related("class_group__level", "class_group__track"), pk=pk
    )
    return course, get_object_or_404(Term.objects.select_related("parent"), pk=term_pk)


class _SheetView(_GradesView):
    """Carnet de l'enseignant (NB.1) : l'enseignant du cours ; `grades.enter_any`, le titulaire
    et le cotitulaire de la classe (NB.7) n'y saisissent qu'un total par élève ; tout autre
    compte : 403 `not_your_course`, il lit la fiche de cotes."""

    def objects(self, pk, term_pk) -> tuple[Course, Term, bool]:
        course, term = _course_and_term(pk, term_pk)
        permissions = school_access(self.request).permissions
        access = grades.notebook_access(self.request.user, permissions, course)
        if access is None:
            raise PermissionDenied(
                _("Only the teacher of this course sees its evaluations."), code="not_your_course"
            )
        return course, term, access == grades.TOTAL_ONLY


@extend_schema(tags=["grades"])
class GradeSheetView(_SheetView):
    serializer_class = SheetUpdateSerializer

    @extend_schema(responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS})
    def get(self, request: Request, pk, term) -> Response:
        """Feuille de notes du cours dans une période ou des examens : évaluations, élèves de la
        classe, notes, note de la période. L'enseignant du cours ; `grades.enter_any` : une
        feuille « total » seulement (403 `notebook_private` si elle a des devoirs)."""
        course, period, total_only = self.objects(pk, term)
        return Response(SheetSerializer(grades.sheet(course, period, total_only=total_only)).data)

    @extend_schema(
        request=SheetUpdateSerializer,
        responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def put(self, request: Request, pk, term) -> Response:
        """Enregistre la feuille d'un seul envoi : évaluations ajoutées, modifiées ou retirées,
        cases changées ; renvoie la feuille à jour."""
        course, period, total_only = self.objects(pk, term)
        serializer = SheetUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved = grades.save_sheet(
            course,
            period,
            actor=request.user,
            may_validate=GRADES_VALIDATE in school_access(request).permissions,
            total_only=total_only,
            **serializer.inputs(),
        )
        return Response(SheetSerializer(saved).data)


@extend_schema(tags=["grades"], request=None)
class GradeSubmitView(_SheetView):
    @extend_schema(responses={200: SheetSerializer, 400: ErrorSerializer, **ERRORS})
    def post(self, request: Request, pk, term) -> Response:
        """Envoie et signe la fiche de cotes : complète (400 `incomplete_sheet`), pas déjà
        envoyée (409 `sheet_not_draft`) ; le directeur des études et le titulaire en sont
        avertis."""
        course, period, total_only = self.objects(pk, term)
        saved = grades.submit_sheet(course, period, actor=request.user, total_only=total_only)
        return Response(SheetSerializer(saved).data)


@extend_schema(tags=["grades"])
class GradeTotalsView(_GradesView):
    """Fiche de cotes (NB.1) : l'enseignant du cours, le titulaire de la classe,
    `grades.enter_any` et `grades.validate`."""

    required_permission = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)

    @extend_schema(responses={200: TotalsSheetSerializer, 400: ErrorSerializer, **ERRORS})
    def get(self, request: Request, pk, term) -> Response:
        """Fiche de cotes du cours dans une période ou des examens : le total de chaque élève au
        maximum de la période, sans les évaluations, une fois envoyée (avant : son état seul) ;
        qui l'a envoyée et signée, validée ou renvoyée, et son historique."""
        course, period = _course_and_term(pk, term)
        if (
            GRADES_VALIDATE not in school_access(request).permissions
            and not self.gradable().filter(pk=course.pk).exists()
        ):
            raise PermissionDenied(
                _("You cannot read the grade sheet of this course."), code="not_your_course"
            )
        return Response(TotalsSheetSerializer(grades.totals_sheet(course, period)).data)


class _ValidationView(APIView):
    """Droit `grades.validate` (double authentification), sur toutes les fiches de cotes de
    l'école ; le carnet de l'enseignant reste fermé (NB.1)."""

    permission_classes = [HasSchoolPermission]
    required_permission = GRADES_VALIDATE
    required_module = "academics"


@extend_schema(tags=["grades"], request=None)
class GradeValidateView(_ValidationView):
    @extend_schema(responses={200: TotalsSheetSerializer, 400: ErrorSerializer, **ERRORS})
    def post(self, request: Request, pk, term) -> Response:
        """Valide une fiche envoyée : elle est fermée (409 `sheet_not_sent` sinon)."""
        saved = grades.validate_sheet(*_course_and_term(pk, term), actor=request.user)
        return Response(TotalsSheetSerializer(saved).data)


@extend_schema(tags=["grades"])
class GradeReopenView(_ValidationView):
    serializer_class = ReopenSerializer

    @extend_schema(
        request=ReopenSerializer,
        responses={200: TotalsSheetSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request, pk, term) -> Response:
        """Renvoie une fiche envoyée ou validée à l'enseignant avec les remarques (`reason`) :
        elle revient dans son carnet, que la date limite ne ferme plus ; il en est averti."""
        course, period = _course_and_term(pk, term)
        serializer = ReopenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved = grades.reopen_sheet(
            course, period, reason=serializer.validated_data["reason"], actor=request.user
        )
        return Response(TotalsSheetSerializer(saved).data)


@extend_schema(tags=["grades"])
class GradingValidationView(APIView):
    """Tableau du directeur des études (8.2.2, NB.2) : droit `grades.validate`, module
    `academics`."""

    permission_classes = [HasSchoolPermission]
    required_permission = GRADES_VALIDATE
    required_module = "academics"

    @extend_schema(
        parameters=[BoardFilterSerializer], responses={200: ValidationSerializer, **ERRORS}
    )
    def get(self, request: Request) -> Response:
        """Découpage de l'année, dates limites de saisie, et pour une période ou des examens (par
        défaut la dernière commencée) l'état de la fiche de chaque cours de chaque classe :
        `not_started`, `in_progress`, `submitted`, `validated`, `returned` ; dernier rappel."""
        params = BoardFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        term = params.validated_data.get("term")
        year = term.academic_year if term else organisation.current_year()
        if year is None:
            empty = {"academic_year": None, "terms": [], "deadlines": [], "term": None}
            return Response({**empty, "classes": []})
        terms = board.graded_terms(year)
        if term is None or term.kind not in (Term.Kind.PERIOD, Term.Kind.EXAM):
            term = board.default_term(year, terms)
        deadlines = GradeDeadline.objects.filter(term__academic_year=year).values(
            "term_id", "due_on"
        )
        data = {
            "academic_year": year.pk,
            "terms": term_tree(year),
            "deadlines": [{"term": row["term_id"], "due_on": row["due_on"]} for row in deadlines],
            "term": term.pk if term else None,
            "classes": board.board(term) if term else [],
        }
        return Response(ValidationSerializer(data).data)


UNKNOWN_COURSE = ApiError("unknown_course", _("This course does not exist."), 400)


@extend_schema(tags=["grades"])
class GradeRemindersView(APIView):
    permission_classes = [HasSchoolPermission]
    required_permission = GRADES_VALIDATE
    required_module = "academics"

    @extend_schema(
        request=RemindersSerializer,
        responses={
            200: RemindersResultSerializer,
            400: ErrorSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def post(self, request: Request) -> Response:
        """Rappelle aux enseignants les fiches pas encore envoyées de ces cours (NB.2) : une
        notification par enseignant ; cours envoyés, sans enseignant ou déjà rappelés aujourd'hui
        ignorés ; 409 `notifications_off` sans le module Notifications."""
        serializer = RemindersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = set(serializer.validated_data["courses"])
        courses = list(Course.objects.filter(pk__in=ids).select_related("class_group"))
        if len(courses) != len(ids):
            raise BusinessError(UNKNOWN_COURSE)
        result = board.remind(serializer.validated_data["term"], courses, actor=request.user)
        return Response(RemindersResultSerializer(result).data)


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
        if kind in ("class", "ranking"):
            if not (
                permissions & {GRADES_ENTER_ANY, GRADES_VALIDATE}
                or group.is_homeroom_of(request.user)
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
        if kind in ("class", "ranking"):
            column = next((c for c in report.columns if c.key == data["column"]), None)
            if column is None:
                raise ValidationError({"column": "Unknown column."})
            # « Provisoire » d'après les seules périodes de la colonne imprimée.
            parts = set(column.parts)
            missing = [item for item in missing if str(item[1].pk) in parts]
            build = gradebook.class_table if kind == "class" else gradebook.ranking
            context = build(report, column.key, columns=columns, missing=bool(missing))
            name = f"{'cotes' if kind == 'class' else 'palmares'}-{slugify(group.name)}"
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
