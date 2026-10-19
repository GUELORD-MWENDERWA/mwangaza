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

from apps.academics import council as council_module
from apps.academics import deliberation as deliberation_module
from apps.academics import promotion, report_cards, resits
from apps.academics.discipline import DEFAULT_RULES
from apps.academics.grades import term_maximum
from apps.academics.models import (
    ApplicationGrade,
    ConductGrade,
    Course,
    Deliberation,
    DeliberationDecision,
    DeliberationSnapshot,
    DisciplineIncident,
    DisciplineRule,
    Evaluation,
    Grade,
    GradeDeadline,
    GradeSheet,
    PlaceConfirmation,
    ReportCardsReady,
    ResitGrade,
)
from apps.academics.official import BY_KEY, category_of
from apps.accounts.models import User
from apps.accounts.roles import GRADES_VALIDATE
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.schools import organisation
from apps.schools.demo import DEMO_ORGANISATIONS, DemoSpace
from apps.schools.models import AcademicYear, ClassGroup, Term
from apps.schools.organisation import current_year
from apps.students.models import Enrollment, Family

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
                    course.category = category_of(BY_KEY[key], name, exam)
                    # Démonstration : tous les cours sont donnés, même ceux que le formulaire barre
                    # pour l'option, pour que chaque bulletin ait tous ses totaux (décision du
                    # 2026-10-16) ; l'école barre ce qu'elle ne donne pas (`is_taught`).
                    course.is_taught = True
                    # Inventées d'après le maximum : de 1 h (sur 10 ou 20) à 7 h (atelier sur 100).
                    course.weekly_hours = hours or max(1, round(maximum / 15))
                    course.teacher = assigned.get((group.level.name, code, group.section, name))
            Course.objects.bulk_create(created)
            Course.objects.bulk_update(
                updated,
                [
                    "period_max",
                    "has_exam",
                    "is_taught",
                    "order",
                    "weekly_hours",
                    "teacher",
                    "category",
                ],
            )


# Évaluations de la 1re période : nom et part du maximum du cours.
EVALUATIONS = (("Interrogation 1", 0.25), ("Interrogation 2", 0.25), ("Devoir", 0.5))
EMPTY_SHARE = 0.01


def demo_evaluations(school) -> tuple:
    """Évaluations d'une période : trois devoirs, ou le seul total pour une école qui saisit sans
    devoirs (8.4.0)."""
    return (("Total", 1),) if school.grading["entry"] == "totals" else EVALUATIONS


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
            ReportCardsReady.objects.filter(term=first).delete()
            Evaluation.objects.filter(term=first).delete()
            students: dict = defaultdict(list)
            paper = _paper_class(year) if space.profile == "itig" else None
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
                for course in Course.objects.filter(class_group__academic_year=year, is_taught=True)
                .exclude(class_group=paper)
                .order_by("pk")
                for order, (name, share) in enumerate(demo_evaluations(space.school))
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
            _create_demo_homeroom(space, first)
            _create_demo_discipline(first, students, draw)
            if space.profile == "itig":
                _complete_demo_classes(year, students, draw)
            if paper is not None:
                _create_demo_prior_results(paper, year, draw)


# Reprise des résultats (8.4.7) : la 8EB C de l'ITIG tenue sur papier cette année, sans aucune
# note ; la moitié de ses résultats déjà repris (décision et pourcentage), le reste à importer du
# modèle Excel, puis la classe à proclamer.
PAPER_CLASS = ("8EB", "C")


def _paper_class(year) -> ClassGroup | None:
    level, section = PAPER_CLASS
    return ClassGroup.objects.filter(
        academic_year=year, level__name=level, track__isnull=True, section=section
    ).first()


def _create_demo_prior_results(group: ClassGroup, year, draw: random.Random) -> None:
    Deliberation.objects.filter(class_group=group).delete()
    deliberation = Deliberation.objects.create(
        class_group=group, held_on=year.ends_on - timedelta(days=5)
    )
    enrollments = Enrollment.objects.filter(
        class_group=group, status=Enrollment.Status.ACTIVE
    ).order_by("student__last_name", "student__first_name", "pk")
    Decision = DeliberationDecision.Decision
    decisions = []
    for enrollment in list(enrollments)[::2]:
        percent = Decimal(draw.randint(380, 820)) / 10
        decision = Decision.PASS if percent >= 50 else Decision.REPEAT
        decisions.append(
            DeliberationDecision(
                deliberation=deliberation,
                enrollment=enrollment,
                decision=decision,
                prior_percent=percent,
            )
        )
    DeliberationDecision.objects.bulk_create(decisions)


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


