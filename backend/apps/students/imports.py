"""Import d'une liste d'élèves depuis Excel (.xlsx) ou CSV (D1, `docs/04` § 3).

1. `create_import` lit la première feuille (titres des colonnes, puis chaque ligne en texte),
   devine les colonnes d'après leurs titres (NOM, POSTNOM, DATE NAISS.…) et vérifie les lignes.
2. `update_import` : colonnes et classes choisies à la main, puis nouvelle vérification.
3. `confirm` lance la tâche Celery ; `run` crée familles, tuteurs, élèves et inscriptions d'un
   seul envoi, dans une transaction, avec le matricule de l'école ; une ligne de journal par élève.

Chaque ligne est prête, en avertissement (importée, à vérifier) ou en erreur (pas importée). Un
élève déjà dans l'école (mêmes noms et date de naissance) n'est pas importé : un fichier importé
deux fois ne crée aucun doublon. Fratries : les lignes qui ont le même tuteur (même nom et même
téléphone) forment une famille ; jamais de rattachement à une famille déjà dans l'école (décision
du 2026-09-27).
"""

import csv
import io
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import partial

import openpyxl
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.accounts.phone import InvalidPhoneError, normalize_phone
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.audit.context import current_request_info
from apps.core.documents import workbook
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools import matricule
from apps.schools.models import AcademicYear, ClassGroup, School
from apps.students.models import (
    FAMILY_CODE_ALPHABET,
    FAMILY_CODE_LENGTH,
    Enrollment,
    Family,
    Guardian,
    MatriculeSequence,
    Student,
    StudentImport,
)
from apps.students.services import _student_data

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 40
# Lignes lues au-dessus des titres (nom de l'école, titre de la liste…).
HEADER_SEARCH_ROWS = 10
# Une analyse abandonnée garde des noms d'élèves : effacée après ce délai.
ABANDONED_AFTER = timedelta(days=2)

FIELDS = (
    "last_name",
    "middle_name",
    "first_name",
    "sex",
    "birth_date",
    "birth_place",
    "class_name",
    "matricule",
    "guardian_name",
    "guardian_phone",
)
REQUIRED_FIELDS = ("last_name", "sex", "class_name")
FIELD_LABELS = {
    "last_name": _("Last name"),
    "middle_name": _("Middle name"),
    "first_name": _("First name"),
    "sex": _("Sex (M/F)"),
    "birth_date": _("Date of birth (DD/MM/YYYY)"),
    "birth_place": _("Place of birth"),
    "class_name": _("Class"),
    "matricule": _("Student number"),
    "guardian_name": _("Guardian name"),
    "guardian_phone": _("Guardian phone"),
}
# Titres reconnus (sans accents, espaces ni ponctuation ; ce qui est entre parenthèses ignoré).
_TITLES = {
    "last_name": {"nom", "noms", "nomdeleleve", "nomeleve", "lastname", "surname"},
    "middle_name": {"postnom", "postnoms", "middlename"},
    "first_name": {"prenom", "prenoms", "firstname"},
    "sex": {"sexe", "sex", "genre", "gender", "s"},
    "birth_date": {
        "datedenaissance",
        "datenaissance",
        "datenaiss",
        "datedenaiss",
        "naissance",
        "nele",
        "neele",
        "dn",
        "dateofbirth",
        "birthdate",
    },
    "birth_place": {
        "lieudenaissance",
        "lieunaissance",
        "lieudenaiss",
        "lieunaiss",
        "lieu",
        "ln",
        "placeofbirth",
        "birthplace",
    },
    "class_name": {"classe", "class", "promotion", "classeoption"},
    "matricule": {"matricule", "mat", "numeromatricule", "studentnumber"},
    "guardian_name": {
        "nomdututeur",
        "nomduparent",
        "nomparent",
        "nomtuteur",
        "parent",
        "parents",
        "tuteur",
        "parenttuteur",
        "nomduparenttuteur",
        "responsable",
        "guardianname",
        "guardian",
        "parentname",
    },
    "guardian_phone": {
        "tel",
        "telephone",
        "teldututeur",
        "telephonedututeur",
        "telduparent",
        "telephoneduparent",
        "telparent",
        "teltuteur",
        "contact",
        "gsm",
        "numerodetelephone",
        "guardianphone",
        "parentphone",
        "phone",
    },
}

