"""Décision proposée par les règles de délibération de l'école (8.4.1, NB.4) : d'après le
pourcentage de l'année de chaque cours, la catégorie des cours (`Course.category`), la conduite,
l'application, les années déjà faites et l'âge de l'élève, et les règles de l'école
(`schools/pass_rules.py`), le système propose une issue et **cite la règle appliquée** (`rule`,
`params`). L'enseignant du cours saisit (et signe) la note de repêchage de chaque cours échoué.
Rien n'est stocké que cette note : la proposition suit les notes et les règles. La décision prise
(admis, doublant…) est celle de la délibération (8.4.2).

Seconde session (NB.6) : après la proclamation de fin d'année, seuls les élèves qu'elle envoie au
repêchage reçoivent une note, chaque cours échoué compris quand le conseil a accordé le repêchage
contre la proposition ; une fois la seconde session proclamée, plus aucune note (la rouvrir).

Issues proposées : `exclude` (conduite ou application, tripler, trop de redoublements), `unranked`
(non classé : aucune note), `incomplete` (une note de l'année manque), `orient` (sous le seuil
d'orientation), `failed` (double), `resit` (notes de repêchage attendues), `passed`.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.academics import application, discipline, report_cards
from apps.academics.grades import gradable_courses
from apps.academics.models import (
    MAIN,
    OPTION,
    PRACTICAL,
    Course,
    Deliberation,
    DeliberationSnapshot,
    ResitGrade,
)
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools import pass_rules as rules_module
from apps.schools.models import ClassGroup, Level, Term
from apps.students.models import Enrollment

INCOMPLETE, PASSED, RESIT, FAILED = "incomplete", "passed", "resit", "failed"
# Sans aucune note : non classé. Sous le seuil d'orientation : orienté ailleurs. Renvoi : exclu.
UNRANKED, ORIENT, EXCLUDE = "unranked", "orient", "exclude"
# Règle citée avec la proposition (traduite par l'interface, `deliberation.rules.*`).
RULES = (
    "passed",
    "passed_final",
    "resits_passed",
    "resit",
    "below_pass",
    "below_resit",
    "final_class",
    "practical",
    "too_many_resits",
    "main_courses",
    "option_courses",
    "resits_lost",
    "age_exception",
    "below_orientation",
    "repeated_class",
    "max_repeats",
    "conduct_ma",
    "conduct_me",
    "application_ma",
    "application_me",
    "no_grades",
    "missing_grades",
)

NOT_A_RESIT_COURSE = ApiError(
    "not_a_resit_course", _("This course does not open a resit exam for this student."), 400
)
BAD_PERCENT = ApiError("bad_percent", _("A resit grade is a percentage from 0 to 100."), 400)
SESSION_CLOSED = ApiError(
    "second_session_closed",
    _("The second session is proclaimed: reopen it before changing a resit grade."),
    400,
)
STEP = Decimal("0.1")


@dataclass
class CourseResit:
    course: Course
    percent: Decimal
    eligible: bool = False
    resit: ResitGrade | None = None
    can_enter: bool = False

    def passed(self, rules: dict) -> bool | None:
        if self.resit is None:
            return None
        return self.resit.percent >= rules["course_pass_percent"]


@dataclass
class Record:
    """Ce que les règles regardent pour un élève ; sans base de données (tests)."""

    percent: Decimal | None
    failed: list[CourseResit] = field(default_factory=list)
    noted: bool = True
    complete: bool = True
    # Cotes de chaque période, dans l'ordre (vide : pas encore de cote).
    conduct: list[str] = field(default_factory=list)
    application: list[str] = field(default_factory=list)
    # A déjà fait ce niveau une année précédente ; redoublements déjà faits ; âge à la rentrée
    # suivante ; la classe suivante est celle de l'Examen d'État.
    repeated_class: bool = False
    repeats: int = 0
    age: int | None = None
    enters_final: bool = False
    # Envoyé au repêchage par la proclamation de fin d'année (NB.6) : chaque cours échoué se
    # repasse, même contre la proposition ; seules les notes de repêchage décident.
    resit_decided: bool = False


@dataclass
class StudentResits:
    enrollment: Enrollment
    percent: Decimal | None
    outcome: str
    failed: list[CourseResit] = field(default_factory=list)
    rule: str = ""
    params: dict = field(default_factory=dict)


Decided = tuple[str, str, dict]


def _run(grades: list[str], worst: set[str]) -> int:
    """Plus longue suite de périodes consécutives notées dans `worst`."""
    longest = current = 0
    for grade in grades:
        current = current + 1 if grade in worst else 0
        longest = max(longest, current)
    return longest


def _misconduct(rules: dict, record: Record) -> Decided | None:
    """Exclusion : MA, ou ME ou moins, autant de périodes de suite ; en conduite, puis en
    application si l'école la compte (chacune à part)."""
    subjects = [("conduct", record.conduct)]
    if rules["application_counts"]:
        subjects.append(("application", record.application))
    for subject, grades in subjects:
        for code, limit, worst in (
            ("ma", rules["conduct_ma_to_exclude"], {"MA"}),
            ("me", rules["conduct_me_to_exclude"], {"ME", "MA"}),
        ):
            if limit and _run(grades, worst) >= limit:
                return EXCLUDE, f"{subject}_{code}", {"count": limit}
    return None