def _create_demo_homeroom(space: DemoSpace, term: Term) -> None:
    """Espace du titulaire (NB.3) : dans la classe du titulaire de la démonstration, toutes les
    fiches de la période validées sauf la dernière, envoyée et signée : le directeur des études la
    valide, puis le titulaire déclare les bulletins prêts."""
    level, track, section = DEMO_ORGANISATIONS[space.profile].homeroom_class
    group = ClassGroup.objects.filter(
        academic_year_id=term.academic_year_id,
        level__name=level,
        section=section,
        **({"track__code": track} if track else {"track__isnull": True}),
    ).first()
    if group is None:
        return
    courses = list(
        Course.objects.filter(class_group=group, is_taught=True, evaluations__term=term)
        .distinct()
        .order_by("order", "name")
    )
    GradeSheet.objects.filter(term=term, course__in=courses).delete()
    now = timezone.now()
    GradeSheet.objects.bulk_create(
        GradeSheet(
            course=course,
            term=term,
            status=GradeSheet.Status.SUBMITTED if last else GradeSheet.Status.VALIDATED,
            submitted_at=now - timedelta(days=2),
            submitted_by=course.teacher,
            validated_at=None if last else now - timedelta(days=1),
        )
        for last, course in ((i == len(courses) - 1, c) for i, c in enumerate(courses))
    )


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
        ResitGrade.objects.filter(course__in=courses).delete()
        Deliberation.objects.filter(class_group=group).delete()
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
                for order, (name, share) in enumerate(demo_evaluations(group.school)):
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
        _create_demo_resits(group, draw, now)
        _create_demo_deliberation(group, year, proclaim=group.level.has_state_exam)
        if not group.level.has_state_exam:
            _create_demo_council(group, terms, now)


def _create_demo_resits(group: ClassGroup, draw: random.Random, now) -> None:
    """Repêchage (8.4.1) : un cours échoué sur deux a déjà sa note de repêchage, signée par son
    enseignant ; les autres l'attendent (l'élève est « en repêchage »)."""
    rows = resits.class_overview(report_cards.class_report(group), with_history=False)
    ResitGrade.objects.bulk_create(
        ResitGrade(
            enrollment=student.enrollment,
            course=row.course,
            percent=Decimal(draw.randint(300, 800)) / 10,
            signed_by=row.course.teacher,
        )
        for student in rows
        for row in student.failed
        if row.eligible and row.course.teacher_id and draw.random() < 0.5
    )


def _create_demo_deliberation(group: ClassGroup, year, *, proclaim: bool) -> None:
    """Délibération (8.4.2) : date posée et décision proposée prise pour chaque élève qui en a
    une ; la première classe reste à proclamer (de quoi essayer écart, motif et proclamation).
    La classe de dernière année est proclamée (8.4.4 : situations de la classe et de l'école),
    avec un écart motivé : un élève proposé au repêchage est admis."""
    rows = resits.class_overview(report_cards.class_report(group), with_history=False)
    deliberation = Deliberation.objects.create(
        class_group=group, held_on=year.ends_on - timedelta(days=5)
    )
    proposals = deliberation_module.PROPOSAL
    Decision = DeliberationDecision.Decision
    # Signataire : un membre de l'école qui proclame (direction des études).
    director = User.objects.filter(
        memberships__school=group.school,
        memberships__roles__permissions__contains=[GRADES_VALIDATE],
    ).first()
    proclaim = proclaim and director is not None
    decided = []
    gap = proclaim
    for student in rows:
        proposed = proposals.get(student.outcome, "")
        decision, reason = proposed, ""
        if gap and proposed == Decision.RESIT:
            decision, reason, gap = Decision.PASS, "Excellent en atelier", False
        if proclaim and not decision:
            decision = Decision.DROPPED
        if decision:
            decided.append(
                deliberation_module.StudentRow(
                    student.enrollment,
                    student.percent,
                    student.outcome,
                    proposed,
                    decision,
                    reason,
                    [f.course.name for f in student.failed if f.eligible],
                    student.rule,
                    student.params,
                )
            )
    DeliberationDecision.objects.bulk_create(
        DeliberationDecision(
            deliberation=deliberation,
            enrollment=row.enrollment,
            decision=row.decision,
            proposed=row.proposed,
            reason=row.reason,
        )
        for row in decided
    )
    if not proclaim:
        return
    deliberation.status = Deliberation.Status.PROCLAIMED
    deliberation.version = 1
    deliberation.save(update_fields=["status", "version", "updated_at"])
    DeliberationSnapshot.objects.create(
        deliberation=deliberation,
        version=1,
        held_on=deliberation.held_on,
        proclaimed_at=timezone.now(),
        proclaimed_by=director,
        rows=[deliberation_module._frozen(row) for row in decided],
    )