ERROR, WARNING, INFO = "error", "warning", "info"
ISSUES = {
    "missing_last_name": (ERROR, _("Last name missing")),
    "invalid_sex": (ERROR, _("Sex missing or unknown (M or F)")),
    "invalid_date": (ERROR, _("Invalid date of birth")),
    "missing_class": (ERROR, _("Class missing")),
    "unknown_class": (ERROR, _("Unknown class")),
    "matricule_taken": (ERROR, _("Student number already used in the school")),
    "matricule_repeated": (ERROR, _("Student number repeated (line %(line)s)")),
    "already_in_school": (ERROR, _("Already in the school (same names and date of birth)")),
    "duplicate_in_file": (WARNING, _("Possible duplicate (line %(line)s)")),
    "missing_birth_date": (WARNING, _("Date of birth missing")),
    "invalid_phone": (WARNING, _("Unreadable phone number: guardian kept without phone")),
    "guardian_without_name": (WARNING, _("Phone without guardian name: not kept")),
    "same_family": (INFO, _("Same family as line %(line)s")),
}

FILE_TOO_LARGE = ApiError("file_too_large", _("The file is larger than 5 MB."), 400)
OLD_EXCEL = ApiError(
    "old_excel", _("Old Excel file (.xls): save it as .xlsx in Excel, then try again."), 400
)
UNREADABLE_FILE = ApiError(
    "unreadable_file", _("This file cannot be read: send an Excel (.xlsx) or CSV file."), 400
)
EMPTY_FILE = ApiError("empty_file", _("The file has no student rows."), 400)
TOO_MANY_ROWS = ApiError("too_many_rows", _("The file has more than 5,000 rows."), 400)
IMPORT_CLOSED = ApiError("import_closed", _("This import has already been started."), 409)
NOTHING_TO_IMPORT = ApiError("nothing_to_import", _("No row can be imported."), 409)


# Lecture du fichier


def _key(text) -> str:
    """« Date naiss. (JJ/MM/AAAA) » → « datenaiss » : sans accents, casse ni ponctuation."""
    text = re.sub(r"\(.*?\)", "", str(text))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _text(value) -> str:
    """Cellule en texte ; une date d'Excel au format de la RDC (JJ/MM/AAAA), un nombre sans
    « .0 » (téléphone, matricule)."""
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def _read_xlsx(file) -> tuple[str, list]:
    """Première feuille. La lecture s'arrête après 1 000 lignes vides de suite (une mise en
    forme peut étendre une feuille à un million de lignes) ou au-delà du maximum."""
    try:
        book = openpyxl.load_workbook(file, read_only=True, data_only=True)
        sheet = book.worksheets[0]
        table, filled, empty = [], 0, 0
        for row in sheet.iter_rows(max_col=MAX_COLUMNS, values_only=True):
            cells = [_text(cell) for cell in row]
            table.append(cells)
            empty = 0 if any(cells) else empty + 1
            filled += empty == 0
            if empty > 1000 or filled > MAX_ROWS + HEADER_SEARCH_ROWS:
                break
        return sheet.title, table
    except Exception as error:  # fichier abîmé ou qui n'est pas un classeur
        raise BusinessError(UNREADABLE_FILE) from error


def _read_csv(file) -> list:
    raw = file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel en français sous Windows enregistre le CSV en Windows-1252, avec « ; ».
        text = raw.decode("cp1252", errors="replace")
    delimiter = max((";", ",", "\t"), key=text[:5000].count)
    return [
        [_text(cell) for cell in row[:MAX_COLUMNS]]
        for row in csv.reader(io.StringIO(text), delimiter=delimiter)
    ]


