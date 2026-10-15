"""Bulletin imprimable d'un élève (8.3.2, maquettes `gestion/bulletin*`) : même calcul que
`report_cards.class_report`, mis en page comme le formulaire de l'EPST (cours en lignes, périodes,
examens, totaux de semestre et T.G. en colonnes), avec les places de la classe.

Le QR code ouvre `/v/b/<jeton>` sur l'adresse de l'école : le jeton, signé par le serveur avec un
sel propre à l'école, porte l'inscription, la date et le résultat imprimé (pourcentage, place,
effectif) ; la page publique les montre avec l'élève en initiales
(`verification.verify_report_card`).
Ce que disait le bulletin à la date d'impression : une note corrigée ensuite ne le rend pas faux,
la page l'indique."""

from datetime import date

from django.core import signing
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, gettext
from django.utils.translation import gettext_lazy as _

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
    """« PREMIER SEMESTRE » : le nom du semestre ou du trimestre, sinon son rang dans l'année."""
    if term.name:
        return term.name.upper()
    rank = [g.pk for g in groups if g.kind == term.kind].index(term.pk) + 1
    ranks = {1: gettext("FIRST"), 2: gettext("SECOND"), 3: gettext("THIRD")}
    unit = gettext("SEMESTER") if term.kind == Term.Kind.SEMESTER else gettext("TERM")
    return f"{ranks.get(rank, rank)} {unit}"


# Formulaire officiel (3e HT, scan à 150 ppp) : largeurs en mm de ses colonnes, de gauche à droite.
FORM_WIDTH = 199.5
BRANCH_WIDTH = 40.7
YEAR_WIDTH = 15.1
SPACER_WIDTH = 5.6  # colonne noircie entre le T.G. et le repêchage
RESIT_WIDTHS = (9.6, 21.0)
# Deux semestres de deux périodes, un examen et un total chacun : la structure du formulaire.
STANDARD_KINDS = ["period", "period", "exam", "group"] * 2
STANDARD_WIDTHS = [12.7, 15.2, 15.5, 15.3, 10.1, 10.3, 15.4, 13.1]
BODY_HEIGHT = 154.1  # mm, de la première ligne MAXIMA à la signature du responsable
ROW_HEIGHT = 4.4  # mm, hauteur d'une ligne du formulaire
MAX_ROW_HEIGHT = 9.0
# Peu de cours : la place libre va d'abord sous le cadre (jusqu'à OUTSIDE_FIRST), puis se partage
# entre l'extérieur et l'intérieur du cadre (lignes plus hautes) jusqu'à disparaître.
OUTSIDE_FIRST = 15.0
OUTSIDE_SHARE = 0.4
SHEET_HEIGHT = 279.5  # mm, hauteur du formulaire
FOOTER_ROWS = 7  # maxima généraux, totaux, pourcentage, place, application, conduite, signature


def _ordinal(n: int) -> str:
    """« 1er », « 3e » (français) ou « 1st », « 3rd » (anglais) : la place dans la classe."""
    if (get_language() or "fr").startswith("fr"):
        return f"{n}er" if n == 1 else f"{n}e"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _period_label(n: int) -> str:
    return gettext("1st P.") if n == 1 else gettext("P%(n)d") % {"n": n}