def _resit_blocked(rules: dict, failed: list[CourseResit]) -> tuple[str, dict] | None:
    """Ce qui ferme le repêchage : cours pratique, trop de cours, trop de cours principaux ou de
    branches d'option ensemble."""
    practical = [f.course.name for f in failed if f.course.category == PRACTICAL]
    if practical and not rules["practical_resit"]:
        return "practical", {"courses": ", ".join(practical)}
    if len(failed) > rules["max_resit_courses"]:
        return "too_many_resits", {"count": len(failed), "max": rules["max_resit_courses"]}
    main = [f.course.name for f in failed if f.course.category == MAIN]
    if len(main) > rules["max_main_resits"]:
        return "main_courses", {"courses": ", ".join(main), "max": rules["max_main_resits"]}
    options = [f for f in failed if f.course.category == OPTION]
    if len(options) > rules["max_option_resits"]:
        return "option_courses", {"count": len(options), "max": rules["max_option_resits"]}
    return None


def _results(rules: dict, record: Record) -> Decided:
    """Passe, repêchage ou double, d'après les notes ; ouvre le repêchage des cours échoués."""
    percent, failed = record.percent, record.failed
    if record.resit_decided and failed:
        return _after_resits(rules, failed)
    if record.enters_final and rules["final_pass_percent"]:
        threshold = rules["final_pass_percent"]
        if percent >= threshold and not failed:
            return PASSED, "passed_final", {"threshold": threshold}
        return FAILED, "final_class", {"percent": percent, "threshold": threshold}
    if percent < rules["pass_percent"]:
        return FAILED, "below_pass", {"percent": percent, "threshold": rules["pass_percent"]}
    if not failed:
        return PASSED, "passed", {}
    if percent < rules["resit_percent"]:
        return FAILED, "below_resit", {"percent": percent, "threshold": rules["resit_percent"]}
    if blocked := _resit_blocked(rules, failed):
        return FAILED, *blocked
    return _after_resits(rules, failed)


def _after_resits(rules: dict, failed: list[CourseResit]) -> Decided:
    """Repêchage ouvert pour chaque cours échoué : attendu tant qu'une note manque, puis passe ou
    double selon les cours perdus."""
    for row in failed:
        row.eligible = True
    if any(row.resit is None for row in failed):
        return RESIT, "resit", {"count": len(failed)}
    lost = sum(1 for row in failed if not row.passed(rules))
    if lost >= rules["resit_failures_to_fail"]:
        return FAILED, "resits_lost", {"count": lost}
    return PASSED, "resits_passed", {}


def _young(rules: dict, record: Record) -> bool:
    years, limit = rules["age_exception_years"], rules["age_limit"]
    return bool(years and limit and record.age is not None and record.age <= limit - years)


def _repeat_or_leave(rules: dict, record: Record, results: Decided) -> Decided:
    """L'élève qui doit doubler peut-il reprendre la classe ? Sinon orienté ou exclu, sauf
    l'élève jeune (exception d'âge)."""
    percent = record.percent
    if rules["orientation_percent"] and percent < rules["orientation_percent"]:
        threshold = rules["orientation_percent"]
        leave = ORIENT, "below_orientation", {"percent": percent, "threshold": threshold}
    elif rules["exclude_repeated_class"] and record.repeated_class:
        leave = EXCLUDE, "repeated_class", {}
    elif rules["max_repeats"] and record.repeats >= rules["max_repeats"]:
        leave = EXCLUDE, "max_repeats", {"max": rules["max_repeats"]}
    else:
        return results
    if _young(rules, record) and percent >= rules["age_exception_percent"]:
        return FAILED, "age_exception", {"age": record.age, "limit": rules["age_limit"]}
    return leave


