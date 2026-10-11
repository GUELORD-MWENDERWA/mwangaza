"""Annulation d'un import d'élèves (D6) : un fichier importé dans la mauvaise année ou les
mauvaises classes se rattrape.

Les élèves créés par l'import (`Student.student_import`) sont effacés avec leurs inscriptions,
leurs frais dus et les familles restées sans élève. Un élève que quelque chose touche déjà
reste, avec sa famille et son lien : paiement ou crédit, réduction, échéancier particulier,
compte parent activé. Aucun paiement n'est touché ; les frais dus effacés ici n'ont jamais rien
reçu (seule exception à « rien n'est effacé dans les finances », décision du 2026-10-11).

Tout nouveau modèle lié à un élève ou à une inscription s'ajoute ici : aux raisons de garder
l'élève (`_touches`) ou à ce qui part avec lui (`cancel`). Sinon la base refuse l'annulation.
"""

import logging
from dataclasses import dataclass
from functools import partial, reduce
from operator import or_

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.finance.models import CreditAllocation, Discount, Payment, StudentCharge, StudentCredit
from apps.schools.models import AcademicYear
from apps.students.models import Enrollment, Family, MatriculeSequence, Student, StudentImport
from apps.students.services import _student_data
from apps.sync import changes as sync_changes

logger = logging.getLogger(__name__)

PAYMENT, DISCOUNT, SCHEDULE, PORTAL = "payment", "discount", "schedule", "portal"
REASONS = (PAYMENT, DISCOUNT, SCHEDULE, PORTAL)
# Élèves gardés nommés à l'écran ; au-delà, leur nombre seulement.
KEPT_SHOWN = 50

NOT_CANCELLABLE = ApiError(
    "import_not_cancellable", _("Only a finished import can be cancelled."), 409
)
NOTHING_TO_CANCEL = ApiError(
    "nothing_to_cancel", _("No student of this import can be removed."), 409
)
CHANGED_MEANWHILE = ApiError(
    "import_changed", _("A student of this import has just changed: try again."), 409
)


@dataclass
class Cancellation:
    removable_count: int
    kept_count: int
    # Les premiers élèves gardés, chacun avec ses `reasons`.
    kept: list[Student]


def _touches() -> dict[str, tuple[str, Exists]]:
    """Ce qui garde un élève : nom de l'annotation → (raison, sous-requête)."""
    student = OuterRef("pk")
    custom = StudentCharge.Source.CUSTOM
    return {
        "paid": (PAYMENT, Exists(Payment.objects.filter(enrollment__student=student))),
        "credited": (PAYMENT, Exists(StudentCredit.objects.filter(enrollment__student=student))),
        "credit_used": (
            PAYMENT,
            Exists(CreditAllocation.objects.filter(student_charge__enrollment__student=student)),
        ),
        "discounted": (DISCOUNT, Exists(Discount.objects.filter(enrollment__student=student))),
        "rescheduled": (
            SCHEDULE,
            Exists(StudentCharge.objects.filter(enrollment__student=student, source=custom)),
        ),
        "on_portal": (
            PORTAL,
            Exists(Family.objects.filter(pk=OuterRef("family_id"), primary_user__isnull=False)),
        ),
    }


def _students(imp: StudentImport) -> tuple[QuerySet[Student], Q]:
    """Élèves de l'import, annotés de ce qui les touche, et le filtre « gardé »."""
    touches = _touches()
    students = Student.objects.filter(student_import=imp).annotate(
        **{name: exists for name, (_reason, exists) in touches.items()}
    )
    return students, reduce(or_, (Q(**{name: True}) for name in touches))


def cancellation(imp: StudentImport) -> Cancellation:
    """Ce que ferait (ou ce qu'a laissé) l'annulation : élèves à retirer, élèves gardés."""
    students, kept = _students(imp)
    counts = students.aggregate(total=Count("pk"), kept=Count("pk", filter=kept))
    shown = []
    if counts["kept"]:
        touches = _touches()
        shown = list(
            students.filter(kept).order_by("last_name", "middle_name", "first_name")[:KEPT_SHOWN]
        )
        for student in shown:
            found = {
                reason for name, (reason, _exists) in touches.items() if getattr(student, name)
            }
            student.reasons = [reason for reason in REASONS if reason in found]
    return Cancellation(counts["total"] - counts["kept"], counts["kept"], shown)