def _headers(report: ClassReport) -> dict:
    """En-tête à trois rangées comme le formulaire : semestres (ou trimestres), « Travail
    journalier » sur les périodes avec examen et total sur deux rangées, puis les périodes ; le
    T.G. s'étend sur les trois."""
    terms = [c.term for c in report.columns if c.kind == "group"]
    cells, year, head2, head3, groups = [], None, [], [], []
    run = 0  # périodes qui se suivent : une seule case « Travail journalier »
    start = periods = 0
    for column in report.columns:
        if column.kind == "year":
            year = {"key": column.key, "label": "T.G."}
            continue
        if column.kind == "group":
            kind, label = "group", gettext("TOT.")
        elif column.term.kind == Term.Kind.EXAM:
            kind, label = "exam", gettext("EXAM.")
        else:
            kind, label = "period", ""
        cells.append({"key": column.key, "kind": kind})
        if kind == "period":
            periods += 1
            run += 1
            head3.append({"label": _period_label(periods)})
            continue
        if run:
            head2.append({"label": gettext("DAILY WORK."), "colspan": run})
            run = 0
        head2.append({"label": label, "rowspan": 2})
        if kind == "group":
            groups.append({"label": _group_label(column.term, terms), "span": len(cells) - start})
            start = len(cells)
    if run:
        head2.append({"label": gettext("DAILY WORK."), "colspan": run})
    if start < len(cells):
        groups.append({"label": "", "span": len(cells) - start})
    standard = [c["kind"] for c in cells] == STANDARD_KINDS and year is not None
    if standard:
        widths = STANDARD_WIDTHS
    else:
        fixed = BRANCH_WIDTH + SPACER_WIDTH + sum(RESIT_WIDTHS) + (YEAR_WIDTH if year else 0)
        free = FORM_WIDTH - fixed
        widths = [round(free / len(cells), 2)] * len(cells)
    return {
        "groups": groups,
        "head2": head2,
        "head3": head3,
        "cells": cells,
        "year_column": year,
        "widths": [*widths, *([YEAR_WIDTH] if year else [])],
    }


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
    """Lignes du tableau : une ligne « Maxima » chaque fois que le groupe de cours change (même
    maximum par période, avec ou sans examen), comme sur le formulaire. Un cours barré (autre
    option) garde sa place dans son groupe, en tirets."""
    lines: list[dict] = []
    ordered = sorted(report.courses, key=lambda c: (c.period_max, not c.has_exam, c.name))
    # Maxima de chaque groupe : ceux de son premier cours suivi (un cours barré n'en a pas).
    group_maxima: dict[tuple, tuple] = {}
    for course in ordered:
        if course.is_taught:
            row = _row(student.cells[course.pk], keys)
            group_maxima.setdefault(
                (course.period_max, course.has_exam), tuple(cell["maximum"] for cell in row)
            )
    previous = None
    for course in ordered:
        group = (course.period_max, course.has_exam)
        if group != previous and group in group_maxima:
            lines.append({"maxima": group_maxima[group]})
            previous = group
        if course.is_taught:
            lines.append({"name": course.name, "cells": _row(student.cells[course.pk], keys)})
        else:
            lines.append({"name": course.name, "struck": True, "cells": [{}] * len(keys)})
    return lines


def _total_rows(student: StudentReport, keys: list[str], size: int) -> dict:
    totals = [student.totals[key] for key in keys]
    return {
        "maximum": [t.maximum for t in totals],
        "score": [t.score for t in totals],
        "percent": [t.percent for t in totals],
        "place": [f"{_ordinal(t.place)}/{size}" if t.place else "" for t in totals],
        "mention": [MENTION_LABELS[t.mention] if t.mention else "" for t in totals],
    }


def student_report(class_group: ClassGroup, enrollment_id) -> tuple[ClassReport, StudentReport]:
    """Le bulletin de la classe et celui de l'élève ; `None` si l'élève n'y est pas inscrit."""
    report = class_report(class_group)
    found = next((s for s in report.students if s.enrollment.pk == enrollment_id), None)
    return report, found


def _state_parts() -> list[list[dict]]:
    """Colonne de droite de la dernière année, comme le formulaire : cinq parties, une ligne de
    texte par ligne du tableau (texte, gras, deux cases `cols` ou cases `boxes`)."""
    return [
        [
            {"cols": (gettext("Points"), gettext("MAX"))},
            {"cols": (gettext("Exam"), "")},
            {"cols": ("%", "")},
        ],
        [
            {"text": gettext("For checking"), "bold": True},
            {"text": gettext("On ...../...../.....")},
            {"text": gettext("The head of the centre")},
        ],
        [{"text": gettext("Centre code")}, {"boxes": range(5)}],
        [
            {"text": gettext("FINAL RESULT"), "bold": True},
            {"text": gettext("Diploma (1)")},
            {"text": gettext("With ......... (%)")},
            {"text": gettext("Failed (1)")},
        ],
        [
            {"text": gettext("As evidence"), "bold": True},
            {"text": gettext("On ...../...../.....")},
            {"text": gettext("The head of the school")},
            {"text": gettext("School seal")},
        ],
    ]


def _state_column(rows: int) -> list[dict]:
    """Une entrée par ligne du tableau : les cinq parties s'espacent sur toutes les lignes sauf la
    dernière (signature du responsable), la dernière partie finit en bas. Quel que soit le nombre
    de cours, aucune ligne n'est ajoutée ni retirée ; trop peu de lignes : le bas est coupé."""
    parts = _state_parts()
    items: list[dict] = [{} for _ in range(rows)]
    available = rows - 1
    free = max(0, available - sum(len(part) for part in parts))
    gaps = len(parts) - 1
    row = 0
    for index, part in enumerate(parts):
        for entry in part:
            if row < available:
                items[row] = entry
            row += 1
        row += free // gaps + (1 if index < free % gaps else 0)
    return items


