"""Notes (8.2.1) : la feuille d'un cours dans une période ou des examens — ses évaluations
(interrogations, devoirs, travaux pratiques : nom et maximum libres) et les notes des élèves de la
classe — se lit et s'enregistre d'un seul envoi.

Note de la période = somme des notes ramenée au maximum de la période (examens : deux fois le
maximum du cours) par une règle de trois, arrondie au dixième (décisions du 2026-10-15) ; calculée,
jamais stockée. Chaque enregistrement qui change quelque chose écrit **une** entrée au journal
(domaine `grades`), avec les seules cases changées.

Carnet de l'enseignant (NB.1, `notebook_access`) : les évaluations d'un cours et leurs notes ne sont
lues et modifiées que par l'**enseignant du cours** ; `grades.enter_any` n'y saisit qu'**un total
par élève** (feuille « total ») ; le directeur des études, le titulaire et tout autre compte n'ont
que la **fiche de cotes** (`totals_sheet`) : le total de chaque élève, une fois la feuille envoyée.
Pas de copie : la fiche est une vue des totaux de la même feuille.

Saisie des points (8.4.0) : selon le réglage de l'école ou du cours, la feuille compte des devoirs
détaillés ou **une seule évaluation « Total »** au maximum de la période (`entry_mode`) ; tout ce
qui suit (note de la période, bulletin, fiches, délibération) lit les évaluations de la même
façon. Une feuille qui a déjà plusieurs évaluations reste détaillée, quel que soit le réglage.

Contrôle (8.2.2) : la feuille est un brouillon, puis envoyée et signée par l'enseignant
(`submit_sheet`, complète ; le directeur des études et le titulaire en sont avertis), puis validée
par le directeur des études (`validate_sheet`, droit `grades.validate`) ou renvoyée avec ses
remarques (`reopen_sheet` : brouillon « rouvert », l'enseignant en est averti). Brouillon : saisie
libre jusqu'à la date limite de la période (`set_deadline`), passée : refusée, sauf feuille rouverte
ou droit `grades.validate`. Envoyée : modifier demande un motif, gardé au journal. Validée :
fermée ; `reopen_sheet` (avec remarques) la renvoie aussi. Tout est dans le journal de la
feuille (`GradeSheet`), que `sheet()` relit comme historique.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Course, Evaluation, Grade, GradeDeadline, GradeSheet
from apps.accounts.models import User
from apps.accounts.roles import GRADES_ENTER, GRADES_ENTER_ANY
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.notifications import events
from apps.schools.grading import DETAILED, TOTALS
from apps.schools.models import Term
from apps.students.models import Enrollment

NOT_GRADED_HERE = ApiError("not_graded_here", _("This course is not graded in this period."), 400)
DEADLINE_PASSED = ApiError(
    "deadline_passed", _("The deadline to enter these grades has passed."), 409
)
SHEET_VALIDATED = ApiError(
    "sheet_validated", _("These grades are validated: ask the director of studies to reopen."), 409
)
SHEET_NOT_DRAFT = ApiError("sheet_not_draft", _("These grades are already sent."), 409)
SHEET_NOT_SENT = ApiError("sheet_not_sent", _("These grades are not waiting for validation."), 409)
INCOMPLETE_SHEET = ApiError(
    "incomplete_sheet", _("Every student needs a grade in every evaluation before sending."), 400
)
TOTALS_ONLY = ApiError(
    "totals_only",
    _("This course is graded with the period total only: a single evaluation at the maximum."),
    400,
)
NOTEBOOK_PRIVATE = ApiError(
    "notebook_private",
    _("The evaluations of this course are kept by its teacher: open its grade sheet instead."),
    403,
)
REASON_REQUIRED = ApiError(
    "reason_required", _("Give the reason for changing grades that are already sent."), 400
)
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


@dataclass(frozen=True)
class HistoryEntry:
    """Une ligne de l'historique de la feuille, tirée du journal."""

    action: str
    at: datetime
    by: str
    reason: str
    changes: int


@dataclass
class Sheet:
    course: Course
    term: Term
    maximum: int
    evaluations: list[Evaluation]
    rows: list[Row]
    entry: str = DETAILED
    status: str = GradeSheet.Status.DRAFT
    reopened: bool = False
    due_on: date | None = None
    submitted_at: datetime | None = None
    submitted_by: str = ""
    validated_at: datetime | None = None
    validated_by: str = ""
    history: list[HistoryEntry] = field(default_factory=list)
    # Renvoyée par le directeur des études (brouillon rouvert) : qui, quand, ses remarques.
    returned: HistoryEntry | None = None


# Accès à la feuille d'un cours (NB.1) : le carnet complet, ou un total par élève.
NOTEBOOK, TOTAL_ONLY = "notebook", "total"


