"""Tableau du directeur des études (NB.2) : pour une période ou des examens, l'état de la fiche de
cotes de chaque cours de chaque classe, et le rappel des enseignants en retard.

État d'un cours (calculé, rien de stocké) : `validated`, `submitted` (envoyée et signée, à
valider), `returned` (renvoyée avec remarques : brouillon rouvert), `in_progress` (au moins une
évaluation, ou un brouillon), `not_started`. Une classe est complète quand toutes ses fiches de la
période sont validées.

Rappel : une notification par enseignant, avec ses cours en retard ; un cours déjà envoyé, sans
enseignant ou déjà rappelé le jour même est ignoré. Chaque rappel est une entrée du journal sur la
période (`grades.reminded`, cours rappelés) : le tableau y lit le dernier rappel de chaque cours,
sans champ en base. Lectures bornées (cinq requêtes), quel que soit le nombre de classes.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.grades import NOT_GRADED_HERE, term_label
from apps.academics.models import Course, Evaluation, GradeSheet
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.notifications import events
from apps.schools.models import AcademicYear, Term

NOT_STARTED, IN_PROGRESS, SUBMITTED, VALIDATED, RETURNED = (
    "not_started",
    "in_progress",
    "submitted",
    "validated",
    "returned",
)
STATUSES = [NOT_STARTED, IN_PROGRESS, SUBMITTED, VALIDATED, RETURNED]
SENT = {GradeSheet.Status.SUBMITTED, GradeSheet.Status.VALIDATED}

NOTIFICATIONS_OFF = ApiError(
    "notifications_off",
    _("Notifications are turned off for this school: nobody can be reminded."),
    409,
)


@dataclass
class BoardCourse:
    id: UUID
    name: str
    teacher_id: UUID | None
    teacher: str
    status: str
    submitted_at: datetime | None
    reminded_at: datetime | None
    reminded_today: bool


@dataclass
class BoardClass:
    id: UUID
    name: str
    homeroom_teacher: str
    courses: list[BoardCourse] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.courses) and all(c.status == VALIDATED for c in self.courses)


def graded_terms(year: AcademicYear) -> list[Term]:
    """Périodes et examens de l'année, dans l'ordre du calendrier."""
    return list(
        Term.objects.filter(
            academic_year=year, kind__in=(Term.Kind.PERIOD, Term.Kind.EXAM)
        ).order_by("order")
    )


def default_term(year: AcademicYear, terms: list[Term]) -> Term | None:
    """La période (ou les examens) du jour d'après ses dates ; sinon la dernière où une note est
    commencée ; sinon la première."""
    today = timezone.localdate()
    dated = next(
        (t for t in terms if t.starts_on and t.ends_on and t.starts_on <= today <= t.ends_on),
        None,
    )
    if dated:
        return dated
    started = set(
        Evaluation.objects.filter(term__academic_year=year).values_list("term_id", flat=True)
    )
    return next((t for t in reversed(terms) if t.pk in started), terms[0] if terms else None)


def _courses(year_id, term: Term) -> list[Course]:
    courses = Course.objects.filter(class_group__academic_year_id=year_id, is_taught=True)
    if term.kind == Term.Kind.EXAM:
        courses = courses.filter(has_exam=True)
    return list(
        courses.select_related(
            "teacher", "class_group__level", "class_group__track", "class_group__homeroom_teacher"
        ).order_by(
            "class_group__level__order",
            "class_group__level__name",
            "class_group__track__name",
            "class_group__section",
            "order",
            "name",
        )
    )


def _reminders(term: Term, since: datetime | None = None) -> dict[str, datetime]:
    """Dernier rappel de chaque cours (identifiant en texte) pour cette période."""
    entries = AuditLog.objects.filter(
        action=Action.GRADES_REMINDED,
        entity_type=term._meta.label_lower,
        entity_id=term.pk,
    )
    if since:
        entries = entries.filter(created_at__gte=since)
    last: dict[str, datetime] = {}
    for created_at, after in entries.order_by("created_at").values_list("created_at", "after"):
        for course in (after or {}).get("courses", []):
            last[course] = created_at
    return last


def _today() -> datetime:
    """Début du jour de l'école : un cours n'est rappelé qu'une fois par jour."""
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def board(term: Term) -> list[BoardClass]:
    """Chaque classe de l'année de `term` et l'état de chacun de ses cours notés dans `term`."""
    courses = _courses(term.academic_year_id, term)
    sheets = {
        row["course_id"]: row
        for row in GradeSheet.objects.filter(term=term, course__in=[c.pk for c in courses]).values(
            "course_id", "status", "reopened", "submitted_at"
        )
    }
    started = set(
        Evaluation.objects.filter(term=term, course__in=[c.pk for c in courses]).values_list(
            "course_id", flat=True
        )
    )
    reminded = _reminders(term)
    today = _today()
    classes: dict[UUID, BoardClass] = {}
    for course in courses:
        group = course.class_group
        entry = classes.get(group.pk)
        if entry is None:
            titular = group.homeroom_teacher
            entry = classes[group.pk] = BoardClass(
                group.pk, group.name, titular.get_full_name() if titular else ""
            )
        sheet = sheets.get(course.pk)
        if sheet and sheet["status"] == GradeSheet.Status.VALIDATED:
            status = VALIDATED
        elif sheet and sheet["status"] == GradeSheet.Status.SUBMITTED:
            status = SUBMITTED
        elif sheet and sheet["reopened"]:
            status = RETURNED
        elif sheet or course.pk in started:
            status = IN_PROGRESS
        else:
            status = NOT_STARTED
        last = reminded.get(str(course.pk))
        entry.courses.append(
            BoardCourse(
                course.pk,
                course.name,
                course.teacher_id,
                course.teacher.get_full_name() if course.teacher else "",
                status,
                sheet["submitted_at"] if status in (SUBMITTED, VALIDATED) else None,
                last,
                bool(last and last >= today),
            )
        )
    return list(classes.values())