def decide(rules: dict, record: Record) -> Decided:
    """Issue proposée, règle citée et ses valeurs. Ordre : conduite et application, notes
    (passe, repêchage, double), puis orientation ou exclusion de qui devrait doubler."""
    results = None
    if record.noted and record.percent is not None and record.complete:
        results = _results(rules, record)
    if excluded := _misconduct(rules, record):
        return excluded
    if not record.noted:
        return UNRANKED, "no_grades", {}
    if results is None:
        return INCOMPLETE, "missing_grades", {}
    if results[0] != FAILED:
        return results
    return _repeat_or_leave(rules, record, results)


def grades_of_class(enrollment_ids: list[UUID]) -> dict[tuple[UUID, UUID], ResitGrade]:
    """Notes de repêchage de la classe, par (inscription, cours), avec l'enseignant qui a signé :
    une requête, pour le bulletin."""
    return {
        (r.enrollment_id, r.course_id): r
        for r in ResitGrade.objects.filter(enrollment__in=enrollment_ids).select_related(
            "signed_by"
        )
    }


def rules_of(group: ClassGroup) -> dict:
    """Règles de la classe : celles de l'école, que son niveau peut remplacer (7e, 3e…)."""
    return rules_module.class_rules(group.school.settings, group.level.pass_rules)


def _enters_final(level: Level) -> bool:
    """La classe suivante (niveau suivant dans l'ordre de l'école) est celle de l'Examen
    d'État."""
    if level.has_state_exam:
        return False
    levels = list(Level.objects.only("pk", "has_state_exam"))
    index = next((i for i, item in enumerate(levels) if item.pk == level.pk), None)
    return index is not None and index + 1 < len(levels) and levels[index + 1].has_state_exam


def _history(group: ClassGroup, students) -> dict[UUID, list[UUID]]:
    """Niveaux de chaque élève les années d'avant (une requête), dans cette école seulement."""
    levels: dict[UUID, list[UUID]] = {}
    rows = Enrollment.objects.filter(
        student__in=[s.enrollment.student_id for s in students],
        academic_year__starts_on__lt=group.academic_year.starts_on,
    ).values_list("student_id", "class_group__level_id")
    for student_id, level_id in rows:
        levels.setdefault(student_id, []).append(level_id)
    return levels


def _age(birth: date | None, on: date) -> int | None:
    if birth is None:
        return None
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def class_overview(
    report: report_cards.ClassReport,
    *,
    user: User | None = None,
    permissions=(),
    with_history: bool = True,
    resit_decided: set[UUID] | None = None,
) -> list[StudentResits]:
    """Pour chaque élève de la classe : pourcentage de l'année, cours échoués (avec la note de
    repêchage éventuelle), issue proposée et règle citée. Quelques requêtes pour toute la classe
    (notes de repêchage, conduite, application, années d'avant) ; `user` et `permissions` disent
    quels cours la personne peut noter. `with_history=False` : notes seules (`make demo`).
    `resit_decided` : élèves envoyés au repêchage par la proclamation (NB.6)."""
    group = report.class_group
    rules = rules_of(group)
    enrollment_ids = [s.enrollment.pk for s in report.students]
    resits = grades_of_class(enrollment_ids)
    enterable: set[UUID] = set()
    if user is not None:
        enterable = set(
            gradable_courses(user, permissions)
            .filter(class_group=group)
            .values_list("pk", flat=True)
        )
    terms = [c.term for c in report.columns if c.kind == "leaf" and c.term.kind == Term.Kind.PERIOD]
    conduct, applied, history, enters_final = {}, {}, {}, False
    # La démonstration (`make demo`) n'en a pas besoin et la requête des points de conduite est
    # lente sur une base toute neuve.
    if with_history:
        conduct = discipline.grades_of_class(enrollment_ids, terms)
        if rules["application_counts"]:
            applied = application.grades_of_report(report)
        history = _history(group, report.students)
        enters_final = _enters_final(group.level)
    # Âge à la rentrée suivante : le même mois, l'année d'après.
    start = group.academic_year.starts_on
    next_start = date(start.year + 1, start.month, 1)
    result = []
    for student in report.students:
        enrollment = student.enrollment
        noted = any(
            cell.score is not None for row in student.cells.values() for cell in row.values()
        )
        total = student.totals.get(report_cards.YEAR_KEY)
        failed, complete = [], True
        for course in report.courses:
            cell = student.cells[course.pk].get(report_cards.YEAR_KEY)
            if not course.is_taught or cell is None or not cell.maximum:
                continue
            if cell.score is None:
                complete = False
                continue
            percent = report_cards._percent(cell.score, cell.maximum)
            if percent < rules["course_pass_percent"]:
                failed.append(
                    CourseResit(
                        course,
                        percent,
                        resit=resits.get((enrollment.pk, course.pk)),
                        can_enter=course.pk in enterable,
                    )
                )
        before = history.get(enrollment.student_id, [])
        levels = [*before, group.level_id]
        record = Record(
            total.percent if total else None,
            failed,
            noted=noted,
            complete=complete,
            conduct=[conduct.get((enrollment.pk, t.pk), "") for t in terms],
            application=[applied.get((enrollment.pk, t.pk), "") for t in terms],
            repeated_class=group.level_id in before,
            repeats=len(levels) - len(set(levels)),
            age=_age(enrollment.student.birth_date, next_start),
            enters_final=enters_final,
            resit_decided=enrollment.pk in (resit_decided or ()),
        )
        outcome, rule, params = decide(rules, record)
        # Pourcentages en texte (« 48.5 ») : la ligne figée de la proclamation est du JSON.
        params = {k: str(v) if isinstance(v, Decimal) else v for k, v in params.items()}
        result.append(StudentResits(enrollment, record.percent, outcome, failed, rule, params))
    return result


