"""Fiche d'inscription et liste de classe (D5, M11) : ce que chaque document contient. Le rendu
(aperçu HTML, PDF, Excel) est dans `apps.core.documents`."""

from django.conf import settings
from django.db.models import Prefetch
from django.utils.formats import date_format
from django.utils.translation import gettext

from apps.accounts.phone import format_phone
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import data_uri, school_header, workbook
from apps.core.tenancy import require_current_school
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment, Guardian, Student
from apps.students.photos import CONTENT_TYPES as PHOTO_TYPES
from apps.students.photos import photo_kind

PAPERS = ("a4", "a5")
# Colonnes au choix de la liste de classe ; N° et nom toujours présents.
MATRICULE, SEX_BIRTH, GUARDIAN_PHONE = "matricule", "sex_birth", "guardian_phone"
COLUMNS = (MATRICULE, SEX_BIRTH, GUARDIAN_PHONE)
MAX_BLANK_COLUMNS = 5
BY_NAME, BY_MATRICULE = "name", "matricule"
# L'aperçu montre où sera le code, sans le donner : seul le PDF l'imprime (et le note).
HIDDEN_CODE = "••••-••••"


def _code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}" if len(code) == 8 else code


def _photo(student: Student) -> str:
    if not student.photo:
        return ""
    try:
        with student.photo.open("rb") as file:
            kind = photo_kind(file)
    except OSError:
        return ""
    return data_uri(student.photo, kind, PHOTO_TYPES)


def _address(student: Student) -> str:
    address = student.address or {}
    street = " n° ".join(part for part in (address.get("avenue"), address.get("number")) if part)
    parts = (address.get("commune"), address.get("quartier"), street)
    return ", ".join(part for part in parts if part)


def registration_form(
    enrollment: Enrollment, *, actor, paper: str, with_code: bool, preview: bool
) -> dict:
    """Contenu de la fiche. Le code famille, pour le tuteur principal, n'y est que si
    `with_code` ; chaque PDF qui l'imprime est noté dans le journal d'audit."""
    student = enrollment.student
    family = student.family
    guardians = list(family.guardians.all())
    primary = next((guardian for guardian in guardians if guardian.is_primary), None)
    if with_code and not preview:
        audit.record(
            Action.STUDENTS_FAMILY_CODE_PRINTED,
            family,
            actor=actor,
            label=student.full_name,
        )
    return {
        **school_header(require_current_school()),
        "paper": paper,
        "enrollment": enrollment,
        "student": student,
        "photo": _photo(student),
        "origin": ", ".join(
            part for part in (student.origin_territory, student.origin_province) if part
        ),
        "address": _address(student),
        "guardians": [
            {
                "name": guardian.full_name,
                "relationship": guardian.get_relationship_display(),
                "phone": format_phone(str(guardian.phone)),
                "primary": guardian.is_primary,
                "emergency": guardian.is_emergency_contact,
            }
            for guardian in guardians
        ],
        "family_code": (HIDDEN_CODE if preview else _code(family.code)) if with_code else "",
        "primary_phone": format_phone(str(primary.phone)) if primary and primary.phone else "",
        "portal_url": settings.PORTAL_URL,
        "printed_by": actor.get_full_name(),
    }


def class_list(class_group: ClassGroup, *, columns: list[str], blank_columns: int, order: str):
    """Élèves actifs de la classe (les départs n'y sont pas), NOM POST-NOM Prénom ou matricule."""
    enrollments = Enrollment.objects.filter(
        class_group=class_group, status=Enrollment.Status.ACTIVE
    ).select_related("student__family")
    if GUARDIAN_PHONE in columns:
        enrollments = enrollments.prefetch_related(
            Prefetch(
                "student__family__guardians",
                queryset=Guardian.objects.filter(is_primary=True),
                to_attr="primary_guardians",
            )
        )
    names = ("student__last_name", "student__middle_name", "student__first_name")
    ordering = ("student__matricule", *names) if order == BY_MATRICULE else names
    rows = []
    for number, enrollment in enumerate(enrollments.order_by(*ordering), start=1):
        student = enrollment.student
        guardian = None
        if GUARDIAN_PHONE in columns:
            guardian = next(iter(student.family.primary_guardians), None)
        rows.append(
            {
                "number": number,
                "matricule": student.matricule,
                "surname": " ".join(p for p in (student.last_name, student.middle_name) if p),
                "first_name": student.first_name,
                "sex": student.sex,
                "birth_date": student.birth_date,
                "phone": format_phone(str(guardian.phone)) if guardian and guardian.phone else "",
            }
        )
    teacher = class_group.homeroom_teacher
    return {
        **school_header(require_current_school()),
        "class_group": class_group,
        "year": class_group.academic_year,
        "teacher": teacher.get_full_name() if teacher else "",
        "rows": rows,
        "boys": sum(1 for row in rows if row["sex"] == Student.Sex.MALE),
        "girls": sum(1 for row in rows if row["sex"] == Student.Sex.FEMALE),
        "columns": columns,
        "blank_columns": range(blank_columns),
    }


def class_list_workbook(context: dict) -> bytes:
    """Mêmes colonnes que le PDF ; colonnes vides à droite pour l'appel ou les notes."""
    columns = context["columns"]
    headers = [gettext("No.")]
    widths = [6]
    if MATRICULE in columns:
        headers.append(gettext("Student number"))
        widths.append(18)
    headers.append(gettext("Last name, middle name, first name"))
    widths.append(38)
    if SEX_BIRTH in columns:
        headers += [gettext("Sex"), gettext("Date of birth")]
        widths += [6, 14]
    if GUARDIAN_PHONE in columns:
        headers.append(gettext("Main contact's phone"))
        widths.append(20)
    headers += [""] * len(context["blank_columns"])
    widths += [14] * len(context["blank_columns"])
    rows = []
    for row in context["rows"]:
        cells = [row["number"]]
        if MATRICULE in columns:
            cells.append(row["matricule"])
        cells.append(" ".join(part for part in (row["surname"], row["first_name"]) if part))
        if SEX_BIRTH in columns:
            birth = row["birth_date"]
            cells += [row["sex"], date_format(birth, "d/m/Y") if birth else ""]
        if GUARDIAN_PHONE in columns:
            cells.append(row["phone"])
        rows.append(cells + [""] * len(context["blank_columns"]))
    return workbook(headers, rows, title=context["class_group"].name, widths=widths)
