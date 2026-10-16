"""Cours de démonstration (8.1, `docs/07-a-fournir.md` § 4) : chaque classe reçoit une grille
officielle (`official.py`) d'après son niveau et son option, avec des heures inventées quand la
grille n'en donne pas, et quelques cours ont un enseignant parmi les comptes d'exemple. Rejouable :
les cours de la grille sont remis comme au départ, ceux ajoutés en essayant restent.

Notes (8.2.1) : la 1re période de l'année est notée dans chaque cours (deux interrogations et un
devoir), chaque élève avec son niveau ; quelques cases restent vides (« incomplet »). Rejouable :
la 1re période est remise comme au départ, les autres restent.

Bulletins complets (8.3.4) : deux classes de l'ITIG (une sans Examen d'État, une avec) sont notées
dans tous leurs cours, toutes les périodes et tous les examens, feuilles validées : leur bulletin
n'a aucune case vide et peut s'imprimer. Les autres classes n'ont que la 1re période, à valider."""

import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import gettext

from apps.academics.discipline import DEFAULT_RULES
from apps.academics.grades import term_maximum
from apps.academics.models import (
    ConductGrade,
    Course,
    DisciplineIncident,
    DisciplineRule,
    Evaluation,
    Grade,
    GradeDeadline,
    GradeSheet,
)
from apps.academics.official import BY_KEY
from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.schools.models import ClassGroup, Term
from apps.schools.organisation import current_year
from apps.students.models import Enrollment

# (niveau, code de l'option) → grille ; une classe sans grille connue n'a pas de cours.
BASIC = "basic_education"
TRACK_GRIDS = {"ELEC": "electricity", "MG": "general_mechanics", "MA": "general_mechanics"}

# Compte d'exemple → cours qu'il donne : (niveau, option, section, cours).
TEACHERS = {
    "itig": {
        # L'enseignant des deux écoles, le chef d'atelier, la directrice des études.
        "+243000001008": [
            (level, "ELEC", section, course)
            for level, section in (("1HT", "A"), ("1HT", "B"), ("2HT", "A"))
            for course in ("Mathématique", "Physique")
        ],
        "+243000001010": [
            ("1HT", "ELEC", "A", "Atelier électrique"),
            ("1HT", "ELEC", "B", "Atelier électrique"),
            ("2HT", "ELEC", "A", "Atelier électrique"),
        ],
        "+243000001002": [("1HT", "ELEC", "A", "Français")],
    },
    "volcans": {"+243000001008": [("7e EB", "", "A", "Mathématique")]},
}


def _grid_key(group: ClassGroup) -> str | None:
    if group.level.cycle == group.level.Cycle.BASIC:
        return BASIC
    code = group.track.code if group.track else ""
    if code == "ELO":
        return {"1HT": "electronics_1", "3HT": "electronics_3", "4HT": "electronics_3"}.get(
            group.level.name, "electronics_2"
        )
    return TRACK_GRIDS.get(code)


