"""Notes et bulletin d'un enfant sur le Portail (8.8).

Ce que la famille voit :
- les **totaux par cours** de chaque période ou examens dont la feuille est **validée** (jamais les
  devoirs un à un : c'est le carnet de l'enseignant, `grades.py`) ;
- la **décision de passage** dès la proclamation de fin d'année, toujours visible, même quand le
  bulletin est retenu (on ne chasse pas l'enfant) ;
- le **bulletin PDF** d'une période seulement une fois sa délibération proclamée, et sauf retard de
  frais non couvert par une dérogation (`academics/waivers.py`). Une délibération rouverte retire
  le bulletin jusqu'à la nouvelle proclamation.

Même accès que le reste du Portail : l'enfant d'une famille reliée au compte, sinon 404."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound

from apps.academics import deliberation, grades, report_card_documents, report_cards, waivers
from apps.academics.models import Course, Deliberation, Evaluation, Grade, GradeSheet
from apps.accounts.models import User
from apps.core.errors import ApiError, BusinessError
from apps.portal import children
from apps.schools.models import Term
from apps.students.models import Enrollment

REPORT_WITHHELD = ApiError(
    "report_withheld",
    _("The report card is withheld: some fees are overdue. Please contact the school."),
    403,
)
REPORT_NOT_READY = ApiError(
    "report_not_ready",
    _("The report card is not available yet: the results are not proclaimed."),
    409,
)


def released_terms(group) -> set[UUID]:
    """Périodes et examens dont le bulletin est remis aux parents : ceux d'une délibération
    proclamée (la sienne, celle de son semestre, ou celle de la fin d'année pour tous)."""
    proclaimed = set(
        Deliberation.objects.filter(
            class_group=group, status=Deliberation.Status.PROCLAIMED, second_session=False
        ).values_list("term_id", flat=True)
    )
    if not proclaimed:
        return set()
    leaves = [
        t
        for t in Term.objects.filter(academic_year_id=group.academic_year_id)
        if t.kind in (Term.Kind.PERIOD, Term.Kind.EXAM)
    ]
    if None in proclaimed:
        return {t.pk for t in leaves}
    return {t.pk for t in leaves if t.pk in proclaimed or t.parent_id in proclaimed}


def _term_courses(enrollment: Enrollment, courses: list[Course], leaves: list[Term]) -> list:
    """Totaux de l'élève par cours pour chaque période dont la feuille est validée."""
    validated = set(
        GradeSheet.objects.filter(
            course__class_group_id=enrollment.class_group_id,
            status=GradeSheet.Status.VALIDATED,
        ).values_list("course_id", "term_id")
    )
    if not validated:
        return []
    evaluations: dict[tuple, list[Evaluation]] = defaultdict(list)
    for evaluation in Evaluation.objects.filter(course__class_group_id=enrollment.class_group_id):
        evaluations[(evaluation.course_id, evaluation.term_id)].append(evaluation)
    # Pas de jointure : les évaluations de la classe viennent d'être lues (voir `class_report`).
    scores = dict(
        Grade.objects.filter(
            enrollment=enrollment,
            evaluation_id__in=[e.pk for sheet in evaluations.values() for e in sheet],
        ).values_list("evaluation_id", "score")
    )
    result = []
    for term in leaves:
        lines = []
        for course in courses:
            sheet = evaluations.get((course.pk, term.pk), [])
            if (course.pk, term.pk) not in validated or not course.is_taught or not sheet:
                continue
            if term.kind == Term.Kind.EXAM and not course.has_exam:
                continue
            maximum = grades.term_maximum(course, term)
            score = grades.period_score(
                [scores.get(e.pk) for e in sheet], [e.max_score for e in sheet], maximum
            )
            lines.append({"course": course.name, "score": score, "maximum": maximum})
        if lines:
            result.append((term, lines))
    return result


def _decision(group, enrollment: Enrollment) -> dict | None:
    proclaimed = deliberation.proclaimed_rows(group)
    row = proclaimed.rows.get(str(enrollment.pk)) if proclaimed else None
    if row is None or not row.get("decision"):
        return None
    return {
        "decision": row["decision"],
        "resit_courses": row.get("resit_courses", []),
        "held_on": proclaimed.date_of(row),
    }


def child_results(user: User, student_id) -> dict:
    """Notes, décision et état du bulletin de l'enfant (année en cours). Une vingtaine de
    requêtes au plus ; vide dans une école sans le module `academics`."""
    student = children.find_student(user, student_id)
    with children.in_school(student.school):
        enrollment = children._current_enrollment(student)
        group = enrollment.class_group
        data = {
            "id": student.pk,
            "full_name": student.full_name,
            "class_group": group.name,
            "terms": [],
            "decision": None,
            "report_available": False,
            "withheld": False,
        }
        if not student.school.has_module("academics"):
            return data
        released = released_terms(group)
        courses = list(Course.objects.filter(class_group=group).order_by("order", "name"))
        leaves = sorted(
            Term.objects.filter(
                academic_year_id=group.academic_year_id,
                kind__in=[Term.Kind.PERIOD, Term.Kind.EXAM],
            ),
            key=lambda t: (t.parent_id is None, t.order),
        )
        for term, lines in _term_courses(enrollment, courses, leaves):
            complete = len(lines) == sum(
                1 for c in courses if c.is_taught and (term.kind != Term.Kind.EXAM or c.has_exam)
            )
            data["terms"].append(
                {
                    "id": term.pk,
                    "name": grades.term_label(term),
                    "released": term.pk in released,
                    "courses": lines,
                    "total": sum((line["score"] or Decimal(0) for line in lines), Decimal(0))
                    if complete and all(line["score"] is not None for line in lines)
                    else None,
                    "maximum": sum(line["maximum"] for line in lines) if complete else None,
                }
            )
        data["decision"] = _decision(group, enrollment)
        data["withheld"] = bool(released) and waivers.is_withheld(enrollment)
        data["report_available"] = bool(released) and not data["withheld"]
        return data


def report_context(user: User, student_id, *, absolute) -> tuple[dict, str]:
    """Contenu du bulletin PDF de l'élève, limité aux périodes proclamées (les cotes de conduite
    et d'application des autres sont vidées aussi), et son nom de fichier. À appeler et rendre dans
    l'école de l'enfant (`children.in_school`). 403 si retenu, 409 si rien n'est proclamé."""
    student = children.find_student(user, student_id)
    enrollment = children._current_enrollment(student)
    group = enrollment.class_group
    released = released_terms(group) if student.school.has_module("academics") else set()
    if not released:
        raise BusinessError(REPORT_NOT_READY)
    if waivers.is_withheld(enrollment):
        raise BusinessError(REPORT_WITHHELD)
    report = report_cards.class_report(group, released)
    found = next((s for s in report.students if s.enrollment.pk == enrollment.pk), None)
    if found is None:
        raise NotFound
    context = report_card_documents.report_card_document(
        report, found, actor=user, absolute=absolute
    )
    keys = {str(pk) for pk in released}
    columns = context["columns"]
    for line in ("conduct", "application"):
        context[line] = [
            {**cell, "grade": cell["grade"] if column["key"] in keys else ""}
            for cell, column in zip(context[line], columns, strict=False)
        ]
    context["missing_count"] = 0
    return context, f"bulletin-{slugify(student.full_name)}.pdf"