def read_file(file) -> tuple[str, list[str], list]:
    """`(feuille, titres, lignes)` ; chaque ligne : `[numéro dans le fichier, cellules]`. La
    ligne des titres est celle qui en reconnaît le plus parmi les premières (une liste commence
    souvent par le nom de l'école)."""
    name = file.name.lower()
    if file.size > MAX_FILE_SIZE:
        raise BusinessError(FILE_TOO_LARGE)
    if name.endswith(".xls"):
        raise BusinessError(OLD_EXCEL)
    if name.endswith(".csv"):
        sheet, table = "", _read_csv(file)
    elif name.endswith((".xlsx", ".xlsm")):
        sheet, table = _read_xlsx(file)
    else:
        raise BusinessError(UNREADABLE_FILE)
    lines = [(number, cells) for number, cells in enumerate(table, start=1) if any(cells)]
    if len(lines) < 2:
        raise BusinessError(EMPTY_FILE)
    known = set().union(*_TITLES.values())
    top = lines[:HEADER_SEARCH_ROWS]
    position = max(
        range(len(top)), key=lambda i: (sum(_key(cell) in known for cell in top[i][1]), -i)
    )
    headers = lines[position][1]
    rows = [[number, cells] for number, cells in lines[position + 1 :]]
    if not rows:
        raise BusinessError(EMPTY_FILE)
    if len(rows) > MAX_ROWS:
        raise BusinessError(TOO_MANY_ROWS)
    while headers and not headers[-1]:
        headers = headers[:-1]
    return sheet, headers, rows


def guess_mapping(headers: list[str]) -> dict:
    """Champ de l'élève → numéro de la colonne dont le titre est reconnu (ou `None`)."""
    mapping, used = {}, set()
    for name in FIELDS:
        column = next(
            (
                index
                for index, title in enumerate(headers)
                if index not in used and _key(title) in _TITLES[name]
            ),
            None,
        )
        mapping[name] = column
        if column is not None:
            used.add(column)
    return mapping


# Vérification


def _class_key(text: str) -> str:
    """« 3ème Élec. A » et « 3E ELEC A » → « 3eeleca »."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()
    text = re.sub(r"^(\d+)\s*(?:ieme|eme|em|e)\b", r"\1e", text)
    text = re.sub(r"^(\d+)\s*(?:ere|er|re)\b", r"\1re", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _class_keys(groups: list[ClassGroup]) -> dict[str, ClassGroup]:
    """Écritures reconnues de chaque classe : son nom, ou le niveau, le code ou le nom de
    l'option, puis la section (« 3E ELEC A », « 2E ELECTRONIQUE A »). Une écriture qui désigne
    deux classes n'est pas reconnue."""
    found: dict[str, ClassGroup | None] = {}
    for group in groups:
        options = [group.track.code, group.track.name] if group.track_id else [""]
        keys = {_class_key(group.name)}
        keys.update(
            _class_key(f"{group.level.name} {option} {group.section}") for option in options
        )
        for key in keys:
            found[key] = group if found.get(key, group) == group else None
    return {key: group for key, group in found.items() if group is not None}


def _sex(value: str) -> str | None:
    key = _key(value)
    if key in {"m", "masculin", "male", "garcon", "g", "h", "homme"}:
        return Student.Sex.MALE
    if key in {"f", "feminin", "female", "fille", "femme"}:
        return Student.Sex.FEMALE
    return None


def _birth_date(value: str) -> date | None:
    """JJ/MM/AAAA (aussi avec « - » ou « . ») ou AAAA-MM-JJ ; `None` si la date n'existe pas ou
    n'est pas encore passée."""
    for pattern, order in (
        (r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", (3, 2, 1)),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", (1, 2, 3)),
    ):
        found = re.fullmatch(pattern, value.strip())
        if found:
            year, month, day = (int(found.group(index)) for index in order)
            try:
                result = date(year, month, day)
            except ValueError:
                return None
            return result if date(1900, 1, 1) < result < timezone.localdate() else None
    return None


