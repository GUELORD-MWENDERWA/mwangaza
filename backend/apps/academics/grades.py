"""Notes (8.2.1) : la feuille d'un cours dans une période ou des examens — ses évaluations
(interrogations, devoirs, travaux pratiques : nom et maximum libres) et les notes des élèves de la
classe — se lit et s'enregistre d'un seul envoi.

Note de la période = somme des notes ramenée au maximum de la période (examens : deux fois le
maximum du cours) par une règle de trois, arrondie au dixième (décisions du 2026-10-15) ; calculée,
jamais stockée. Droits `grades.enter` (ses cours et sa classe de titulaire) et `grades.enter_any`
(toutes les classes), vérifiés par l'API avec `gradable_courses`. Chaque enregistrement qui change
quelque chose écrit **une** entrée au journal (domaine `grades`), avec les seules cases changées.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Course, Evaluation, Grade
from apps.accounts.models import User
from apps.accounts.roles import GRADES_ENTER, GRADES_ENTER_ANY
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import Term
from apps.students.models import Enrollment

NOT_GRADED_HERE = ApiError("not_graded_here", _("This course is not graded in this period."), 400)
# Au-delà, c'est une erreur de saisie (une période en compte rarement plus de dix).
MAX_EVALUATIONS = 30
STEP = Decimal("0.1")


@dataclass(frozen=True)
class EvaluationInput:
    """Une évaluation à ajouter ou à garder ; `id` : la sienne, ou celle donnée par l'appareil
    pour une nouvelle."""

    name: str
    max_score: int
    id: UUID | None = None


@dataclass(frozen=True)
class GradeInput:
    """Une case changée ; `score` vide : la case est vidée."""

    enrollment_id: UUID
    evaluation_id: UUID
    score: Decimal | None


@dataclass
class Row:
    enrollment: Enrollment
    scores: dict[UUID, Decimal] = field(default_factory=dict)
    total: Decimal | None = None


@dataclass
class Sheet:
    course: Course
    term: Term
    maximum: int
    evaluations: list[Evaluation]
    rows: list[Row]


def gradable_courses(user: User, permissions) -> QuerySet[Course]:
    """Cours de l'école courante dont `user` saisit les notes : tous avec `grades.enter_any` ;
    avec `grades.enter`, ceux qu'il donne et ceux de la classe dont il est titulaire."""
    courses = Course.objects.all()
    if GRADES_ENTER_ANY in permissions:
        return courses
    if GRADES_ENTER in permissions:
        return courses.filter(Q(teacher=user) | Q(class_group__homeroom_teacher=user))
    return courses.none()


def term_maximum(course: Course, term: Term) -> int:
    """Maximum de la feuille : celui du cours pour une période, le double pour des examens."""
    return course.period_max * 2 if term.kind == Term.Kind.EXAM else course.period_max


def period_score(scores: list[Decimal | None], maxima: list[int], maximum: int) -> Decimal | None:
    """Somme des notes ramenée à `maximum` (règle de trois), au dixième le plus proche (la moitié
    vers le haut). Rien sans évaluation, ni tant qu'une case est vide (« incomplet »)."""
    if not maxima or any(score is None for score in scores):
        return None
    total = sum(scores, Decimal(0)) * maximum / sum(maxima)
    return total.quantize(STEP, rounding=ROUND_HALF_UP)


def term_label(term: Term) -> str:
    """Nom de la période ou des examens pour le journal : le sien, sinon « Période 3 »,
    « Examens · Semestre 1 » (l'interface, elle, a tout le découpage pour le nommer)."""
    if term.name:
        return term.name

    def place(node: Term) -> int:
        earlier = Term.objects.filter(
            academic_year_id=node.academic_year_id, kind=node.kind, order__lt=node.order
        )
        return earlier.count() + 1

    if term.kind == Term.Kind.PERIOD:
        return _("Period %(n)d") % {"n": place(term)}
    parent = term.parent
    if parent is None:
        return str(_("Exams"))
    group = parent.name or (
        _("Semester %(n)d") if parent.kind == Term.Kind.SEMESTER else _("Trimester %(n)d")
    ) % {"n": place(parent)}
    return _("Exams · %(group)s") % {"group": group}


def _check_term(course: Course, term: Term) -> None:
    year = course.class_group.academic_year_id
    exam = term.kind == Term.Kind.EXAM
    if (
        term.academic_year_id != year
        or term.kind not in (Term.Kind.PERIOD, Term.Kind.EXAM)
        or (exam and not course.has_exam)
    ):
        raise BusinessError(NOT_GRADED_HERE)


