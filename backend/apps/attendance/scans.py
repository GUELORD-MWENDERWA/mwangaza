"""Pointage à l'entrée (6.3) : chaque passage lu par un appareil enregistré, même sans réseau,
arrive par la synchronisation (opération `attendance.scan`, `sync/operations.py`). L'appareil a
déjà décidé seul d'après sa liste (`cards.roster_*`) ; le serveur rejoue la même règle et garde
une seule ligne par personne et par jour : un second passage, d'un autre appareil ou rejoué, est
« déjà passé » et ne crée rien. Une écriture par passage, sans journal d'audit (seules les
corrections y vont, partie suivante)."""

from datetime import datetime, timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Membership, User
from apps.attendance.cards import current_enrollments
from apps.attendance.models import AttendanceRecord, AttendanceSession, IdCard
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools.attendance import late_after
from apps.students.models import Student
from apps.sync.models import Device

CARD_UNKNOWN = ApiError("card_unknown", _("Unknown card: it is not a card of this school."), 404)
CARD_REVOKED = ApiError("card_revoked", _("This card has been revoked: it is refused."), 409)
CARD_EXPIRED = ApiError("card_expired", _("This card is no longer valid."), 409)
NOT_ENROLLED = ApiError("not_enrolled", _("This student is not enrolled this year."), 409)
MEMBER_INACTIVE = ApiError("member_inactive", _("This person no longer works at the school."), 409)
CLOCK_AHEAD = ApiError(
    "device_clock_ahead", _("The clock of this device is ahead: set the right time."), 400
)
TAKEN_ID = ApiError("id_taken", _("This identifier is already used: update the application."), 409)
# Écart toléré entre l'horloge de l'appareil et celle du serveur.
CLOCK_MARGIN = timedelta(minutes=10)


def entrance(day) -> AttendanceSession:
    """Séance « entrée » du jour, créée au premier passage (deux appareils en même temps : une
    seule, grâce à la contrainte d'unicité)."""
    session, _created = AttendanceSession.objects.get_or_create(
        kind=AttendanceSession.Kind.ENTRANCE, date=day
    )
    return session


def _holder(
    card_hash: str, student: Student | None, member: Membership | None, seen_at: datetime
) -> tuple[IdCard | None, Student | None, Membership | None]:
    if not card_hash:
        return None, student, member
    card = IdCard.objects.select_related("student", "member").filter(token_hash=card_hash).first()
    if card is None:
        raise BusinessError(CARD_UNKNOWN)
    # Hors ligne, un passage lu avant la révocation reste bon.
    if card.revoked_at is not None and card.revoked_at <= seen_at:
        raise BusinessError(CARD_REVOKED)
    if timezone.localdate(seen_at) > card.valid_until:
        raise BusinessError(CARD_EXPIRED)
    return card, card.student, card.member


def record_scan(
    *,
    actor: User,
    device: Device | None,
    id: UUID,
    seen_at: datetime,
    card_hash: str = "",
    student: Student | None = None,
    member: Membership | None = None,
) -> tuple[AttendanceRecord, bool]:
    """Passage lu par la carte (`card_hash`, empreinte du jeton) ou matricule tapé (`student` ou
    `member`). Retard après l'heure limite de l'école. Renvoie la ligne et `True` si la personne
    était déjà passée ce jour-là."""
    if seen_at > timezone.now() + CLOCK_MARGIN:
        raise BusinessError(CLOCK_AHEAD)
    card, student, member = _holder(card_hash, student, member, seen_at)
    if student is not None and not current_enrollments().filter(student=student).exists():
        raise BusinessError(NOT_ENROLLED)
    if member is not None and (
        not member.is_active or member.school_id != require_current_school().pk
    ):
        raise BusinessError(MEMBER_INACTIVE)
    holder = {"student": student} if student is not None else {"member": member}
    local = timezone.localtime(seen_at)
    late = local.time() > late_after(require_current_school().settings)
    session = entrance(local.date())
    existing = AttendanceRecord.objects.filter(session=session, **holder).first()
    if existing is not None:
        return existing, True
    try:
        with transaction.atomic():
            record = AttendanceRecord.objects.create(
                id=id,
                session=session,
                card=card,
                device=device,
                seen_at=seen_at,
                method=AttendanceRecord.Method.QR if card else AttendanceRecord.Method.MANUAL,
                status=AttendanceRecord.Status.LATE if late else AttendanceRecord.Status.PRESENT,
                created_by=actor,
                **holder,
            )
    except IntegrityError:
        # Même personne envoyée au même instant par un autre appareil, ou passage déjà reçu.
        found = AttendanceRecord.objects.filter(Q(pk=id) | Q(session=session, **holder)).first()
        if found is None:
            raise BusinessError(TAKEN_ID) from None
        return found, True
    return record, False