def _phone(value: str) -> str:
    """Numéro E.164 ; Excel efface le 0 du début d'un numéro tapé comme un nombre."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 9 and not value.strip().startswith(("+", "0")):
        value = f"0{digits}"
    return normalize_phone(value)


@dataclass
class _Row:
    line: int
    values: dict
    issues: list = field(default_factory=list)
    student: dict = field(default_factory=dict)
    group: ClassGroup | None = None
    guardian: tuple[str, str] | None = None
    family_line: int | None = None
    family: Family | None = None

    def add(self, code: str, **params) -> None:
        self.issues.append({"code": code, **params})

    @property
    def status(self) -> str:
        levels = {ISSUES[issue["code"]][0] for issue in self.issues}
        return ERROR if ERROR in levels else "warning" if WARNING in levels else "ready"


def _check(imp: StudentImport) -> tuple[dict, list[_Row]]:
    """Rapport de l'import et lignes vérifiées (dans l'école courante)."""
    groups = list(
        ClassGroup.objects.filter(academic_year=imp.academic_year).select_related("level", "track")
    )
    chosen = {str(group.pk): group for group in groups}
    automatic = _class_keys(groups)
    existing = {
        (last.lower(), first.lower(), born)
        for last, first, born in Student.objects.exclude(birth_date=None).values_list(
            "last_name", "first_name", "birth_date"
        )
    }
    taken = set(Student.objects.exclude(matricule="").values_list("matricule", flat=True))
    seen_students: dict[tuple, int] = {}
    seen_matricules: dict[str, int] = {}
    families: dict[tuple, int] = {}
    classes: dict[str, dict] = {}
    rows = []
    for line, cells in imp.rows:
        columns = {name: imp.mapping.get(name) for name in FIELDS}
        values = {
            name: cells[column] if column is not None and column < len(cells) else ""
            for name, column in columns.items()
        }
        row = _Row(line=line, values=values)
        rows.append(row)
        last_name, first_name = values["last_name"], values["first_name"]
        if not last_name:
            row.add("missing_last_name")
        sex = _sex(values["sex"])
        if sex is None:
            row.add("invalid_sex")
        birth = None
        if values["birth_date"]:
            birth = _birth_date(values["birth_date"])
            if birth is None:
                row.add("invalid_date")
        else:
            row.add("missing_birth_date")
        label = values["class_name"]
        if not label:
            row.add("missing_class")
        else:
            row.group = chosen.get(imp.class_mapping.get(label) or "") or automatic.get(
                _class_key(label)
            )
            summary = classes.setdefault(
                label,
                {
                    "label": label,
                    "class_group": str(row.group.pk) if row.group else None,
                    "chosen": label in imp.class_mapping,
                    "rows": 0,
                },
            )
            summary["rows"] += 1
            if row.group is None:
                row.add("unknown_class")
        number = values["matricule"]
        if number in taken:
            row.add("matricule_taken")
        elif number in seen_matricules:
            row.add("matricule_repeated", line=seen_matricules[number])
        elif number:
            seen_matricules[number] = line
        if birth is not None and last_name:
            identity = (last_name.lower(), first_name.lower(), birth)
            if identity in existing:
                row.add("already_in_school")
            elif identity in seen_students:
                row.add("duplicate_in_file", line=seen_students[identity])
            else:
                seen_students[identity] = line
        guardian_name, phone = values["guardian_name"], ""
        if values["guardian_phone"]:
            try:
                phone = _phone(values["guardian_phone"])
            except InvalidPhoneError:
                row.add("invalid_phone")
            if phone and not guardian_name:
                row.add("guardian_without_name")
        if guardian_name:
            row.guardian = (guardian_name, phone)
            if phone:
                family = (_key(guardian_name), phone)
                row.family_line = families.setdefault(family, line)
                if row.family_line != line:
                    row.add("same_family", line=row.family_line)
        row.student = {
            "last_name": last_name[:80],
            "middle_name": values["middle_name"][:80],
            "first_name": first_name[:80],
            "sex": sex,
            "birth_date": birth,
            "birth_place": values["birth_place"][:120],
            "matricule": number[:60],
        }
    counts = {"rows": len(rows), "ready": 0, "warning": 0, "error": 0}
    for row in rows:
        counts[row.status] += 1
    report = {
        "counts": counts,
        "missing_fields": [name for name in REQUIRED_FIELDS if imp.mapping.get(name) is None],
        "classes": sorted(classes.values(), key=lambda item: item["label"]),
        "lines": [
            {"line": row.line, "status": row.status, "issues": row.issues, "values": row.values}
            for row in rows
        ],
    }
    return report, rows


# Service


def create_import(*, actor: User, file, academic_year: AcademicYear) -> StudentImport:
    """Lit le fichier et le vérifie : rien n'est encore créé."""
    require_current_school()
    sheet, headers, rows = read_file(file)
    StudentImport.objects.filter(
        status__in=[StudentImport.Status.ANALYSED, StudentImport.Status.FAILED],
        created_at__lt=timezone.now() - ABANDONED_AFTER,
    ).delete()
    imp = StudentImport(
        academic_year=academic_year,
        file_name=file.name[:255],
        sheet_name=sheet[:100],
        headers=headers,
        rows=rows,
        mapping=guess_mapping(headers),
        created_by=actor,
    )
    imp.report = _check(imp)[0]
    imp.save()
    return imp