def _evaluations(course: Course, term: Term) -> list[Evaluation]:
    return list(Evaluation.objects.filter(course=course, term=term).order_by("order", "created_at"))


def sheet(course: Course, term: Term) -> Sheet:
    """Feuille de notes : évaluations dans l'ordre, élèves actifs de la classe (et ceux partis
    qui ont déjà une note ici) par nom, leurs notes et leur note de la période. Trois requêtes."""
    _check_term(course, term)
    evaluations = _evaluations(course, term)
    graded_here = Grade.objects.filter(enrollment=OuterRef("pk"), evaluation__in=evaluations)
    enrollments = (
        Enrollment.objects.filter(class_group_id=course.class_group_id)
        .filter(Q(status=Enrollment.Status.ACTIVE) | Exists(graded_here))
        .select_related("student")
        .order_by("student__last_name", "student__middle_name", "student__first_name")
    )
    rows = {enrollment.pk: Row(enrollment) for enrollment in enrollments}
    grades = Grade.objects.filter(evaluation__in=evaluations).values_list(
        "enrollment_id", "evaluation_id", "score"
    )
    for enrollment_id, evaluation_id, score in grades:
        if enrollment_id in rows:
            rows[enrollment_id].scores[evaluation_id] = score
    maximum = term_maximum(course, term)
    maxima = [evaluation.max_score for evaluation in evaluations]
    for row in rows.values():
        scores = [row.scores.get(evaluation.pk) for evaluation in evaluations]
        row.total = period_score(scores, maxima, maximum)
    return Sheet(course, term, maximum, evaluations, list(rows.values()))


def _invalid(path: str, message, code: str) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code)})


def _plan_evaluations(
    existing: dict[UUID, Evaluation], items: list[EvaluationInput], removed: set[UUID]
) -> dict[UUID, int]:
    """Vérifie les évaluations envoyées ; renvoie le maximum de chacune après l'envoi."""
    maxima = {pk: evaluation.max_score for pk, evaluation in existing.items() if pk not in removed}
    seen: set[UUID] = set()
    for index, item in enumerate(items):
        if item.id is not None:
            if item.id in seen or item.id in removed:
                raise _invalid(
                    f"evaluations.{index}.id", _("Unknown evaluation."), "unknown_evaluation"
                )
            seen.add(item.id)
            maxima[item.id] = item.max_score
    if len(maxima) + sum(item.id is None for item in items) > MAX_EVALUATIONS:
        raise _invalid(
            "evaluations",
            _("At most %(max)d evaluations per period.") % {"max": MAX_EVALUATIONS},
            "too_many_evaluations",
        )
    return maxima


