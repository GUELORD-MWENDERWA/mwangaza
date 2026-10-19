"""Fiches de cotes imprimables (8.3.6, maquette `gestion/notes-fiches`) : fiche d'un cours (notes de
chaque période, des examens et des totaux avec moyenne, plus haute et plus basse note, nombre sous
la moitié), fiche vierge à remplir à la main, tableau de toute la classe pour une colonne du
bulletin (élèves en lignes, cours en colonnes ; servira à la délibération, 8.4).

Tout vient de `report_cards.class_report` (une lecture des notes de la classe, rien de stocké) : une
case incomplète reste vide, une statistique ne compte que les cases remplies."""

from decimal import ROUND_HALF_UP, Decimal

from django.utils.translation import gettext

from apps.academics.models import Course
from apps.academics.report_card_documents import MENTION_LABELS, _period_label
from apps.academics.report_cards import ClassReport, StudentReport
from apps.core.documents import school_header
from apps.core.tenancy import require_current_school
from apps.schools.models import Term

MATRICULE = "matricule"
TOTALS = "totals"
COLUMNS = [MATRICULE, TOTALS]
MAX_BLANK_COLUMNS = 20
AVERAGE_STEP = Decimal("0.1")


def column_labels(report: ClassReport) -> dict[str, str]:
    """Titre court de chaque colonne du bulletin : « 1st P. », « EXAM. », « TOT. 1 », « T.G. »."""
    labels, periods, groups = {}, 0, 0
    for column in report.columns:
        if column.kind == "year":
            labels[column.key] = gettext("T.G.")
        elif column.kind == "group":
            groups += 1
            labels[column.key] = f"{gettext('TOT.')} {groups}"
        elif column.term.kind == Term.Kind.EXAM:
            labels[column.key] = gettext("EXAM.")
        else:
            periods += 1
            labels[column.key] = _period_label(periods)
    return labels


def _name(student: StudentReport) -> dict:
    person = student.enrollment.student
    return {
        "matricule": person.matricule,
        "surname": " ".join(p for p in (person.last_name, person.middle_name) if p),
        "first_name": person.first_name,
    }


def _statistics(scores: list[Decimal], maximum: int) -> dict:
    """Moyenne (au dixième), plus haute et plus basse note, nombre d'élèves sous la moitié."""
    if not scores:
        return {"average": None, "high": None, "low": None, "below": None}
    average = (sum(scores, Decimal(0)) / len(scores)).quantize(AVERAGE_STEP, ROUND_HALF_UP)
    return {
        "average": average,
        "high": max(scores),
        "low": min(scores),
        "below": sum(1 for score in scores if score * 2 < maximum),
    }


def _header(report: ClassReport, *, orientation: str, missing: bool) -> dict:
    group = report.class_group
    teacher = group.homeroom_teacher
    return {
        **school_header(require_current_school()),
        "class_group": group,
        "year": group.academic_year,
        "titular": teacher.get_full_name() if teacher else "",
        "orientation_default": orientation,
        "provisional": missing,
    }


def course_sheet(
    report: ClassReport, course: Course, *, columns: set[str], missing: bool, blank: int | None
) -> dict:
    """Fiche d'un cours ; `blank` : fiche vierge avec ce nombre de colonnes vides (sans notes)."""
    labels = column_labels(report)
    sample = report.students[0].cells[course.pk] if report.students else {}
    shown = [
        {
            "key": column.key,
            "label": labels[column.key],
            "maximum": sample[column.key].maximum,
        }
        for column in report.columns
        if column.key in sample
        and sample[column.key].maximum
        and (column.kind == "leaf" or TOTALS in columns)
    ]
    rows = []
    for number, student in enumerate(report.students, start=1):
        cells = student.cells[course.pk]
        scores = [] if blank is not None else [cells[c["key"]].score for c in shown]
        rows.append({"number": number, **_name(student), "scores": scores})
    statistics = []
    for index, column in enumerate(shown if blank is None else []):
        scores = [row["scores"][index] for row in rows if row["scores"][index] is not None]
        statistics.append(_statistics(scores, column["maximum"]))
    if not any(row["matricule"] for row in rows):
        columns = columns - {MATRICULE}
    teacher = course.teacher
    return {
        **_header(report, orientation="portrait", missing=missing),
        "kind": "blank" if blank is not None else "course",
        "course": course,
        "teacher": teacher.get_full_name() if teacher else "",
        "columns": columns,
        "shown": [] if blank is not None else shown,
        "blank_columns": range(blank or 0),
        "rows": rows,
        "statistics": [] if blank is not None else statistics,
    }


def class_table(report: ClassReport, key: str, *, columns: set[str], missing: bool) -> dict:
    """Tableau de la classe pour la colonne `key` du bulletin : une note par cours, puis le total,
    le pourcentage et la place de chaque élève."""
    labels = column_labels(report)
    shown = []
    for course in report.courses:
        maximum = report.students[0].cells[course.pk][key].maximum if report.students else 0
        if maximum:
            shown.append({"course": course, "maximum": maximum})
    rows = []
    for number, student in enumerate(report.students, start=1):
        total = student.totals[key]
        rows.append(
            {
                "number": number,
                **_name(student),
                "scores": [student.cells[item["course"].pk][key].score for item in shown],
                "total": total,
            }
        )
    if not any(row["matricule"] for row in rows):
        columns = columns - {MATRICULE}
    return {
        **_header(report, orientation="landscape", missing=missing),
        "kind": "class",
        "column_label": labels[key],
        "columns": columns,
        "shown": shown,
        "rows": rows,
        "size": len(rows),
        "maximum": rows[0]["total"].maximum if rows else 0,
    }


def ranking(report: ClassReport, key: str, *, columns: set[str], missing: bool) -> dict:
    """Palmarès de la classe (NB.2) pour la colonne `key` : du premier au dernier, ex æquo à la
    même place (puis par nom) ; les élèves sans total (une note manque) à la fin, non classés."""
    rows = []
    for student in report.students:
        total = student.totals[key]
        rows.append(
            {
                **_name(student),
                "total": total,
                "place": total.place,
                "mention": MENTION_LABELS[total.mention] if total.mention else "",
            }
        )
    rows.sort(key=lambda r: (r["place"] is None, r["place"] or 0, r["surname"], r["first_name"]))
    places = [row["place"] for row in rows if row["place"]]
    for row in rows:
        row["tie"] = bool(row["place"]) and places.count(row["place"]) > 1
    if not any(row["matricule"] for row in rows):
        columns = columns - {MATRICULE}
    return {
        **_header(report, orientation="portrait", missing=missing),
        "kind": "ranking",
        "column_label": column_labels(report)[key],
        "columns": columns,
        "rows": rows,
        "size": len(rows),
        "ranked": len(places),
        "maximum": rows[0]["total"].maximum if rows else 0,
    }
