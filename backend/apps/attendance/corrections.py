"""Corrections au journal (6.5) et justifications d'absence (6.6). Rien n'est modifié : une
correction est une ligne de plus, la plus récente l'emporte ; une justification ne change qu'une
fois, quand l'école l'accepte ou la refuse. Tout passe au journal d'audit, sauf l'envoi d'une
justification par le parent (l'école la voit en attente)."""

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Membership, User
from apps.attendance import follow
from apps.attendance.cards import current_enrollments, staff
from apps.attendance.models import (
    AbsenceJustification,
    AttendanceCorrection,
    AttendanceRecord,
    AttendanceSession,
)
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.images import clean_image
from apps.notifications import events
from apps.schools import organisation
from apps.students.models import Student

NOT_A_SCHOOL_DAY = ApiError(
    "not_a_school_day",
    _("Nobody was recorded at the entrance that day, or it is a holiday: nothing to correct."),
    409,
)
NOT_EXPECTED = ApiError("not_expected", _("This person was not expected at school that day."), 409)
NOTHING_TO_CORRECT = ApiError(
    "nothing_to_correct", _("The attendance is already the one chosen."), 409
)
OUTSIDE_YEAR = ApiError("outside_year", _("Choose days of the current school year."), 400)
TOO_EARLY = ApiError(
    "justification_too_early",
    _("An absence is justified within 30 days."),
    400,
)
TOO_FAR = ApiError(
    "justification_too_far",
    _("An absence is announced at most 7 days ahead."),
    400,
)
TOO_LONG = ApiError(
    "justification_too_long",
    _("One justification covers 15 days at most."),
    400,
)
ALREADY_JUSTIFIED = ApiError(
    "already_justified",
    _("A justification already covers one of these days (pending or accepted)."),
    409,
)
ALREADY_DECIDED = ApiError(
    "already_decided", _("This justification has already been decided."), 409
)

# Fenêtre d'une justification : jusqu'à 30 jours après l'absence, 7 jours avant (deuil, soins
# prévus), 15 jours au plus d'un coup.
LOOK_BACK, LOOK_AHEAD, LONGEST = timedelta(days=30), timedelta(days=7), timedelta(days=14)
DOCUMENT_MAX_SIZE = 5 * 1024 * 1024
PDF_MAGIC = b"%PDF-"


def _person_label(student: Student | None, member: Membership | None) -> str:
    return str(student) if student is not None else str(member.user)


def correct(
    *,
    actor: User,
    day: date,
    status: str,
    reason: str,
    student: Student | None = None,
    member: Membership | None = None,
) -> AttendanceCorrection:
    """Corrige la présence d'un élève ou d'un membre du personnel un jour de classe passé ou
    d'aujourd'hui : « présent, carte oubliée », retard excusé, absent malgré un passage."""
    year = organisation.current_year()
    if year is None or not (year.starts_on <= day <= min(year.ends_on, timezone.localdate())):
        raise BusinessError(OUTSIDE_YEAR)
    session = follow.school_days(day, day).get(day)
    if session is None:
        raise BusinessError(NOT_A_SCHOOL_DAY)
    if student is not None:
        expected = current_enrollments().filter(student=student, enrolled_on__lte=day).exists()
        holder = {"student": student}
    else:
        expected = staff().filter(pk=member.pk).exists()
        holder = {"member": member}
    if not expected:
        raise BusinessError(NOT_EXPECTED)
    with transaction.atomic():
        # Une correction à la fois pour une personne et un jour : la « précédente » est sûre.
        AttendanceSession.objects.select_for_update().filter(pk=session).first()
        record = AttendanceRecord.objects.filter(session_id=session, **holder).first()
        last = (
            AttendanceCorrection.objects.filter(session_id=session, **holder)
            .order_by("-created_at")
            .first()
        )
        previous = last.status if last else (record.status if record else follow.ABSENT)
        if previous == status:
            raise BusinessError(NOTHING_TO_CORRECT)
        correction = AttendanceCorrection.objects.create(
            session_id=session,
            record=record,
            status=status,
            previous_status=previous,
            reason=reason,
            created_by=actor,
            **holder,
        )
        audit.record(
            Action.ATTENDANCE_CORRECTED,
            correction,
            actor=actor,
            before={"status": previous},
            after={"status": status, "reason": reason, "date": day.isoformat()},
            label=f"{_person_label(student, member)} · {day:%d/%m/%Y}",
        )
    return correction


# Justifications


