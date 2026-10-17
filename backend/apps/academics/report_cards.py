"""Calcul du bulletin d'une classe (8.3.1) : notes de chaque période et des examens, totaux du
semestre (ou du trimestre) et de l'année (T.G.), totaux par domaine, pourcentage, place, mention.
Tout est calculé d'après les notes (`grades.period_score`), jamais stocké ; une seule lecture des
notes de la classe, quelle que soit sa taille.

Règles (décisions du 2026-10-15) :
- Une case est « incomplète » (`None`) tant qu'une évaluation n'est pas notée pour
  l'élève, ou que le cours n'a aucune évaluation dans la période : aucun total ne cache un manque.
- Un total n'existe que si toutes ses cases le sont ; sans total, ni pourcentage, ni place.
- Un cours barré (`is_taught` faux, autre option du formulaire) n'est ni noté ni compté dans les
  maxima : le bulletin l'imprime en tirets.
- Un cours sans examen (atelier, laboratoire) n'a pas de case d'examen : son maximum n'y compte pas.
- Place : 1 + nombre d'élèves au total strictement plus haut (ex æquo : même place). Le nombre
  d'élèves est celui de la classe.
- Mention : d'après le pourcentage (`MENTIONS`), échelle à confirmer par l'école (`07` I15).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from apps.academics.grades import period_score, term_maximum
from apps.academics.models import Course, Evaluation, Grade, GradeSheet
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

PERCENT_STEP = Decimal("0.1")
YEAR_KEY = "year"

# Du plus haut au plus bas : (pourcentage minimal, code). Sous le dernier seuil : « insuffisant ».
MENTIONS = (
    (80, "excellent"),
    (70, "very_good"),
    (60, "good"),
    (50, "satisfactory"),
)
INSUFFICIENT = "insufficient"


def mention(percent: Decimal | None) -> str | None:
    if percent is None:
        return None
    return next((code for floor, code in MENTIONS if percent >= floor), INSUFFICIENT)


@dataclass(frozen=True)
class Column:
    """Une colonne du bulletin. `leaf` : une période ou les examens ; `group` : total du
    semestre (ou du trimestre) ; `year` : total général (T.G.). `parts` : les colonnes `leaf`
    additionnées."""

    key: str
    kind: str
    term: Term | None
    parts: tuple[str, ...]


@dataclass(frozen=True)
class Cell:
    """Note ramenée au maximum de la case ; `score` vide : incomplète. Maximum 0 : sans objet."""

    score: Decimal | None
    maximum: int


@dataclass(frozen=True)
class Total:
    score: Decimal | None
    maximum: int
    percent: Decimal | None
    place: int | None
    mention: str | None


@dataclass
class StudentReport:
    enrollment: Enrollment
    # Cours puis colonne.
    cells: dict[UUID, dict[str, Cell]] = field(default_factory=dict)
    # Domaine (« » : cours sans domaine) puis colonne.
    domains: dict[str, dict[str, Cell]] = field(default_factory=dict)
    totals: dict[str, Total] = field(default_factory=dict)


@dataclass
class ClassReport:
    class_group: ClassGroup
    courses: list[Course]
    columns: list[Column]
    students: list[StudentReport]


def columns(year_terms: list[Term]) -> list[Column]:
    """Colonnes de l'année dans l'ordre du bulletin : pour chaque semestre ses périodes, ses
    examens puis son total ; à la fin le T.G. (`year_terms` triés par `order`)."""
    leaves = [t for t in year_terms if t.kind in (Term.Kind.PERIOD, Term.Kind.EXAM)]
    groups = [t for t in year_terms if t.kind in Term.GROUPS]
    result: list[Column] = []
    placed: set[UUID] = set()
    for group in groups:
        children = [t for t in leaves if t.parent_id == group.pk]
        result += [Column(str(t.pk), "leaf", t, (str(t.pk),)) for t in children]
        placed |= {t.pk for t in children}
        result.append(Column(str(group.pk), "group", group, tuple(str(t.pk) for t in children)))
    # Périodes et examens hors de tout semestre.
    for term in leaves:
        if term.pk not in placed:
            result.append(Column(str(term.pk), "leaf", term, (str(term.pk),)))
    leaf_keys = tuple(c.key for c in result if c.kind == "leaf")
    if leaf_keys:
        result.append(Column(YEAR_KEY, "year", None, leaf_keys))
    return result


def _sum(cells: list[Cell]) -> Cell:
    applicable = [c for c in cells if c.maximum]
    maximum = sum(c.maximum for c in applicable)
    if not applicable or any(c.score is None for c in applicable):
        return Cell(None, maximum)
    return Cell(sum((c.score for c in applicable), Decimal(0)), maximum)


def _percent(score: Decimal, maximum: int) -> Decimal:
    return (score * 100 / maximum).quantize(PERCENT_STEP, rounding=ROUND_HALF_UP)


def missing_sheets(class_group: ClassGroup) -> list[tuple[Course, Term]]:
    """Feuilles de notes pas encore validées, pour les périodes et examens déjà commencés dans la
    classe (au moins une évaluation) ; classe sans aucune note : la première période. Le bulletin
    imprimé attend que cette liste soit vide (un cours sans note chez l'enseignant, ou envoyé et
    pas encore validé, ne laisse pas de case vide sur un bulletin remis aux parents)."""
    terms = [
        term
        for term in Term.objects.filter(academic_year_id=class_group.academic_year_id).order_by(
            "order"
        )
        if term.kind in (Term.Kind.PERIOD, Term.Kind.EXAM)
    ]
    started = set(
        Evaluation.objects.filter(course__class_group=class_group).values_list("term_id", flat=True)
    )
    due = [term for term in terms if term.pk in started] or terms[:1]
    validated = set(
        GradeSheet.objects.filter(
            course__class_group=class_group, status=GradeSheet.Status.VALIDATED
        ).values_list("course_id", "term_id")
    )
    courses = Course.objects.filter(class_group=class_group, is_taught=True).order_by(
        "order", "name"
    )
    return [
        (course, term)
        for term in due
        for course in courses
        if (term.kind != Term.Kind.EXAM or course.has_exam)
        and (course.pk, term.pk) not in validated
    ]


def class_report(class_group: ClassGroup) -> ClassReport:
    """Bulletin de toute la classe, pour l'année de la classe (élèves inscrits actifs)."""
    year_terms = list(Term.objects.filter(academic_year_id=class_group.academic_year_id))
    cols = columns(year_terms)
    leaves = {c.key: c for c in cols if c.kind == "leaf"}
    courses = list(Course.objects.filter(class_group=class_group).order_by("order", "name"))
    enrollments = list(
        Enrollment.objects.filter(class_group=class_group, status=Enrollment.Status.ACTIVE)
        .select_related("student")
        .order_by("student__last_name", "student__middle_name", "student__first_name", "pk")
    )

    evaluations: dict[tuple[UUID, UUID], list[Evaluation]] = defaultdict(list)
    for evaluation in Evaluation.objects.filter(course__class_group=class_group):
        evaluations[(evaluation.course_id, evaluation.term_id)].append(evaluation)
    # Sans jointure : les évaluations de la classe viennent d'être lues. Sur une base qui ne
    # connaît pas encore la taille de ses tables (démonstration, tests), la jointure notes →
    # évaluations → cours prenait parfois un plan de 30 s au lieu de quelques millisecondes.
    evaluation_ids = [e.pk for sheet in evaluations.values() for e in sheet]
    scores: dict[tuple[UUID, UUID], Decimal] = {
        (enrollment_id, evaluation_id): score
        for enrollment_id, evaluation_id, score in Grade.objects.filter(
            evaluation_id__in=evaluation_ids, enrollment__in=enrollments
        ).values_list("enrollment_id", "evaluation_id", "score")
    }

    students = []
    for enrollment in enrollments:
        report = StudentReport(enrollment)
        for course in courses:
            row: dict[str, Cell] = {}
            for key, column in leaves.items():
                term = column.term
                if not course.is_taught or (term.kind == Term.Kind.EXAM and not course.has_exam):
                    row[key] = Cell(None, 0)
                    continue
                maximum = term_maximum(course, term)
                sheet = evaluations.get((course.pk, term.pk), [])
                score = period_score(
                    [scores.get((enrollment.pk, e.pk)) for e in sheet],
                    [e.max_score for e in sheet],
                    maximum,
                )
                row[key] = Cell(score, maximum)
            for column in cols:
                if column.kind != "leaf":
                    row[column.key] = _sum([row[k] for k in column.parts])
            report.cells[course.pk] = row
        for domain in {c.domain for c in courses}:
            in_domain = [report.cells[c.pk] for c in courses if c.domain == domain]
            report.domains[domain] = {
                column.key: _sum([row[column.key] for row in in_domain]) for column in cols
            }
        students.append(report)

    for column in cols:
        _rank(column.key, students)
    return ClassReport(class_group, courses, cols, students)


def _rank(key: str, students: list[StudentReport]) -> None:
    """Total, pourcentage, place et mention de chaque élève dans une colonne."""
    sums = {id(student): _sum([row[key] for row in student.cells.values()]) for student in students}
    complete = sorted(
        (cell.score for cell in sums.values() if cell.score is not None), reverse=True
    )
    for student in students:
        cell = sums[id(student)]
        if cell.score is None:
            student.totals[key] = Total(None, cell.maximum, None, None, None)
            continue
        percent = _percent(cell.score, cell.maximum) if cell.maximum else None
        # Les notes sont triées de la plus haute à la plus basse : la première égale donne la place.
        place = complete.index(cell.score) + 1
        student.totals[key] = Total(cell.score, cell.maximum, percent, place, mention(percent))