def _create_demo_council(group: ClassGroup, terms: list[Term], now) -> None:
    """Conseil de délibération (NB.5) : bulletins de chaque période et examen dits prêts, puis la
    1re période délibérée et proclamée, avec ses présents (tous sauf le dernier enseignant),
    président, secrétaire et observations : de quoi imprimer un procès-verbal. La 2e période
    reste à délibérer. Rien au journal, comme le reste de la démonstration."""
    members = council_module.members(group)
    director = next((m for m in members if m.direction), None)
    first = next((t for t in terms if t.kind == Term.Kind.PERIOD), None)
    if director is None or first is None:
        return
    actor = User.objects.get(pk=director.user_id)
    ReportCardsReady.objects.filter(class_group=group).delete()
    ReportCardsReady.objects.bulk_create(
        ReportCardsReady(
            class_group=group,
            term=term,
            declared_by=group.homeroom_teacher or actor,
            declared_at=now + timedelta(seconds=1),
        )
        for term in terms
    )
    present = members[:-1] if len(members) > 2 else members
    secretary = next((m for m in present if m.homeroom), present[-1])
    deliberation = Deliberation.objects.create(
        class_group=group,
        term=first,
        held_on=first.ends_on or timezone.localdate(),
        council={
            "present": [str(m.user_id) for m in present],
            "chair": str(director.user_id),
            "secretary": str(secretary.user_id),
        },
        remarks="Classe sérieuse ; le français reste faible : remédiation avant la 2e période.",
    )
    rows = deliberation_module.session_overview(group, first).rows
    deliberation.status = Deliberation.Status.PROCLAIMED
    deliberation.version = 1
    deliberation.save(update_fields=["status", "version", "updated_at"])
    DeliberationSnapshot.objects.create(
        deliberation=deliberation,
        version=1,
        held_on=deliberation.held_on,
        proclaimed_at=now,
        proclaimed_by=actor,
        rows=[deliberation_module._session_frozen(row) for row in rows],
        council=council_module.frozen(deliberation),
    )


# Conduite (8.5.1a) : la liste proposée et quelques incidents dans la 1re période, pour qu'un
# élève sur dix environ ait déjà des points (de quoi voir les cotes TB à MA).
DEMO_INCIDENT_SHARE = 0.1


def _create_demo_discipline(term: Term, students: dict, draw: random.Random) -> None:
    ConductGrade.objects.filter(term=term).delete()
    ApplicationGrade.objects.filter(term=term).delete()
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
    # Une cote d'application corrigée par le titulaire (8.5.1c), pour voir « corrigée » à l'écran.
    with translation.override(settings.LANGUAGE_CODE):
        reason = gettext("Very attentive in class, grade raised by the homeroom teacher")
    first = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).order_by("pk").first()
    if first is not None:
        ApplicationGrade.objects.create(
            enrollment=first, term=term, grade="TB", reason=reason, corrected_by=author
        )


# Passage de classe (8.4.5) : l'année suivante préparée (classes et barèmes de l'année en cours,
# sans journal), la classe de l'enfant du parent de démonstration proclamée et des places
# proposées à la plupart des élèves, avec des réponses variées ; celle de l'enfant attend sa
# réponse au Portail. Rien n'est inscrit : c'est à essayer.
PROMOTION_DECISIONS = {"pass": 70, "repeat": 14, "resit": 8, "orient": 4, "dropped": 4}
PROMOTION_OUTCOMES = {
    "pass": "passed",
    "repeat": "failed",
    "resit": "resit",
    "orient": "orient",
    "dropped": "incomplete",
}
PERCENTS = {"pass": (52, 86), "repeat": (36, 49), "resit": (45, 50), "orient": (28, 40)}
# Places pas encore proposées ; réponses des parents : une sur huit « ne revient pas », une sur
# trois pas encore, les autres « revient ».
NOT_OFFERED_SHARE = 0.15


def _demo_answer(index: int) -> str:
    return "no" if index % 8 == 3 else "" if index % 3 == 2 else "yes"