def gradable_courses(user: User, permissions) -> QuerySet[Course]:
    """Cours de l'école courante que `user` voit dans les notes (liste, fiche de cotes, fiche
    imprimée, repêchage) : tous avec `grades.enter_any` ; avec `grades.enter`, ceux qu'il donne et
    ceux de la classe dont il est titulaire. Les évaluations d'un cours : `notebook_access`."""
    courses = Course.objects.filter(is_taught=True)
    if GRADES_ENTER_ANY in permissions:
        return courses
    if GRADES_ENTER in permissions:
        return courses.filter(Q(teacher=user) | Q(class_group__homeroom_teacher=user))
    return courses.none()


def notebook_access(user: User, permissions, course: Course) -> str | None:
    """Ce que `user` fait dans la feuille de `course` (NB.1) : `NOTEBOOK` pour l'enseignant du
    cours (ses évaluations et leurs notes) ; `TOTAL_ONLY` avec `grades.enter_any` (un total par
    élève, pour un enseignant qui rend sa fiche sur papier) ; sinon `None` : le directeur des
    études, le titulaire, le préfet n'ont que la fiche de cotes. Un remplaçant passe par la
    réattribution du cours (charges, 8.1)."""
    if not course.is_taught:
        return None
    if course.teacher_id == user.pk and (
        GRADES_ENTER in permissions or GRADES_ENTER_ANY in permissions
    ):
        return NOTEBOOK
    return TOTAL_ONLY if GRADES_ENTER_ANY in permissions else None


def _detailed(evaluations: list[Evaluation], maximum: int) -> bool:
    """La feuille a des devoirs : plus d'une évaluation, ou une seule sous un autre maximum que
    celui de la période (une seule au maximum, c'est le total lui-même)."""
    return len(evaluations) > 1 or any(e.max_score != maximum for e in evaluations)


def entry_mode(course: Course, evaluation_count: int) -> str:
    """Saisie de la feuille : le choix du cours, sinon celui de l'école (`School.grading`), sauf
    si la feuille a déjà plusieurs évaluations (elle garde ses devoirs : rien n'est perdu en
    silence)."""
    if evaluation_count > 1:
        return DETAILED
    return course.grade_entry or require_current_school().grading["entry"]


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


HISTORY_SHOWN = 30


def _state(course: Course, term: Term) -> GradeSheet | None:
    return (
        GradeSheet.objects.select_related("submitted_by", "validated_by")
        .filter(course=course, term=term)
        .first()
    )


def _history(state: GradeSheet) -> list[HistoryEntry]:
    entries = (
        AuditLog.objects.filter(entity_type=state._meta.label_lower, entity_id=state.pk)
        .select_related("actor")
        .order_by("-created_at")[:HISTORY_SHOWN]
    )
    return [
        HistoryEntry(
            action=entry.action,
            at=entry.created_at,
            by=str(entry.actor) if entry.actor else "",
            reason=(entry.after or {}).get("reason", ""),
            changes=sum(len((entry.after or {}).get(key, [])) for key in ("grades", "evaluations")),
        )
        for entry in entries
    ]


def sheet(course: Course, term: Term, *, total_only: bool = False) -> Sheet:
    """Feuille de notes : évaluations dans l'ordre, élèves actifs de la classe (et ceux partis
    qui ont déjà une note ici) par nom, leurs notes et leur note de la période, son état, sa date
    limite, son historique et les remarques d'un renvoi. Huit requêtes au plus. `total_only`
    (`grades.enter_any`) : une feuille qui a des devoirs est refusée (403 `notebook_private`)."""
    _check_term(course, term)
    evaluations = _evaluations(course, term)
    if total_only and _detailed(evaluations, term_maximum(course, term)):
        raise BusinessError(NOTEBOOK_PRIVATE)
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
    result = Sheet(course, term, maximum, evaluations, list(rows.values()))
    result.entry = TOTALS if total_only else entry_mode(course, len(evaluations))
    deadline = GradeDeadline.objects.filter(term=term).values_list("due_on", flat=True).first()
    result.due_on = deadline
    state = _state(course, term)
    if state is not None:
        result.status, result.reopened = state.status, state.reopened
        result.submitted_at, result.submitted_by = state.submitted_at, str(state.submitted_by or "")
        result.validated_at, result.validated_by = state.validated_at, str(state.validated_by or "")
        result.history = _history(state)
        if state.status == GradeSheet.Status.DRAFT and state.reopened:
            result.returned = _returned(state)
    return result


def _returned(state: GradeSheet) -> HistoryEntry | None:
    entry = (
        AuditLog.objects.filter(
            entity_type=state._meta.label_lower,
            entity_id=state.pk,
            action=Action.GRADES_REOPENED,
        )
        .select_related("actor")
        .order_by("-created_at")
        .first()
    )
    if entry is None:
        return None
    reason = (entry.after or {}).get("reason", "")
    return HistoryEntry(entry.action, entry.created_at, str(entry.actor or ""), reason, 0)