def update_import(
    imp: StudentImport, *, mapping: dict | None = None, class_mapping: dict | None = None
) -> StudentImport:
    """Colonnes (champ → numéro de colonne) et classes (classe du fichier → classe de l'année)
    choisies à la main ; une classe vide rend la main au rapprochement automatique."""
    if imp.status != StudentImport.Status.ANALYSED:
        raise BusinessError(IMPORT_CLOSED)
    if mapping is not None:
        columns = [column for column in mapping.values() if column is not None]
        if any(name not in FIELDS for name in mapping) or len(columns) != len(set(columns)):
            raise ValidationError({"mapping": ValidationError(_("Invalid column mapping."))})
        if any(column not in range(len(imp.headers)) for column in columns):
            raise ValidationError({"mapping": ValidationError(_("Unknown column."))})
        imp.mapping = {name: mapping.get(name, imp.mapping.get(name)) for name in FIELDS}
    if class_mapping is not None:
        chosen = {label: value for label, value in class_mapping.items() if value}
        known = {
            str(pk)
            for pk in ClassGroup.objects.filter(
                academic_year=imp.academic_year, pk__in=_uuids(chosen.values())
            ).values_list("pk", flat=True)
        }
        if set(chosen.values()) - known:
            raise ValidationError(
                {"class_mapping": ValidationError(_("Choose a class of this school year."))}
            )
        imp.class_mapping = chosen
    imp.report = _check(imp)[0]
    imp.save()
    return imp


def _uuids(values) -> list[str]:
    """Identifiants bien formés seulement (un texte quelconque ne lève pas d'erreur SQL)."""
    pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    return [value for value in values if isinstance(value, str) and pattern.fullmatch(value)]


def importable_count(imp: StudentImport) -> int:
    counts = imp.report.get("counts", {})
    return counts.get("ready", 0) + counts.get("warning", 0)


def confirm(imp: StudentImport, *, actor: User) -> StudentImport:
    """Lance l'import en tâche de fond, une seule fois."""
    from apps.students import tasks

    with transaction.atomic():
        imp = StudentImport.objects.select_for_update().get(pk=imp.pk)
        if imp.status != StudentImport.Status.ANALYSED:
            raise BusinessError(IMPORT_CLOSED)
        if not importable_count(imp):
            raise BusinessError(NOTHING_TO_IMPORT)
        imp.status = StudentImport.Status.IMPORTING
        imp.save(update_fields=["status", "updated_at"])
        info = current_request_info()
        in_support = info.support_school_id == imp.school_id and info.impersonated_by is not None
        request = {
            "ip": info.ip,
            "user_agent": info.user_agent,
            "impersonated_by": str(info.impersonated_by.pk) if in_support else None,
        }
        transaction.on_commit(
            partial(tasks.run_student_import.delay, str(imp.pk), str(actor.pk), request)
        )
    return imp


def _family_codes(count: int) -> list[str]:
    """`count` codes famille nouveaux, uniques sur toute la plateforme."""
    codes: set[str] = set()
    while len(codes) < count:
        wanted = {
            "".join(secrets.choice(FAMILY_CODE_ALPHABET) for _ in range(FAMILY_CODE_LENGTH))
            for _ in range(count - len(codes))
        }
        wanted -= set(Family.all_schools.filter(code__in=wanted).values_list("code", flat=True))
        codes |= wanted
    return list(codes)


