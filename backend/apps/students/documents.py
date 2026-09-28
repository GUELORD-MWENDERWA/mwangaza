"""Fiche d'inscription et liste de classe (D5, M11) : ce que chaque document contient. Le rendu
(aperçu HTML, PDF, Excel) est dans `apps.core.documents`. Frais de l'année et situation des
paiements (2.7) : calculés par `apps.finance.services`."""

from django.conf import settings
from django.db.models import Prefetch
from django.utils.formats import date_format
from django.utils.translation import gettext, ngettext

from apps.accounts.phone import format_phone
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import data_uri, qr_code, school_header, workbook
from apps.core.money import Currency, format_amount
from apps.core.tenancy import require_current_school
from apps.finance import services as finance
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment, Guardian, Student
from apps.students.photos import CONTENT_TYPES as PHOTO_TYPES
from apps.students.photos import photo_kind

PAPERS = ("a4", "a5")
# Colonnes au choix de la liste de classe ; N° et nom toujours présents. `payments` : avec
# `finance.view_reports`, vérifié par l'API.
MATRICULE, SEX_BIRTH, GUARDIAN_PHONE = "matricule", "sex_birth", "guardian_phone"
PAYMENTS = "payments"
COLUMNS = (MATRICULE, SEX_BIRTH, GUARDIAN_PHONE, PAYMENTS)
# Au-delà, les échéances d'un frais (mensuel) sont résumées : « 10 échéances, du 10/09 au 10/06 ».
LISTED_DUE_DATES = 4
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


def _due_dates(days: list) -> str:
    if len(days) <= LISTED_DUE_DATES:
        return ", ".join(date_format(day, "d/m") for day in days)
    return ngettext(
        "%(count)d installment, %(first)s to %(last)s",
        "%(count)d installments, %(first)s to %(last)s",
        len(days),
    ) % {
        "count": len(days),
        "first": date_format(days[0], "d/m"),
        "last": date_format(days[-1], "d/m"),
    }


def _fees(enrollment: Enrollment) -> list[dict]:
    """Frais de l'année de l'élève, après réductions : par devise (dollars d'abord), un frais
    par ligne avec ses échéances, puis le total de la devise."""
    fees = {}
    for charge in finance.charges_of(enrollment.pk):
        if charge.state is None:
            continue
        fee = fees.setdefault(
            (charge.currency, charge.fee_type.name), {"amount_minor": 0, "days": []}
        )
        fee["amount_minor"] += charge.amount_minor - charge.discount_minor
        fee["days"].append(charge.due_on)
    groups = []
    for currency in Currency.values:
        rows = [(name, fee) for (code, name), fee in sorted(fees.items()) if code == currency]
        if rows:
            groups.append(
                {
                    "rows": [
                        {
                            "name": name,
                            "amount": format_amount(fee["amount_minor"], currency),
                            "due_dates": _due_dates(sorted(fee["days"])),
                        }
                        for name, fee in rows
                    ],
                    "total": format_amount(sum(fee["amount_minor"] for _, fee in rows), currency),
                }
            )
    return groups


def registration_form(
    enrollment: Enrollment, *, actor, paper: str, with_code: bool, with_fees: bool, preview: bool
) -> dict:
    """Contenu de la fiche. Le code famille, pour le tuteur principal, n'y est que si
    `with_code` ; chaque PDF qui l'imprime est noté dans le journal d'audit. Les frais de
    l'année, seulement si `with_fees` (droit de lecture des frais, vérifié par l'API)."""
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
        "fees": _fees(enrollment) if with_fees else [],
        "primary_phone": format_phone(str(primary.phone)) if primary and primary.phone else "",
        "portal_url": settings.PORTAL_URL,
        "portal_qr": qr_code(settings.PORTAL_URL) if with_code else "",
        "printed_by": actor.get_full_name(),
    }


def _situation(charges: list) -> str:
    """« À jour », ou le retard dans chaque devise : « En retard : 20,00 $ + 30 000 FC »."""
    overdue = [
        format_amount(item.overdue_minor, item.currency)
        for item in finance.balance(charges).currencies
        if item.overdue_minor
    ]
    if not overdue:
        return gettext("Up to date")
    return gettext("Overdue: %(amounts)s") % {"amounts": " + ".join(overdue)}


def class_list(class_group: ClassGroup, *, columns: list[str], blank_columns: int, order: str):
    """Élèves actifs de la classe (les départs n'y sont pas), NOM POST-NOM Prénom ou matricule ;
    situation des paiements en deux requêtes pour toute la classe."""
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
    enrollments = list(enrollments.order_by(*ordering))
    charges = (
        finance.charges_by_enrollment([enrollment.pk for enrollment in enrollments])
        if PAYMENTS in columns
        else {}
    )
    rows = []
    for number, enrollment in enumerate(enrollments, start=1):
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
                "payments": _situation(charges.get(enrollment.pk, []))
                if PAYMENTS in columns
                else "",
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
    if PAYMENTS in columns:
        headers.append(gettext("Payment status"))
        widths.append(34)
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
        if PAYMENTS in columns:
            cells.append(row["payments"])
        rows.append(cells + [""] * len(context["blank_columns"]))
    return workbook(headers, rows, title=context["class_group"].name, widths=widths)