def _spread(rows: int) -> tuple[float, float]:
    """Hauteur d'une ligne et espace laissé sous le cadre (mm) pour `rows` lignes de tableau : à
    beaucoup de cours, les lignes rétrécissent pour tenir ; à peu de cours, la place libre va sous
    le cadre d'abord, puis aussi dans le cadre, peu à peu, sans changer l'allure du bulletin."""
    free = BODY_HEIGHT - rows * ROW_HEIGHT
    if free <= 0:
        return round(BODY_HEIGHT / rows, 2), 0.0
    outside = min(free, OUTSIDE_FIRST) + max(0.0, free - OUTSIDE_FIRST) * OUTSIDE_SHARE
    inside = min(free - outside, rows * (MAX_ROW_HEIGHT - ROW_HEIGHT))
    return round(ROW_HEIGHT + inside / rows, 2), round(free - inside, 2)


def _signature(kinds: list[str], with_year: bool) -> list[int]:
    """Cases de la ligne « signature du responsable » : une par période, mais l'examen, le total
    du semestre (et le T.G. pour le dernier) se voient en même temps : une seule case."""
    spans: list[int] = []
    for kind in kinds:
        if kind != "period" and spans and spans[-1] < 0:
            spans[-1] -= 1
        else:
            spans.append(1 if kind == "period" else -1)
    spans = [abs(span) for span in spans]
    if with_year:
        if kinds and kinds[-1] != "period":
            spans[-1] += 1
        else:
            spans.append(1)
    return spans


def _boxes(value: str, count: int) -> list[str]:
    """Une case par caractère, sans case vide derrière : la valeur s'imprime telle quelle (au plus
    `count` cases, la largeur du formulaire)."""
    return list(value[:count])


def _code(value: str) -> str:
    """Code de l'école comme sur le formulaire : « 2-610021 »."""
    return f"{value[0]}-{value[1:]}" if len(value) == 7 and value.isdigit() else value


def report_card_document(
    report: ClassReport, student: StudentReport, *, actor, absolute, day: date | None = None
) -> dict:
    """Contenu du PDF A4 du bulletin d'un élève ; `absolute` fait l'adresse complète du QR code."""
    school = require_current_school()
    day = day or timezone.localdate()
    head = _headers(report)
    columns, year = head["cells"], head["year_column"]
    keys = [c["key"] for c in columns] + ([year["key"]] if year else [])
    size = len(report.students)
    person = student.enrollment.student
    class_group = report.class_group
    lines = _body(report, student, keys)
    # Pas de ligne vide : la page reste pleine parce que les lignes (cours, maxima, totaux)
    # s'étirent ; retirer un cours rend sa place à toutes les autres.
    rows = len(lines) + FOOTER_ROWS
    state = _state_column(rows) if class_group.level.has_state_exam else [{}] * rows
    for line, item in zip(lines, state, strict=False):
        line["state"] = item
    row_height, outside = _spread(rows)
    track = class_group.track.name if class_group.track_id else ""
    return {
        **school_header(school),
        "epst_code": _code(school.epst_code),
        "code_boxes": _boxes(_code(school.epst_code), 8),
        "id_boxes": _boxes(person.national_id, 28),
        "perm_boxes": _boxes(person.permanent_number, 15),
        "regime": school.get_regime_display() if school.regime else "",
        "school": school,
        "student": person,
        "class_group": class_group.name,
        "class_title": f"{class_group.level.name} {track}".strip(),
        "state_exam": class_group.level.has_state_exam,
        "year": class_group.academic_year.name,
        "day": day,
        **head,
        "columns": columns,
        "lines": lines,
        "footer_state": state[len(lines) :],
        "row_height": row_height,
        "sheet_height": round(SHEET_HEIGHT - outside, 2),
        "signature": _signature([c["kind"] for c in columns], year is not None),
        "font_size": round(min(9.0, row_height * 2.835 * 0.72), 2),
        "totals": _total_rows(student, keys, size),
        "branch_width": BRANCH_WIDTH,
        "resit_widths": RESIT_WIDTHS,
        "spacer_width": SPACER_WIDTH,
        "qr": qr_code(absolute(verification_path(student, keys, size, day))),
    }