def totals_sheet(course: Course, term: Term) -> Sheet:
    """Fiche de cotes (NB.1) : le total de chaque élève au maximum de la période, sans les
    évaluations ni leurs notes, et seulement une fois la feuille envoyée (avant : son état seul).
    Lue par l'enseignant, le titulaire, `grades.enter_any` et `grades.validate`."""
    result = sheet(course, term)
    result.evaluations = []
    sent = result.status in (GradeSheet.Status.SUBMITTED, GradeSheet.Status.VALIDATED)
    result.rows = result.rows if sent else []
    for row in result.rows:
        row.scores = {}
    return result


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
    reason: str = "",
    may_validate: bool = False,
    total_only: bool = False,
) -> Sheet:
    """Enregistre la feuille d'un seul envoi : évaluations ajoutées ou modifiées (`evaluations`,
    dans l'ordre ; celles qui ne sont pas envoyées restent), retirées avec leurs notes
    (`removed` ; une déjà partie est ignorée), et les seules cases changées (`grades`). Tout est
    vérifié avant d'écrire. Deux enregistrements de la même feuille passent l'un après l'autre ;
    pour une même case, le dernier gagne. Contrôle (8.2.2) : feuille validée : 409
    `sheet_validated` ; date limite passée : 409 `deadline_passed` (sauf feuille rouverte ou
    `may_validate`) ; feuille envoyée : `reason` obligatoire (400 `reason_required`) s'il y a un
    changement. `total_only` (`grades.enter_any`, NB.1) : une feuille qui a des devoirs est
    refusée (403 `notebook_private`), et on n'y met qu'un total."""
    _check_term(course, term)
    with transaction.atomic():
        # Verrou sur le cours : deux envois de la même feuille ne créent pas deux fois une note.
        list(Course.objects.select_for_update().filter(pk=course.pk).order_by().values("pk"))
        state = _state(course, term) or GradeSheet(course=course, term=term, created_by=actor)
        if state.status == GradeSheet.Status.VALIDATED:
            raise BusinessError(SHEET_VALIDATED)
        deadline = GradeDeadline.objects.filter(term=term).values_list("due_on", flat=True).first()
        if (
            deadline is not None
            and deadline < timezone.localdate()
            and not state.reopened
            and not may_validate
        ):
            raise BusinessError(DEADLINE_PASSED)
        reason = reason.strip()
        existing = {evaluation.pk: evaluation for evaluation in _evaluations(course, term)}
        removed_ids = {pk for pk in removed if pk in existing}
        if total_only and _detailed(list(existing.values()), term_maximum(course, term)):
            raise BusinessError(NOTEBOOK_PRIVATE)
        maxima = _plan_evaluations(existing, evaluations, removed_ids)
        if (total_only or entry_mode(course, len(existing)) == TOTALS) and (
            len(maxima) + sum(item.id is None for item in evaluations) != 1
            or any(item.max_score != term_maximum(course, term) for item in evaluations)
        ):
            raise BusinessError(TOTALS_ONLY)
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
        # Objets liés passés tels quels : `bulk_create` ne relit pas l'école de chacun (S.6).
        by_pk = {e.pk: e for e in [*existing.values(), *created]}
        names = {pk: evaluation.name for pk, evaluation in by_pk.items()}

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
                        evaluation=by_pk[evaluation_id],
                        enrollment=students[enrollment_id],
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

        changed = bool(
            before_grades or after_grades or before_evaluations or after_evaluations or removed_ids
        )
        sent = state.status == GradeSheet.Status.SUBMITTED
        if changed and sent and not reason:
            raise BusinessError(REASON_REQUIRED)
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
            if sent:
                after = {**after, "reason": reason}
            if state._state.adding:
                state.save()
            audit.record(
                Action.GRADES_CHANGED,
                state,
                actor=actor,
                before=before or None,
                after=after or None,
                label=_label(course, term),
            )
    return sheet(course, term, total_only=total_only)


def _label(course: Course, term: Term) -> str:
    return f"{course.name} · {course.class_group.name} · {term_label(term)}"


def _locked_state(course: Course, term: Term, actor: User) -> GradeSheet:
    """Feuille de l'état du cours, cours verrouillé (dans une transaction)."""
    list(Course.objects.select_for_update().filter(pk=course.pk).order_by().values("pk"))
    return _state(course, term) or GradeSheet(course=course, term=term, created_by=actor)


def _move(state: GradeSheet, action: str, before: str, after: dict, actor: User, label: str):
    if state._state.adding:
        state.save()
    else:
        state.updated_at = timezone.now()
        state.save()
    audit.record(action, state, actor=actor, before={"status": before}, after=after, label=label)


