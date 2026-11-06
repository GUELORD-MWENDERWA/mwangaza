"""Import des points d'une feuille depuis Excel (8.2.4). Le modèle reprend les élèves et les
évaluations de la feuille (identité verrouillée, notes déjà saisies remplies) ; le contrôle lit le
classeur et dit, ligne par ligne, ce qui ne va pas, sans rien écrire. L'enregistrement passe
ensuite par la saisie (`grades.save_sheet`) : mêmes droits, mêmes règles (motif, date limite,
feuille validée), même journal et même notification de l'enseignant."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.utils.text import slugify
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.academics.grades import SHEET_VALIDATED, STEP, EvaluationInput, GradeInput, Sheet
from apps.academics.models import GradeSheet
from apps.core.errors import ApiError, BusinessError
from apps.core.ids import uuid7
from apps.schools.grading import TOTALS
from apps.students import imports

# Une classe a moins de 100 élèves : au-delà, ce n'est pas la fiche d'une classe.
MAX_ROWS = 300
MATRICULE_TITLES = {"matricule", "numeromatricule", "matr", "studentnumber"}
NAME_TITLES = {"nom", "nomcomplet", "eleve", "nometpostnom", "name", "student"}

READY, SKIPPED, ERROR = "ready", "skipped", "error"

NO_GRADE_COLUMN = ApiError(
    "no_grade_column",
    _(
        "No column of this sheet was found in the file: download the template, fill it in, "
        "then send it again."
    ),
    400,
)
TOO_MANY_LINES = ApiError(
    "too_many_lines", _("The file has more than 300 rows: it is not the sheet of a class."), 400
)


@dataclass(frozen=True)
class Column:
    evaluation_id: UUID
    name: str
    max_score: int
    # Saisie « total » sans évaluation encore : créée à l'enregistrement.
    new: bool = False


@dataclass
class Line:
    number: int
    matricule: str
    name: str
    values: list[str]
    enrollment_id: UUID | None = None
    status: str = READY
    issues: list[dict] = field(default_factory=list)

    def refuse(self, code: str, **params) -> None:
        self.status = ERROR
        self.issues.append({"code": code, **params})


@dataclass
class Check:
    columns: list[Column]
    lines: list[Line]
    # Seulement si aucune ligne n'est fausse : les cases qui changent, prêtes pour la saisie.
    grades: list[GradeInput] = field(default_factory=list)
    unchanged: int = 0

    def count(self, status: str) -> int:
        return sum(line.status == status for line in self.lines)

    @property
    def evaluations(self) -> list[EvaluationInput]:
        """Évaluation à créer avec les notes (saisie « total » encore vide)."""
        return [
            EvaluationInput(c.name, c.max_score, c.evaluation_id) for c in self.columns if c.new
        ]


def columns(sheet: Sheet) -> list[Column]:
    """Colonnes du modèle : les évaluations de la feuille ; saisie « total » : le total."""
    if sheet.entry == TOTALS:
        first = sheet.evaluations[0] if sheet.evaluations else None
        if first is None:
            return [Column(uuid7(), gettext("Total"), sheet.maximum, new=True)]
        return [Column(first.pk, first.name, sheet.maximum)]
    return [Column(e.pk, e.name, e.max_score) for e in sheet.evaluations]


def _title(column: Column) -> str:
    return f"{column.name} /{column.max_score}"


def _student_name(enrollment) -> str:
    student = enrollment.student
    return " ".join(p for p in (student.last_name, student.middle_name, student.first_name) if p)


def file_name(sheet: Sheet, term_label: str) -> str:
    parts = (sheet.course.class_group.name, sheet.course.name, term_label)
    return f"points-{slugify(' '.join(parts))}.xlsx"


def template(sheet: Sheet, term_label: str) -> bytes:
    """Classeur à remplir : une ligne de titre, puis matricule et nom (verrouillés), une colonne
    par évaluation avec les notes déjà saisies. La feuille est protégée sans mot de passe : seules
    les cases des notes s'écrivent."""
    import io

    import openpyxl  # chargé à la demande (PERF.8)
    from openpyxl.styles import Font, Protection
    from openpyxl.utils import get_column_letter

    cols = columns(sheet)
    book = openpyxl.Workbook()
    page = book.active
    page.title = slugify(sheet.course.name)[:31] or "points"
    page.append([f"{sheet.course.class_group.name} · {sheet.course.name} · {term_label}"])
    page["A1"].font = Font(bold=True, size=13)
    page.append([gettext("STUDENT NUMBER"), gettext("NAME"), *(_title(c) for c in cols)])
    for cell in page[2]:
        cell.font = Font(bold=True)
    for row in sheet.rows:
        scores = [row.scores.get(c.evaluation_id) for c in cols]
        page.append(
            [
                row.enrollment.student.matricule,
                _student_name(row.enrollment),
                *(float(s) if s is not None else None for s in scores),
            ]
        )
    unlocked = Protection(locked=False)
    for index in range(len(cols)):
        letter = get_column_letter(index + 3)
        page.column_dimensions[letter].width = max(14, len(_title(cols[index])) + 2)
        for number in range(3, len(sheet.rows) + 3):
            page[f"{letter}{number}"].protection = unlocked
    page.column_dimensions["A"].width = 16
    page.column_dimensions["B"].width = 36
    page.freeze_panes = "C3"
    page.protection.sheet = True
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def _score(text: str, maximum: int) -> tuple[Decimal | None, dict | None]:
    """Note lue : un nombre de 0 au maximum, au dixième (virgule acceptée)."""
    try:
        value = Decimal(text.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None, {"code": "invalid_score"}
    rounded = value.quantize(STEP)
    if not value.is_finite() or value < 0 or abs(value - rounded) > Decimal("0.000001"):
        return None, {"code": "invalid_score"}
    if rounded > maximum:
        return None, {"code": "above_maximum", "max": maximum}
    return rounded, None


def check(file, sheet: Sheet) -> Check:
    """Lit le classeur et contrôle chaque ligne, sans rien écrire : élève de la classe reconnu
    par le matricule (à défaut, par le nom exact), une seule fois ; notes au dixième, de 0 au
    maximum de l'évaluation. Une case vide ne change rien. Feuille validée : 409."""
    if sheet.status == GradeSheet.Status.VALIDATED:
        raise BusinessError(SHEET_VALIDATED)
    cols = columns(sheet)
    by_title = {}
    for column in cols:
        by_title.setdefault(imports._key(_title(column)), column)
        by_title.setdefault(imports._key(column.name), column)
    known = MATRICULE_TITLES | NAME_TITLES | set(by_title)
    _page, headers, rows = imports.read_file(file, known)
    if len(rows) > MAX_ROWS:
        raise BusinessError(TOO_MANY_LINES)
    keys = [imports._key(header) for header in headers]
    matricule_at = next((i for i, key in enumerate(keys) if key in MATRICULE_TITLES), None)
    name_at = next((i for i, key in enumerate(keys) if key in NAME_TITLES), None)
    # Une évaluation en double dans le classeur : la première colonne seule compte.
    found: list[tuple[int, Column]] = []
    for index, key in enumerate(keys):
        column = by_title.get(key)
        if column and all(column is not other for _i, other in found):
            found.append((index, column))
    if not found or (matricule_at is None and name_at is None):
        raise BusinessError(NO_GRADE_COLUMN)
    found_columns = [column for _i, column in found]

    by_matricule = {r.enrollment.student.matricule: r for r in sheet.rows}
    by_matricule.pop("", None)
    by_name: dict[str, list] = {}
    for r in sheet.rows:
        by_name.setdefault(imports._key(_student_name(r.enrollment)), []).append(r)

    def cell(cells: list[str], index: int | None) -> str:
        return cells[index].strip() if index is not None and index < len(cells) else ""

    result = Check(found_columns, [])
    taken: dict[UUID, int] = {}
    changes: list[GradeInput] = []
    for number, cells in rows:
        line = Line(
            number,
            cell(cells, matricule_at),
            cell(cells, name_at),
            [cell(cells, i) for i, _c in found],
        )
        result.lines.append(line)
        if line.matricule:
            row = by_matricule.get(line.matricule)
        else:
            same_name = by_name.get(imports._key(line.name), []) if line.name else []
            row = same_name[0] if len(same_name) == 1 else None
        if row is None:
            line.refuse("unknown_student")
            continue
        line.enrollment_id = row.enrollment.pk
        line.name = _student_name(row.enrollment)
        if row.enrollment.pk in taken:
            line.refuse("duplicate_student", line=taken[row.enrollment.pk])
            continue
        taken[row.enrollment.pk] = number
        if not any(line.values):
            line.status = SKIPPED
            continue
        for text, column in zip(line.values, found_columns, strict=True):
            if not text:
                continue
            score, issue = _score(text, column.max_score)
            if issue:
                line.refuse(issue.pop("code"), column=_title(column), value=text, **issue)
            elif score == row.scores.get(column.evaluation_id):
                result.unchanged += 1
            else:
                changes.append(GradeInput(row.enrollment.pk, column.evaluation_id, score))
    if result.count(ERROR) == 0:
        result.grades = changes
    return result