def create_demo_courses(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        assigned: dict[tuple[str, str, str, str], User] = {}
        for phone, courses in TEACHERS.get(space.profile, {}).items():
            user = User.objects.get(phone=space.numbers.of(phone))
            assigned.update({course: user for course in courses})
        with use_school(space.school):
            year = current_year()
            groups = ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
            existing: dict[tuple, Course] = {
                (course.class_group_id, course.name.casefold()): course
                for course in Course.objects.filter(class_group__academic_year=year)
            }
            created, updated = [], []
            for group in groups:
                key = _grid_key(group)
                if key is None:
                    continue
                code = group.track.code if group.track else ""
                for order, (name, maximum, exam, hours) in enumerate(BY_KEY[key].courses):
                    course = existing.get((group.pk, name.casefold()))
                    if course is None:
                        course = Course(class_group=group, name=name)
                        created.append(course)
                    else:
                        updated.append(course)
                    course.period_max, course.has_exam, course.order = maximum, exam, order
                    # Démonstration : tous les cours sont donnés, même ceux que le formulaire barre
                    # pour l'option, pour que chaque bulletin ait tous ses totaux (décision du
                    # 2026-10-16) ; l'école barre ce qu'elle ne donne pas (`is_taught`).
                    course.is_taught = True
                    # Inventées d'après le maximum : de 1 h (sur 10 ou 20) à 7 h (atelier sur 100).
                    course.weekly_hours = hours or max(1, round(maximum / 15))
                    course.teacher = assigned.get((group.level.name, code, group.section, name))
            Course.objects.bulk_create(created)
            Course.objects.bulk_update(
                updated, ["period_max", "has_exam", "is_taught", "order", "weekly_hours", "teacher"]
            )


# Évaluations de la 1re période : nom et part du maximum du cours.
EVALUATIONS = (("Interrogation 1", 0.25), ("Interrogation 2", 0.25), ("Devoir", 0.5))
EMPTY_SHARE = 0.01


def create_demo_grades(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        draw = random.Random(f"grades-{space.school.code}")
        with use_school(space.school):
            year = current_year()
            first = (
                Term.objects.filter(academic_year=year, kind=Term.Kind.PERIOD)
                .order_by("order")
                .first()
                if year
                else None
            )
            if first is None:
                continue
            # Les notes partent avec leurs évaluations.
            GradeSheet.objects.filter(term=first).delete()
            Evaluation.objects.filter(term=first).delete()
            students: dict = defaultdict(list)
            enrollments = Enrollment.objects.filter(
                academic_year=year, status=Enrollment.Status.ACTIVE
            ).order_by("pk")
            # Inscriptions chargées : `bulk_create` ne relit pas l'école de chaque note.
            for enrollment in enrollments.only("pk", "school_id", "class_group_id"):
                students[enrollment.class_group_id].append(enrollment)
            level = {e.pk: draw.uniform(0.35, 0.95) for group in students.values() for e in group}
            evaluations = [
                Evaluation(
                    course=course,
                    term=first,
                    name=name,
                    max_score=max(1, round(course.period_max * share)),
                    order=order,
                )
                for course in Course.objects.filter(
                    class_group__academic_year=year, is_taught=True
                ).order_by("pk")
                for order, (name, share) in enumerate(EVALUATIONS)
            ]
            Evaluation.objects.bulk_create(evaluations, batch_size=2000)
            grades = []
            for evaluation in evaluations:
                for enrollment in students[evaluation.course.class_group_id]:
                    if draw.random() < EMPTY_SHARE:
                        continue
                    ratio = min(1.0, max(0.0, level[enrollment.pk] + draw.uniform(-0.15, 0.15)))
                    # Au demi-point, comme la plupart des enseignants.
                    halves = round(ratio * evaluation.max_score * 2)
                    grades.append(
                        Grade(
                            evaluation=evaluation, enrollment=enrollment, score=Decimal(halves) / 2
                        )
                    )
            Grade.objects.bulk_create(grades, batch_size=5000)
            _create_demo_control(first)
            _create_demo_discipline(first, students, draw)
            if space.profile == "itig":
                _complete_demo_classes(year, students, draw)


# Contrôle des notes (8.2.2) : quelques feuilles envoyées (à valider) et validées, les autres en
# brouillon, et une date limite encore ouverte.
SENT_SHEETS, VALIDATED_SHEETS = 6, 10


def _create_demo_control(term: Term) -> None:
    GradeDeadline.objects.update_or_create(
        term=term, defaults={"due_on": timezone.localdate() + timedelta(days=14)}
    )
    courses = list(Course.objects.filter(evaluations__term=term).distinct().order_by("pk"))
    now = timezone.now()
    sheets = []
    for position, course in enumerate(courses[: SENT_SHEETS + VALIDATED_SHEETS]):
        validated = position >= SENT_SHEETS
        sheets.append(
            GradeSheet(
                course=course,
                term=term,
                status=GradeSheet.Status.VALIDATED if validated else GradeSheet.Status.SUBMITTED,
                submitted_at=now - timedelta(days=position + 1),
                submitted_by=course.teacher,
                validated_at=now if validated else None,
            )
        )
    GradeSheet.objects.bulk_create(sheets)


def _complete_demo_classes(year, students: dict, draw: random.Random) -> None:
    """Toutes les périodes et tous les examens de deux classes, tous les élèves notés, feuilles
    validées (bulletin imprimable)."""
    groups = sorted(
        ClassGroup.objects.filter(academic_year=year, track__isnull=False).select_related(
            "level", "track"
        ),
        # La 3HT Électronique, classe du bulletin fourni, d'abord.
        key=lambda g: (g.track.code != "ELO" or g.level.name != "3HT", g.level.name, g.name),
    )
    chosen = [
        next((g for g in groups if g.level.has_state_exam is flag and students.get(g.pk)), None)
        for flag in (False, True)
    ]
    terms = list(
        Term.objects.filter(
            academic_year=year, kind__in=(Term.Kind.PERIOD, Term.Kind.EXAM)
        ).order_by("order")
    )
    now = timezone.now()
    for group in filter(None, chosen):
        courses = list(
            Course.objects.filter(class_group=group, is_taught=True).order_by("order", "name")
        )
        enrolled = students[group.pk]
        level = {e.pk: draw.uniform(0.4, 0.92) for e in enrolled}
        GradeSheet.objects.filter(course__in=courses).delete()
        Evaluation.objects.filter(course__in=courses).delete()
        evaluations = []
        for term in terms:
            for course in courses:
                if term.kind == Term.Kind.EXAM:
                    if course.has_exam:
                        evaluations.append(
                            Evaluation(
                                course=course,
                                term=term,
                                name="Examen",
                                max_score=term_maximum(course, term),
                                order=0,
                            )
                        )
                    continue
                for order, (name, share) in enumerate(EVALUATIONS):
                    evaluations.append(
                        Evaluation(
                            course=course,
                            term=term,
                            name=name,
                            max_score=max(1, round(course.period_max * share)),
                            order=order,
                        )
                    )
        Evaluation.objects.bulk_create(evaluations, batch_size=2000)
        grades = []
        for evaluation in evaluations:
            for enrollment in enrolled:
                ratio = min(1.0, max(0.0, level[enrollment.pk] + draw.uniform(-0.15, 0.15)))
                halves = round(ratio * evaluation.max_score * 2)
                grades.append(
                    Grade(evaluation=evaluation, enrollment=enrollment, score=Decimal(halves) / 2)
                )
        Grade.objects.bulk_create(grades, batch_size=5000)
        GradeSheet.objects.bulk_create(
            [
                GradeSheet(
                    course=course,
                    term=term,
                    status=GradeSheet.Status.VALIDATED,
                    submitted_at=now,
                    submitted_by=course.teacher,
                    validated_at=now,
                )
                for term in terms
                for course in courses
                if term.kind != Term.Kind.EXAM or course.has_exam
            ]
        )


# Conduite (8.5.1a) : la liste proposée et quelques incidents dans la 1re période, pour qu'un
# élève sur dix environ ait déjà des points (de quoi voir les cotes TB à MA).
DEMO_INCIDENT_SHARE = 0.1


def _create_demo_discipline(term: Term, students: dict, draw: random.Random) -> None:
    ConductGrade.objects.filter(term=term).delete()
    DisciplineIncident.objects.filter(term=term).delete()
    DisciplineRule.objects.all().delete()
    with translation.override(settings.LANGUAGE_CODE):
        rules = DisciplineRule.objects.bulk_create(
            DisciplineRule(label=gettext(label), points=points, order=order)
            for order, (label, points) in enumerate(DEFAULT_RULES, start=1)
        )
    author = User.objects.filter(phone="+243000001008").first()
    if author is None:
        return
    today = timezone.localdate()
    start = term.starts_on or today - timedelta(days=60)
    span = max(1, (min(term.ends_on or today, today) - start).days)
    incidents = []
    for group in students.values():
        for enrollment in group:
            if draw.random() >= DEMO_INCIDENT_SHARE:
                continue
            for _ in range(draw.choice((1, 1, 2, 3, 6))):
                rule = draw.choice(rules)
                incidents.append(
                    DisciplineIncident(
                        enrollment_id=enrollment.pk,
                        term=term,
                        rule=rule,
                        points=rule.points,
                        occurred_on=start + timedelta(days=draw.randrange(span)),
                        recorded_by=author,
                    )
                )
    DisciplineIncident.objects.bulk_create(incidents, batch_size=2000)
    # Une cote corrigée par le directeur de discipline (8.5.1b), pour voir « corrigée » à l'écran.
    corrected = {i.enrollment_id for i in incidents}
    if corrected:
        with translation.override(settings.LANGUAGE_CODE):
            reason = gettext("Improved behaviour after a talk with the parents")
        ConductGrade.objects.create(
            enrollment_id=sorted(corrected)[0],
            term=term,
            grade="B",
            reason=reason,
            overridden_by=author,
        )