def create_demo_promotion(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        if space.profile != "itig":
            continue
        draw = random.Random(f"promotion-{space.school.code}")
        with use_school(space.school):
            year = current_year()
            family = Family.objects.order_by("created_at", "id").first()
            group = _promotion_class(year, family) if year and family else None
            if group is None:
                continue
            following = _next_demo_year(year)
            _proclaim_for_promotion(group, year, family, draw)
            _offer_demo_places(group, following, family, draw)


def _next_demo_year(year: AcademicYear) -> AcademicYear:
    """L'année suivante, créée une fois (découpage du secondaire, classes et barèmes copiés) ;
    ensuite gardée telle que l'école l'a peut-être changée."""
    name = f"{year.starts_on.year + 1}-{year.ends_on.year + 1}"
    following = AcademicYear.objects.filter(name=name).first()
    if following is None:
        following = AcademicYear.objects.create(
            name=name,
            starts_on=year.starts_on.replace(year=year.starts_on.year + 1),
            ends_on=year.ends_on.replace(year=year.ends_on.year + 1),
        )
        organisation._write_terms(
            following, organisation.template_terms(organisation.YearTemplate.SECONDARY), actor=None
        )
        organisation._copy_classes(year, following, actor=None)
        finance.copy_fee_rules(year, following, actor=None)
    return following


def _promotion_class(year, family: Family) -> ClassGroup | None:
    """La classe de l'enfant du compte du portail, sauf une classe déjà prise par une autre
    démonstration (délibération en cours) ou de dernière année ; sinon la première libre."""
    taken = set(
        Deliberation.objects.filter(
            class_group__academic_year=year,
            term__isnull=True,
            second_session=False,
            status=Deliberation.Status.DRAFT,
        ).values_list("class_group_id", flat=True)
    )
    usable = ClassGroup.objects.filter(academic_year=year, level__has_state_exam=False).exclude(
        pk__in=taken
    )
    child = (
        Enrollment.objects.filter(
            academic_year=year, student__family=family, class_group__in=usable
        )
        .order_by("student__birth_date", "pk")
        .first()
    )
    return child.class_group if child else usable.select_related("level", "track").first()


def _proclaim_for_promotion(group: ClassGroup, year, family: Family, draw: random.Random) -> None:
    Deliberation.objects.filter(class_group=group).delete()
    director = User.objects.filter(
        memberships__school=group.school,
        memberships__roles__permissions__contains=[GRADES_VALIDATE],
    ).first()
    if director is None:
        return
    deliberation = Deliberation.objects.create(
        class_group=group,
        held_on=year.ends_on - timedelta(days=5),
        status=Deliberation.Status.PROCLAIMED,
        version=1,
    )
    enrollments = Enrollment.objects.filter(
        class_group=group, status=Enrollment.Status.ACTIVE
    ).select_related("student")
    decisions, rows = [], []
    for enrollment in enrollments.order_by("student__last_name", "student__first_name", "pk"):
        mine = enrollment.student.family_id == family.pk
        decision = (
            "pass"
            if mine
            else draw.choices(list(PROMOTION_DECISIONS), list(PROMOTION_DECISIONS.values()))[0]
        )
        low, high = PERCENTS.get(decision, (None, None))
        percent = Decimal(draw.randint(low * 10, high * 10)) / 10 if low else None
        decisions.append(
            DeliberationDecision(
                deliberation=deliberation,
                enrollment=enrollment,
                decision=decision,
                proposed=decision,
            )
        )
        rows.append(
            {
                "enrollment": str(enrollment.pk),
                "student": enrollment.student.full_name,
                "percent": str(percent) if percent is not None else None,
                "outcome": PROMOTION_OUTCOMES[decision],
                "proposed": decision,
                "decision": decision,
                "reason": "",
                "deviates": False,
                "resit_courses": [],
            }
        )
    DeliberationDecision.objects.bulk_create(decisions)
    DeliberationSnapshot.objects.create(
        deliberation=deliberation,
        version=1,
        held_on=deliberation.held_on,
        proclaimed_at=timezone.now(),
        proclaimed_by=director,
        rows=rows,
    )


def _offer_demo_places(group: ClassGroup, following, family: Family, draw) -> None:
    """Places proposées d'après la décision ; ce que l'école a inscrit en essayant est gardé."""
    PlaceConfirmation.objects.filter(enrollment__class_group=group).exclude(
        status=PlaceConfirmation.Status.ENROLLED
    ).delete()
    now = timezone.now()
    places = []
    for row in promotion.class_passage(group).rows:
        if row.enrolled_class or row.place or row.proposed_class is None:
            continue
        mine = row.enrollment.student.family_id == family.pk
        if not mine and draw.random() < NOT_OFFERED_SHARE:
            continue
        answer = "" if mine else _demo_answer(len(places))
        places.append(
            PlaceConfirmation(
                enrollment=row.enrollment,
                class_group=row.proposed_class,
                answer=answer,
                answered_at=now - timedelta(days=draw.randint(1, 9)) if answer else None,
            )
        )
    PlaceConfirmation.objects.bulk_create(places)