def run(imp: StudentImport, *, actor: User) -> None:
    """Crée ce qui est importable, d'un seul envoi. Les lignes sont vérifiées de nouveau, année
    verrouillée : un élève inscrit à la main entre-temps n'est pas importé en double."""
    with transaction.atomic():
        imp = StudentImport.objects.select_for_update().get(pk=imp.pk)
        if imp.status != StudentImport.Status.IMPORTING:
            return
        year = AcademicYear.objects.select_for_update().get(pk=imp.academic_year_id)
        report, rows = _check(imp)
        rows = [row for row in rows if row.status != ERROR]
        codes = iter(_family_codes(len(rows)))
        families: dict[int, Family] = {}
        guardians = []
        for row in rows:
            key = row.family_line or row.line
            if key not in families:
                families[key] = Family(code=next(codes), created_by=actor)
                if row.guardian:
                    guardians.append(
                        Guardian(
                            family=families[key],
                            full_name=row.guardian[0][:150],
                            phone=row.guardian[1],
                            relationship=Guardian.Relationship.GUARDIAN,
                            is_primary=True,
                            created_by=actor,
                        )
                    )
            row.family = families[key]
        Family.objects.bulk_create(families.values(), batch_size=500)
        Guardian.objects.bulk_create(guardians, batch_size=500)

        template = School.objects.values_list("matricule_format", flat=True).get(pk=imp.school_id)
        sequence, _created = MatriculeSequence.objects.get_or_create(academic_year=year)
        taken = set(Student.objects.exclude(matricule="").values_list("matricule", flat=True))
        students = []
        for row in rows:
            fields = dict(row.student)
            if not fields["matricule"]:
                while True:
                    sequence.last_number += 1
                    fields["matricule"] = matricule.render(
                        template,
                        year=year.starts_on.year,
                        number=sequence.last_number,
                        track_code=row.group.track.code if row.group.track_id else "",
                    )
                    if fields["matricule"] not in taken:
                        break
            taken.add(fields["matricule"])
            students.append(Student(family=row.family, created_by=actor, **fields))
        sequence.save(update_fields=["last_number", "updated_at"])
        Student.objects.bulk_create(students, batch_size=500)
        today = timezone.localdate()
        Enrollment.objects.bulk_create(
            [
                Enrollment(
                    student=student,
                    academic_year=year,
                    class_group=row.group,
                    enrolled_on=today,
                    created_by=actor,
                )
                for row, student in zip(rows, students, strict=True)
            ],
            batch_size=500,
        )
        audit.record_many(
            Action.STUDENTS_STUDENT_IMPORTED,
            [
                (
                    student,
                    {
                        **_student_data(student),
                        "school_year": year.name,
                        "class": row.group.name,
                        "file": imp.file_name,
                    },
                )
                for row, student in zip(rows, students, strict=True)
            ],
            actor=actor,
        )
        # Restent les lignes non importées, pour le rapport ; le reste du fichier est effacé.
        report["lines"] = [line for line in report["lines"] if line["status"] == ERROR]
        imp.report = report
        imp.rows = []
        imp.status = StudentImport.Status.DONE
        imp.created_count = len(students)
        imp.finished_at = timezone.now()
        imp.save()


def fail(imp: StudentImport) -> None:
    StudentImport.objects.filter(pk=imp.pk, status=StudentImport.Status.IMPORTING).update(
        status=StudentImport.Status.FAILED, finished_at=timezone.now()
    )


# Classeurs à télécharger


def template_workbook() -> bytes:
    """Modèle à remplir : une colonne par champ, titres reconnus à l'import."""
    return workbook([str(FIELD_LABELS[name]).upper() for name in FIELDS], [])


def issue_text(issue: dict) -> str:
    return gettext(ISSUES[issue["code"]][1]) % issue


def report_workbook(imp: StudentImport) -> bytes:
    """Lignes à reprendre (erreurs, puis avertissements tant que l'import n'est pas fait), avec
    les colonnes du fichier : corrigées, elles se réimportent telles quelles."""
    lines = [line for line in imp.report.get("lines", []) if line["status"] != "ready"]
    cells = {number: cells for number, cells in imp.rows}
    # Après l'import, le fichier est effacé : ses colonnes sont refaites avec les valeurs gardées.
    fields = {column: name for name, column in imp.mapping.items() if column is not None}
    headers = [gettext("Line"), gettext("Problems"), *imp.headers]
    rows = []
    for line in lines:
        problems = "; ".join(
            issue_text(issue) for issue in line["issues"] if ISSUES[issue["code"]][0] != INFO
        )
        original = cells.get(line["line"]) or [
            line["values"].get(fields.get(index), "") for index in range(len(imp.headers))
        ]
        rows.append([line["line"], problems, *original])
    return workbook(headers, rows)