def cancel(imp: StudentImport, *, actor: User, reason: str) -> StudentImport:
    """Efface les élèves de l'import que rien ne touche. Un paiement encaissé pendant
    l'annulation passe avant elle : la base la refuse en entier, à refaire (l'élève est alors
    gardé)."""
    try:
        with transaction.atomic():
            return _cancel(imp, actor=actor, reason=reason)
    except IntegrityError:
        logger.exception("Annulation de l'import %s refusée par la base", imp.pk)
        raise BusinessError(CHANGED_MEANWHILE) from None


def _cancel(imp: StudentImport, *, actor: User, reason: str) -> StudentImport:
    """D'un seul envoi, dans la transaction de `cancel`. Les suppressions en masse n'envoient
    pas de signal : le `ChangeLog` est noté ici, une fois."""
    imp = StudentImport.objects.select_for_update().defer("rows").get(pk=imp.pk)
    if imp.status != StudentImport.Status.DONE:
        raise BusinessError(NOT_CANCELLABLE)
    # Année verrouillée, comme à l'import et à l'inscription : le numéro de matricule ne
    # bouge pas pendant qu'il est repris.
    year = AcademicYear.objects.select_for_update().get(pk=imp.academic_year_id)
    students, kept = _students(imp)
    removed = list(students.exclude(kept).select_related("family"))
    if not removed:
        raise BusinessError(NOTHING_TO_CANCEL)
    ids = [student.pk for student in removed]
    enrollments = list(Enrollment.objects.filter(student_id__in=ids).values_list("pk", flat=True))
    audit.record_many(
        Action.STUDENTS_STUDENT_REMOVED,
        [
            (student, {**_student_data(student), "file": imp.file_name, "reason": reason})
            for student in removed
        ],
        actor=actor,
        removed=True,
    )

    using = students.db
    StudentCharge.objects.filter(enrollment_id__in=enrollments)._raw_delete(using)
    Enrollment.objects.filter(pk__in=enrollments)._raw_delete(using)
    Student.objects.filter(pk__in=ids)._raw_delete(using)
    # Tuteurs, demandes des parents et annonces lues partent avec la famille.
    Family.objects.filter(pk__in={student.family_id for student in removed}).filter(
        ~Exists(Student.objects.filter(family=OuterRef("pk")))
    ).delete()
    sync_changes.touch_enrollments(enrollments, operation=sync_changes.Operation.DELETE)
    photos = [student.photo for student in removed if student.photo]
    if photos:
        transaction.on_commit(partial(_delete_photos, photos))

    # Les numéros rendus servent de nouveau ; un numéro encore pris est sauté à l'attribution.
    if imp.matricule_start is not None:
        MatriculeSequence.objects.filter(
            academic_year=year, last_number__gt=imp.matricule_start
        ).update(last_number=imp.matricule_start)

    imp.status = StudentImport.Status.CANCELLED
    imp.cancelled_count = len(removed)
    imp.cancelled_at = timezone.now()
    imp.cancelled_by = actor
    imp.cancel_reason = reason
    imp.save(
        update_fields=[
            "status",
            "cancelled_count",
            "cancelled_at",
            "cancelled_by",
            "cancel_reason",
            "updated_at",
        ]
    )
    audit.record(
        Action.STUDENTS_IMPORT_CANCELLED,
        imp,
        actor=actor,
        after={
            "file": imp.file_name,
            "school_year": year.name,
            "reason": reason,
            "students_removed": len(removed),
            "students_kept": imp.created_count - len(removed),
        },
    )
    return imp


def _delete_photos(photos: list) -> None:
    for photo in photos:
        photo.storage.delete(photo.name)
