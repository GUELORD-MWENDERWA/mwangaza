"""Bulletin imprimable d'un élève (8.3.2, maquettes `gestion/bulletin*`) : même calcul que
`report_cards.class_report`, mis en page comme le formulaire de l'EPST (cours en lignes, périodes,
examens, totaux de semestre et T.G. en colonnes), avec les places de la classe.

Le QR code ouvre `/v/b/<jeton>` sur l'adresse de l'école : le jeton, signé par le serveur avec un
sel propre à l'école, porte l'inscription, la date et le résultat imprimé (pourcentage, place,
effectif) ; la page publique les montre avec l'élève en initiales
(`verification.verify_report_card`).
Ce que disait le bulletin à la date d'impression : une note corrigée ensuite ne le rend pas faux,
la page l'indique."""

from collections import defaultdict
from datetime import date

from django.core import signing
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.academics.grades import term_label
from apps.academics.report_cards import ClassReport, StudentReport, class_report
from apps.core.documents import qr_code, school_header
from apps.core.tenancy import require_current_school
from apps.schools.models import ClassGroup, Term

MENTION_LABELS = {
    "excellent": _("Excellent"),
    "very_good": _("Very good"),
    "good": _("Good"),
    "satisfactory": _("Satisfactory"),
    "insufficient": _("Insufficient"),
}


def _salt() -> str:
    return f"academics.report_card:{require_current_school().pk}"


def _headline(report: StudentReport, order: list[str]):
    """Le dernier total complet (T.G. si l'année est notée, sinon semestre ou période) : ce que
    le QR code garde du bulletin."""
    return next(
        (report.totals[key] for key in reversed(order) if report.totals[key].score is not None),
        None,
    )


def verification_path(report: StudentReport, order: list[str], size: int, day: date) -> str:
    """`/v/b/<jeton>` : inscription, date, pourcentage, place et effectif de la classe."""
    total = _headline(report, order)
    data = {
        "e": str(report.enrollment.pk),
        "d": day.isoformat(),
        "p": str(total.percent) if total and total.percent is not None else None,
        "r": total.place if total else None,
        "n": size,
    }
    token = signing.dumps(data, salt=_salt(), compress=True)
    return reverse("report-card-verification", args=[token])


def read_token(token: str) -> dict | None:
    """Contenu d'un jeton signé pour l'école de l'adresse ; `None` s'il est modifié, illisible ou
    signé pour une autre école."""
    try:
        return signing.loads(token, salt=_salt())
    except signing.BadSignature:
        return None


def _group_label(term: Term, groups: list[Term]) -> str:
    """« Premier semestre » : le nom du semestre ou du trimestre, sinon son rang dans l'année."""
    if term.name:
        return term.name
    rank = [g.pk for g in groups if g.kind == term.kind].index(term.pk) + 1
    if term.kind == Term.Kind.SEMESTER:
        return gettext("Semester %(n)d") % {"n": rank}
    return gettext("Trimester %(n)d") % {"n": rank}


def _headers(report: ClassReport) -> tuple[list[dict], list[dict], dict]:
    """En-tête à deux rangées : groupes (semestre ou trimestre, avec leurs colonnes) puis une
    colonne chacune ; le T.G. s'étend sur les deux rangées."""
    labels = {}
    for column in report.columns:
        if column.kind == "year":
            labels[column.key] = "T.G."
        elif column.kind == "group":
            labels[column.key] = gettext("Total")
        elif column.term.kind == Term.Kind.EXAM:
            labels[column.key] = gettext("Exam")
        else:
            labels[column.key] = term_label(column.term)
    terms = [c.term for c in report.columns if c.kind == "group"]
    groups, cells, year = [], [], {}
    for column in report.columns:
        if column.kind == "year":
            year = {"key": column.key, "label": labels[column.key]}
            continue
        cells.append({"key": column.key, "label": labels[column.key], "kind": column.kind})
    # Un groupe finit par sa colonne de total : ses colonnes sont les précédentes depuis le dernier.
    start = 0
    for index, column in enumerate(c for c in report.columns if c.kind != "year"):
        if column.kind == "group":
            span = index + 1 - start
            groups.append({"label": _group_label(column.term, terms), "span": span})
            start = index + 1
    if start < len(cells):
        groups.append({"label": "", "span": len(cells) - start})
    return groups, cells, year


def _row(cells: dict, keys: list[str]) -> list[dict]:
    result = []
    for key in keys:
        cell = cells[key]
        result.append(
            {
                "score": cell.score,
                "maximum": cell.maximum,
                "low": cell.score is not None and cell.maximum and cell.score * 2 < cell.maximum,
            }
        )
    return result


def _body(report: ClassReport, student: StudentReport, keys: list[str]) -> list[dict]:
    """Lignes du tableau : une ligne « Maxima » chaque fois que les maxima changent d'un cours au
    suivant, comme sur le formulaire."""
    lines: list[dict] = []
    previous = None
    for course in report.courses:
        row = _row(student.cells[course.pk], keys)
        maxima = tuple(cell["maximum"] for cell in row)
        if maxima != previous:
            lines.append({"maxima": maxima})
            previous = maxima
        lines.append({"name": course.name, "cells": row})
    return lines


def _total_rows(student: StudentReport, keys: list[str], size: int) -> dict:
    totals = [student.totals[key] for key in keys]
    return {
        "maximum": [t.maximum for t in totals],
        "score": [t.score for t in totals],
        "percent": [t.percent for t in totals],
        "place": [f"{t.place}/{size}" if t.place else "" for t in totals],
        "mention": [MENTION_LABELS[t.mention] if t.mention else "" for t in totals],
    }


def student_report(class_group: ClassGroup, enrollment_id) -> tuple[ClassReport, StudentReport]:
    """Le bulletin de la classe et celui de l'élève ; `None` si l'élève n'y est pas inscrit."""
    report = class_report(class_group)
    found = next((s for s in report.students if s.enrollment.pk == enrollment_id), None)
    return report, found


def report_card_document(
    report: ClassReport, student: StudentReport, *, actor, absolute, day: date | None = None
) -> dict:
    """Contenu du PDF A4 du bulletin d'un élève ; `absolute` fait l'adresse complète du QR code."""
    school = require_current_school()
    day = day or timezone.localdate()
    groups, columns, year = _headers(report)
    keys = [c["key"] for c in columns] + ([year["key"]] if year else [])
    size = len(report.students)
    person = student.enrollment.student
    class_group = report.class_group
    by_domain: dict[str, int] = defaultdict(int)
    for course in report.courses:
        by_domain[course.domain] += 1
    return {
        **school_header(school),
        "epst_code": school.epst_code,
        "regime": school.get_regime_display() if school.regime else "",
        "student": person,
        "class_group": class_group.name,
        "year": class_group.academic_year.name,
        "day": day,
        "printed_by": actor.get_full_name(),
        "groups": groups,
        "columns": columns,
        "year_column": year,
        "lines": _body(report, student, keys),
        "totals": _total_rows(student, keys, size),
        "qr": qr_code(absolute(verification_path(student, keys, size, day))),
    }
