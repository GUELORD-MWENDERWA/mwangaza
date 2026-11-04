"""Export complet des données d'une école (CON.2, S.7) : remis à l'école qui part, ou sur sa
demande. Un classeur Excel (une feuille par sujet), fait en tâche de fond, gardé 7 jours derrière
un lien signé qu'on envoie à l'école, puis effacé.

Le PDF de la tâche d'origine est écarté : il ne dirait rien de plus que le classeur, mais pèserait
des centaines de pages pour 1 200 élèves (décision notée au journal de `03`).

Isolation : tout est lu dans l'école de l'export (`use_school`), jamais ailleurs. Écriture en flux
(`write_only`) : la mémoire ne dépend pas de la taille de l'école."""

import logging
from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.academics.models import Grade
from apps.core.tenancy import use_school
from apps.finance.models import Payment, StudentCharge
from apps.schools.models import School, SchoolExport
from apps.students.models import Enrollment, Guardian, Student

logger = logging.getLogger(__name__)

VALID_DAYS = 7
SALT = "school-export"


def request_export(school: School, *, actor) -> SchoolExport:
    """Une demande d'export, à exécuter en tâche de fond (`tasks.build_export`)."""
    return SchoolExport.objects.create(school=school, created_by=actor)


def token(export: SchoolExport) -> str:
    return TimestampSigner(salt=SALT).sign(str(export.pk))


def resolve(signed: str) -> SchoolExport | None:
    """L'export d'un lien encore valable (signature juste, moins de 7 jours, fichier prêt), sinon
    `None`. Un lien périmé efface le fichier au passage."""
    try:
        pk = TimestampSigner(salt=SALT).unsign(signed, max_age=timedelta(days=VALID_DAYS))
    except SignatureExpired:
        pk = TimestampSigner(salt=SALT).unsign(signed)
        expire(SchoolExport.objects.filter(pk=pk).first())
        return None
    except BadSignature:
        return None
    export = SchoolExport.objects.filter(pk=pk, state=SchoolExport.State.READY).first()
    if export is None or export.expires_at < timezone.now():
        expire(export)
        return None
    return export


def expire(export: SchoolExport | None) -> None:
    if export is None or export.state == SchoolExport.State.EXPIRED:
        return
    if export.file:
        export.file.delete(save=False)
    export.state = SchoolExport.State.EXPIRED
    export.save(update_fields=["state", "file", "updated_at"])


def purge() -> int:
    """Efface les fichiers périmés (chaque nuit) ; rend leur nombre."""
    late = SchoolExport.objects.filter(
        state=SchoolExport.State.READY, expires_at__lt=timezone.now()
    )
    count = 0
    for export in late:
        expire(export)
        count += 1
    return count


def _sheets(school: School):
    """(titre, en-têtes, lignes) de chaque feuille ; lignes lues en flux depuis l'école."""
    students = Student.objects.select_related("family").order_by("last_name", "first_name")
    yield (
        _("Students"),
        [_("Number"), _("Name"), _("Sex"), _("Date of birth"), _("Place of birth"), _("Family")],
        (
            [s.matricule, s.full_name, s.sex, s.birth_date, s.birth_place, s.family.code]
            for s in students.iterator(chunk_size=500)
        ),
    )
    enrollments = Enrollment.objects.select_related(
        "student", "academic_year", "class_group__level"
    ).order_by("academic_year__name", "student__last_name")
    yield (
        _("Enrollments"),
        [_("Number"), _("Name"), _("Year"), _("Class"), _("Status"), _("Enrolled on")],
        (
            [
                e.student.matricule,
                e.student.full_name,
                e.academic_year.name,
                str(e.class_group),
                e.status,
                e.enrolled_on,
            ]
            for e in enrollments.iterator(chunk_size=500)
        ),
    )
    guardians = Guardian.objects.select_related("family").order_by("family__code")
    yield (
        _("Guardians"),
        [_("Family"), _("Name"), _("Relationship"), _("Phone"), _("Email")],
        (
            [g.family.code, g.full_name, g.relationship, str(g.phone or ""), g.email]
            for g in guardians.iterator(chunk_size=500)
        ),
    )
    charges = StudentCharge.objects.select_related("enrollment__student").order_by("due_on")
    yield (
        _("Fees due"),
        [_("Number"), _("Name"), _("Label"), _("Amount"), _("Currency"), _("Due date")],
        (
            [
                c.enrollment.student.matricule,
                c.enrollment.student.full_name,
                c.label,
                c.amount_minor,
                c.currency,
                c.due_on,
            ]
            for c in charges.iterator(chunk_size=500)
        ),
    )
    payments = Payment.objects.select_related("enrollment__student", "cancellation").order_by(
        "paid_at"
    )
    yield (
        _("Payments"),
        [
            _("Receipt"),
            _("Date"),
            _("Number"),
            _("Name"),
            _("Amount"),
            _("Currency"),
            _("Rate"),
            _("Cancelled"),
        ],
        (
            [
                p.receipt_number,
                timezone.localtime(p.paid_at).replace(tzinfo=None),
                p.enrollment.student.matricule,
                p.enrollment.student.full_name,
                p.received_amount_minor,
                p.received_currency,
                float(p.rate_used) if p.rate_used is not None else None,
                _("Yes") if hasattr(p, "cancellation") else "",
            ]
            for p in payments.iterator(chunk_size=500)
        ),
    )
    grades = Grade.objects.select_related(
        "evaluation__course", "evaluation__term", "enrollment__student"
    ).order_by("enrollment__student__last_name")
    yield (
        _("Grades"),
        [_("Number"), _("Name"), _("Term"), _("Course"), _("Evaluation"), _("Score")],
        (
            [
                g.enrollment.student.matricule,
                g.enrollment.student.full_name,
                str(g.evaluation.term),
                str(g.evaluation.course),
                g.evaluation.name,
                float(g.score) if g.score is not None else None,
            ]
            for g in grades.iterator(chunk_size=500)
        ),
    )


def build(export: SchoolExport) -> SchoolExport:
    """Fait le classeur de l'école et le range ; en cas d'échec l'export passe à « échoué » (la
    console peut le redemander)."""
    from openpyxl import Workbook  # chargé ici : pas dans chaque processus (PERF.8)

    school = export.school
    try:
        book = Workbook(write_only=True)
        with use_school(school):
            for title, headers, rows in _sheets(school):
                sheet = book.create_sheet(str(title)[:31])
                sheet.append([str(h) for h in headers])
                for row in rows:
                    sheet.append(row)
        buffer = BytesIO()
        book.save(buffer)
        name = f"export-{school.code}-{timezone.localdate():%Y%m%d}.xlsx"
        export.file.save(name, ContentFile(buffer.getvalue()), save=False)
        export.state = SchoolExport.State.READY
        export.expires_at = timezone.now() + timedelta(days=VALID_DAYS)
    except Exception:
        logger.exception("Export de l'école %s échoué", school.code)
        export.state = SchoolExport.State.FAILED
    export.save()
    return export