def clean_document(file) -> ContentFile:
    """Certificat : PDF reconnu à ses premiers octets, ou photo ré-encodée ; 5 Mo au plus."""
    if file.size > DOCUMENT_MAX_SIZE:
        raise ValidationError(_("The file must not exceed 5 MB."), code="document_too_large")
    file.seek(0)
    if file.read(len(PDF_MAGIC)) == PDF_MAGIC:
        file.seek(0)
        return ContentFile(file.read(), name="certificate.pdf")
    return clean_image(file, max_size=DOCUMENT_MAX_SIZE)


def _check_period(student: Student, starts_on: date, ends_on: date) -> None:
    today = timezone.localdate()
    year = organisation.current_year()
    if year is None or starts_on < year.starts_on or ends_on > year.ends_on:
        raise BusinessError(OUTSIDE_YEAR)
    if starts_on > ends_on or ends_on - starts_on > LONGEST:
        raise BusinessError(TOO_LONG)
    if starts_on < today - LOOK_BACK:
        raise BusinessError(TOO_EARLY)
    if ends_on > today + LOOK_AHEAD:
        raise BusinessError(TOO_FAR)
    if (
        AbsenceJustification.objects.filter(
            student=student,
            status__in=[AbsenceJustification.Status.PENDING, AbsenceJustification.Status.ACCEPTED],
            starts_on__lte=ends_on,
            ends_on__gte=starts_on,
        )
        .select_for_update()
        .exists()
    ):
        raise BusinessError(ALREADY_JUSTIFIED)


def justify(
    *,
    actor: User,
    student: Student,
    starts_on: date,
    ends_on: date,
    reason: str,
    document=None,
    by_school: bool,
) -> AbsenceJustification:
    """Justification d'une absence, du `starts_on` au `ends_on`. Envoyée par le parent : en
    attente, l'école en est prévenue. Notée par l'école (le parent a apporté un mot) : acceptée
    d'emblée, au journal."""
    Source, Status = AbsenceJustification.Source, AbsenceJustification.Status
    with transaction.atomic():
        # Deux envois en même temps pour le même élève : un seul passe le contrôle des jours.
        Student.objects.select_for_update().filter(pk=student.pk).first()
        _check_period(student, starts_on, ends_on)
        justification = AbsenceJustification(
            student=student,
            starts_on=starts_on,
            ends_on=ends_on,
            reason=reason,
            source=Source.SCHOOL if by_school else Source.PORTAL,
            status=Status.ACCEPTED if by_school else Status.PENDING,
            created_by=actor,
        )
        if by_school:
            justification.decided_at, justification.decided_by = timezone.now(), actor
        if document is not None:
            cleaned = clean_document(document)
            justification.document.save(cleaned.name or "certificate", cleaned, save=False)
        justification.save()
        if by_school:
            audit.record(
                Action.JUSTIFICATION_RECORDED,
                justification,
                actor=actor,
                after=_data(justification),
                label=_label(justification),
            )
        else:
            events.absence_justified(justification)
    return justification


def decide(
    justification: AbsenceJustification, *, actor: User, accept: bool, note: str = ""
) -> AbsenceJustification:
    """Accepte ou refuse une justification en attente ; le parent voit la réponse (notifiée)."""
    with transaction.atomic():
        justification = AbsenceJustification.objects.select_for_update().get(pk=justification.pk)
        if justification.status != AbsenceJustification.Status.PENDING:
            raise BusinessError(ALREADY_DECIDED)
        Status = AbsenceJustification.Status
        justification.status = Status.ACCEPTED if accept else Status.REFUSED
        justification.decided_at, justification.decided_by = timezone.now(), actor
        justification.decision_note = note
        justification.save(
            update_fields=["status", "decided_at", "decided_by", "decision_note", "updated_at"]
        )
        audit.record(
            Action.JUSTIFICATION_DECIDED,
            justification,
            actor=actor,
            before={"status": Status.PENDING},
            after={"status": justification.status, "note": note},
            label=_label(justification),
        )
        events.justification_decided(justification)
    return justification


def _label(justification: AbsenceJustification) -> str:
    return f"{justification.student} · {justification.starts_on:%d/%m/%Y}"


def _data(justification: AbsenceJustification) -> dict:
    return {
        "starts_on": justification.starts_on.isoformat(),
        "ends_on": justification.ends_on.isoformat(),
        "reason": justification.reason,
        "status": justification.status,
        "document": bool(justification.document),
    }