def remind(term: Term, courses: list[Course], *, actor: User) -> dict[str, int]:
    """Rappelle aux enseignants les fiches de `courses` pas encore envoyées pour `term` : une
    notification par enseignant. Rend le nombre d'enseignants avertis, de cours rappelés et de
    cours ignorés (envoyés, sans enseignant, d'une autre année ou déjà rappelés aujourd'hui).
    Droit `grades.validate`, vérifié par l'API ; 409 `notifications_off` sans le module."""
    if not require_current_school().has_module("notifications"):
        raise BusinessError(NOTIFICATIONS_OFF)
    if term.kind not in (Term.Kind.PERIOD, Term.Kind.EXAM):
        raise BusinessError(NOT_GRADED_HERE)
    with transaction.atomic():
        # Deux clics en même temps : le second attend le premier et ne rappelle personne.
        list(Term.objects.select_for_update().filter(pk=term.pk).values("pk"))
        already = _reminders(term, since=_today())
        sent = set(
            GradeSheet.objects.filter(term=term, course__in=courses, status__in=SENT).values_list(
                "course_id", flat=True
            )
        )
        due = [
            course
            for course in courses
            if course.teacher_id
            and course.is_taught
            and course.class_group.academic_year_id == term.academic_year_id
            and (term.kind != Term.Kind.EXAM or course.has_exam)
            and course.pk not in sent
            and str(course.pk) not in already
        ]
        by_teacher: dict[UUID, list[Course]] = defaultdict(list)
        for course in due:
            by_teacher[course.teacher_id].append(course)
        notified = events.grades_reminders(by_teacher, term) if due else 0
        if due:
            audit.record(
                Action.GRADES_REMINDED,
                term,
                actor=actor,
                after={"courses": [str(course.pk) for course in due]},
                label=str(term_label(term)),
            )
    return {"notified": notified, "reminded": len(due), "skipped": len(courses) - len(due)}