def proclaimed_resits(group: ClassGroup) -> set[UUID] | None:
    """Élèves que la dernière proclamation de fin d'année envoie en seconde session ; `None` :
    rien de proclamé encore."""
    snapshot = (
        DeliberationSnapshot.objects.filter(
            deliberation__class_group=group,
            deliberation__term__isnull=True,
            deliberation__second_session=False,
        )
        .order_by("-version")
        .only("rows")
        .first()
    )
    if snapshot is None:
        return None
    return {UUID(row["enrollment"]) for row in snapshot.rows if row.get("decision") == RESIT}


def second_session_closed(group: ClassGroup) -> bool:
    return Deliberation.objects.filter(
        class_group=group,
        second_session=True,
        status=Deliberation.Status.PROCLAIMED,
    ).exists()


def record(
    enrollment: Enrollment, course: Course, *, actor: User, permissions, percent: Decimal
) -> ResitGrade:
    """Saisit (ou remplace) la note de repêchage d'un cours échoué ; l'enseignant la signe. Le
    cours doit être l'un de ceux qui ouvrent un repêchage pour cet élève."""
    percent = Decimal(percent).quantize(STEP)
    if not Decimal(0) <= percent <= Decimal(100):
        raise BusinessError(BAD_PERCENT)
    row = _failed_course(enrollment, course, actor, permissions)
    with transaction.atomic():
        before = {"percent": str(row.resit.percent)} if row.resit else None
        saved, _created = ResitGrade.objects.update_or_create(
            enrollment=enrollment,
            course=course,
            defaults={"percent": percent, "signed_by": actor},
        )
        audit.record(
            Action.RESIT_GRADE_CHANGED,
            saved,
            actor=actor,
            before=before,
            after={"percent": str(percent), "course": course.name},
            label=f"{enrollment.student.full_name} · {course.name}",
        )
    return saved


def clear(enrollment: Enrollment, course: Course, *, actor: User, permissions) -> None:
    """Reprend la note de repêchage ; le journal garde la note retirée."""
    row = _failed_course(enrollment, course, actor, permissions)
    if row.resit is None:
        return
    with transaction.atomic():
        before = {"percent": str(row.resit.percent), "course": course.name}
        row.resit.delete()
        audit.record(
            Action.RESIT_GRADE_CHANGED,
            None,
            actor=actor,
            before=before,
            after=None,
            label=f"{enrollment.student.full_name} · {course.name}",
        )


def _failed_course(enrollment, course, actor, permissions) -> CourseResit:
    group = enrollment.class_group
    if course.class_group_id != enrollment.class_group_id:
        raise BusinessError(NOT_A_RESIT_COURSE)
    if second_session_closed(group):
        raise BusinessError(SESSION_CLOSED)
    sent = proclaimed_resits(group)
    if sent is not None and enrollment.pk not in sent:
        raise BusinessError(NOT_A_RESIT_COURSE)
    report = report_cards.class_report(group)
    students = class_overview(report, user=actor, permissions=permissions, resit_decided=sent)
    for student in students:
        if student.enrollment.pk == enrollment.pk:
            for row in student.failed:
                if row.course.pk == course.pk and row.eligible:
                    return row
    raise BusinessError(NOT_A_RESIT_COURSE)