def submit_sheet(course: Course, term: Term, *, actor: User, total_only: bool = False) -> Sheet:
    """Envoie et signe la fiche de cotes (NB.1 : qui et quand) : au moins une évaluation et une
    note pour chaque élève actif dans chacune (400 `incomplete_sheet`) ; déjà envoyée ou validée :
    409 `sheet_not_draft`. Le directeur des études et le titulaire de la classe en sont avertis."""
    _check_term(course, term)
    with transaction.atomic():
        state = _locked_state(course, term, actor)
        if state.status != GradeSheet.Status.DRAFT:
            raise BusinessError(SHEET_NOT_DRAFT)
        current = sheet(course, term, total_only=total_only)
        active = Enrollment.Status.ACTIVE
        if not current.evaluations or any(
            row.total is None for row in current.rows if row.enrollment.status == active
        ):
            raise BusinessError(INCOMPLETE_SHEET)
        state.status, state.reopened = GradeSheet.Status.SUBMITTED, False
        state.submitted_at, state.submitted_by = timezone.now(), actor
        _move(
            state,
            Action.GRADES_SUBMITTED,
            GradeSheet.Status.DRAFT,
            {"status": state.status},
            actor,
            _label(course, term),
        )
        events.grades_sent(state, actor=actor)
    return sheet(course, term, total_only=total_only)


def validate_sheet(course: Course, term: Term, *, actor: User) -> Sheet:
    """Valide une feuille envoyée (droit `grades.validate`, vérifié par l'API) ; sinon 409
    `sheet_not_sent`."""
    _check_term(course, term)
    with transaction.atomic():
        state = _locked_state(course, term, actor)
        if state.status != GradeSheet.Status.SUBMITTED:
            raise BusinessError(SHEET_NOT_SENT)
        state.status = GradeSheet.Status.VALIDATED
        state.validated_at, state.validated_by = timezone.now(), actor
        _move(
            state,
            Action.GRADES_VALIDATED,
            GradeSheet.Status.SUBMITTED,
            {"status": state.status},
            actor,
            _label(course, term),
        )
    return totals_sheet(course, term)


def reopen_sheet(course: Course, term: Term, *, reason: str, actor: User) -> Sheet:
    """Renvoie une fiche envoyée ou validée à l'enseignant avec les remarques du directeur des
    études (droit `grades.validate`) : brouillon rouvert, que la date limite ne ferme plus ;
    l'enseignant en est averti. Un brouillon : 409 `sheet_not_sent`."""
    _check_term(course, term)
    reason = reason.strip()
    if not reason:
        raise BusinessError(REASON_REQUIRED)
    with transaction.atomic():
        state = _locked_state(course, term, actor)
        if state.status == GradeSheet.Status.DRAFT:
            raise BusinessError(SHEET_NOT_SENT)
        before, sender = state.status, state.submitted_by
        state.status, state.reopened = GradeSheet.Status.DRAFT, True
        state.submitted_at = state.submitted_by = state.validated_at = state.validated_by = None
        _move(
            state,
            Action.GRADES_REOPENED,
            before,
            {"status": state.status, "reason": reason},
            actor,
            _label(course, term),
        )
        events.grades_returned(state, reason, sender=sender, actor=actor)
    return totals_sheet(course, term)


def set_deadline(term: Term, due_on: date | None, *, actor: User) -> None:
    """Date limite de saisie d'une période ou des examens (dernier jour compris) ; vide : plus de
    limite. Droit `grades.validate`, vérifié par l'API."""
    if term.kind not in (Term.Kind.PERIOD, Term.Kind.EXAM):
        raise BusinessError(NOT_GRADED_HERE)
    with transaction.atomic():
        old = GradeDeadline.objects.filter(term=term).first()
        before = old.due_on if old else None
        if before == due_on:
            return
        if due_on is None:
            old.delete()
        elif old is None:
            GradeDeadline.objects.create(term=term, due_on=due_on, created_by=actor)
        else:
            old.due_on, old.updated_at = due_on, timezone.now()
            old.save()
        audit.record(
            Action.GRADES_DEADLINE_SET,
            term,
            actor=actor,
            before={"due_on": str(before)} if before else None,
            after={"due_on": str(due_on)} if due_on else None,
            label=str(term_label(term)),
        )


def awaiting_validation(year) -> list[GradeSheet]:
    """Feuilles envoyées de l'année, les plus anciennes d'abord."""
    return list(
        GradeSheet.objects.filter(
            status=GradeSheet.Status.SUBMITTED, course__class_group__academic_year=year
        )
        .select_related("course__class_group", "term", "submitted_by")
        .order_by("submitted_at")
    )