def save_sheet(
    course: Course,
    term: Term,
    *,
    evaluations: list[EvaluationInput],
    removed: list[UUID],
    grades: list[GradeInput],
    actor: User,
) -> Sheet:
    """Enregistre la feuille d'un seul envoi : évaluations ajoutées ou modifiées (`evaluations`,
    dans l'ordre ; celles qui ne sont pas envoyées restent), retirées avec leurs notes
    (`removed` ; une déjà partie est ignorée), et les seules cases changées (`grades`). Tout est
    vérifié avant d'écrire. Deux enregistrements de la même feuille passent l'un après l'autre ;
    pour une même case, le dernier gagne."""
    _check_term(course, term)
    with transaction.atomic():
        # Verrou sur le cours : deux envois de la même feuille ne créent pas deux fois une note.
        list(Course.objects.select_for_update().filter(pk=course.pk).order_by().values("pk"))
        existing = {evaluation.pk: evaluation for evaluation in _evaluations(course, term)}
        removed_ids = {pk for pk in removed if pk in existing}
        maxima = _plan_evaluations(existing, evaluations, removed_ids)
        new_ids = {item.id for item in evaluations if item.id is not None} - existing.keys()
        enrollment_ids = set(
            Enrollment.objects.filter(
                class_group_id=course.class_group_id,
                pk__in={grade.enrollment_id for grade in grades},
            ).values_list("pk", flat=True)
        )
        current = {
            (grade.enrollment_id, grade.evaluation_id): grade
            for grade in Grade.objects.filter(evaluation__in=list(existing)).select_related(
                "enrollment__student"
            )
        }
        wanted: dict[tuple[UUID, UUID], Decimal | None] = {}
        for index, item in enumerate(grades):
            if item.enrollment_id not in enrollment_ids:
                raise _invalid(
                    f"grades.{index}.enrollment_id",
                    _("This student is not in the class."),
                    "unknown_student",
                )
            if item.evaluation_id not in maxima and item.evaluation_id not in new_ids:
                raise _invalid(
                    f"grades.{index}.evaluation_id", _("Unknown evaluation."), "unknown_evaluation"
                )
            if item.score is not None and item.score > maxima[item.evaluation_id]:
                raise _invalid(
                    f"grades.{index}.score",
                    _("A grade cannot be above the maximum of its evaluation."),
                    "above_maximum",
                )
            wanted[(item.enrollment_id, item.evaluation_id)] = item.score
        # Un maximum baissé sous une note gardée : refusé.
        for key, grade in current.items():
            maximum = maxima.get(grade.evaluation_id)
            score = wanted.get(key, grade.score)
            if maximum is not None and score is not None and score > maximum:
                index = next(
                    (i for i, item in enumerate(evaluations) if item.id == grade.evaluation_id), 0
                )
                raise _invalid(
                    f"evaluations.{index}.max_score",
                    _("A grade is above this maximum."),
                    "below_a_grade",
                )

        before_evaluations, after_evaluations = [], []
        now = timezone.now()
        created, updated = [], []
        for order, item in enumerate(evaluations):
            evaluation = existing.get(item.id) if item.id is not None else None
            if evaluation is None:
                evaluation = Evaluation(course=course, term=term, created_by=actor)
                if item.id is not None:
                    evaluation.pk = item.id
                created.append(evaluation)
                after_evaluations.append({"name": item.name.strip(), "max_score": item.max_score})
            else:
                old = {"name": evaluation.name, "max_score": evaluation.max_score}
                new = {"name": item.name.strip(), "max_score": item.max_score}
                if old != new:
                    before_evaluations.append(old)
                    after_evaluations.append(new)
                if old != new or evaluation.order != order:
                    evaluation.updated_at = now
                    updated.append(evaluation)
            evaluation.name, evaluation.max_score, evaluation.order = (
                item.name.strip(),
                item.max_score,
                order,
            )
        gone = [existing[pk] for pk in removed_ids]
        before_evaluations += [{"name": e.name, "max_score": e.max_score} for e in gone]
        names = {e.pk: e.name for e in [*existing.values(), *created]}

        before_grades, after_grades, to_create, to_update, to_delete = [], [], [], [], []
        students = {
            enrollment.pk: enrollment
            for enrollment in Enrollment.objects.filter(pk__in=enrollment_ids).select_related(
                "student"
            )
        }
        for (enrollment_id, evaluation_id), score in wanted.items():
            grade = current.get((enrollment_id, evaluation_id))
            if grade is not None and grade.score == score:
                continue
            student = students[enrollment_id].student.full_name
            label = {"student": student, "evaluation": names[evaluation_id]}
            if grade is not None:
                before_grades.append({**label, "score": str(grade.score)})
            if score is not None:
                after_grades.append({**label, "score": str(score)})
            if grade is None:
                to_create.append(
                    Grade(
                        evaluation_id=evaluation_id,
                        enrollment_id=enrollment_id,
                        score=score,
                        created_by=actor,
                    )
                )
            elif score is None:
                to_delete.append(grade.pk)
            else:
                grade.score, grade.updated_at = score, now
                to_update.append(grade)
        # Les notes d'une évaluation retirée partent avec elle.
        for (_enrollment_id, evaluation_id), grade in current.items():
            if evaluation_id in removed_ids:
                before_grades.append(
                    {
                        "student": grade.enrollment.student.full_name,
                        "evaluation": names[evaluation_id],
                        "score": str(grade.score),
                    }
                )

        try:
            with transaction.atomic():
                Evaluation.objects.bulk_create(created)
        except IntegrityError:
            # Identifiant déjà pris (autre feuille, autre école).
            raise _invalid("evaluations", _("Unknown evaluation."), "unknown_evaluation") from None
        Evaluation.objects.bulk_update(updated, ["name", "max_score", "order", "updated_at"])
        Grade.objects.filter(pk__in=to_delete).delete()
        Evaluation.objects.filter(pk__in=removed_ids).delete()
        Grade.objects.bulk_create(to_create)
        Grade.objects.bulk_update(to_update, ["score", "updated_at"])

        before = {"evaluations": before_evaluations, "grades": before_grades}
        after = {"evaluations": after_evaluations, "grades": after_grades}
        before = {key: value for key, value in before.items() if value}
        after = {key: value for key, value in after.items() if value}
        if before or after:
            audit.record(
                Action.GRADES_CHANGED,
                course,
                actor=actor,
                before=before or None,
                after=after or None,
                label=f"{course.name} · {course.class_group.name} · {term_label(term)}",
            )
    return sheet(course, term)
