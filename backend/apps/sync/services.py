"""Appareils (3.3.1) : enregistrement, reprise à chaque connexion, révocation, signature des
reçus émis hors ligne. Synchronisation (3.3.2) : instantané et changements descendus sur
l'appareil ; les opérations qu'il envoie sont dans `operations.py`.

Une session connectée garde l'appareil sous `DEVICE_SESSION_KEY` : le journal d'audit note
l'appareil de chaque action (`AuditMiddleware`)."""

import base64
import binascii
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import load_der_public_key
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.accounts.roles import FINANCE_COLLECT_PAYMENT, FINANCE_VIEW_REPORTS, STUDENTS_VIEW
from apps.audit import services as audit
from apps.audit.actions import Action, PlatformAction
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.models import (
    CashRegister,
    CreditAllocation,
    ExchangeRate,
    FeeType,
    Payment,
    StudentCredit,
)
from apps.schools import organisation
from apps.schools.models import AcademicYear, ClassGroup, School
from apps.students.models import Enrollment
from apps.sync import changes
from apps.sync.models import ChangeLog, Device

DEVICE_SESSION_KEY = "sync.device"
# « Poste » : jamais égal au code d'une caisse (`C1`), qui numérote les reçus donnés en ligne.
PREFIX_LETTER = "P"

DEVICE_REVOKED = ApiError(
    "device_revoked", _("This device was disconnected. It is no longer remembered."), 409
)
DEVICE_REQUIRED = ApiError(
    "device_required", _("Remember this device when you log in to work without internet."), 403
)
# Dernier contact noté au plus une fois par 30 s (la synchronisation tourne toutes les 60 s).
SEEN_EVERY = timedelta(seconds=30)

SNAPSHOT_REQUIRED = ApiError(
    "snapshot_required", _("The data of this device is out of date: download it again."), 409
)


def session_device(session, school: School | None) -> str | None:
    """Identifiant de l'appareil de la session, s'il a été enregistré dans cette école."""
    data = session.get(DEVICE_SESSION_KEY)
    if not data or school is None or data.get("school") != str(school.pk):
        return None
    return data["id"]


def register_device(school: School, user: User, session, *, label: str, public_key: str) -> Device:
    """« Se souvenir de cet appareil » : nouvel appareil du compte, rattaché à la session."""
    _load_public_key(public_key)
    with transaction.atomic():
        # Deux enregistrements en même temps ne prennent pas le même préfixe.
        School.objects.select_for_update().filter(pk=school.pk).first()
        device = Device(
            user=user, label=label, prefix=_next_prefix(), public_key=public_key, created_by=user
        )
        _attach(device, school, session)
        device.save()
        audit.record(
            Action.DEVICES_REGISTERED,
            device,
            actor=user,
            after={"prefix": device.prefix, "label": device.label},
        )
    return device


def resume_device(device: Device, school: School, session) -> Device:
    """Connexion depuis un appareil déjà enregistré : il reprend la nouvelle session."""
    if device.revoked_at is not None:
        raise BusinessError(DEVICE_REVOKED)
    _attach(device, school, session)
    device.save(update_fields=["session_key", "last_seen_at", "updated_at"])
    return device


def revoke_device(device: Device, *, actor: User) -> None:
    """« Déconnecter » : l'appareil ne sert plus (préfixe jamais redonné) et sa session est
    fermée ; il efface ses données au prochain contact."""
    if device.revoked_at is not None:
        return
    with transaction.atomic():
        device.revoked_at = timezone.now()
        device.save(update_fields=["revoked_at", "updated_at"])
        audit.record(Action.DEVICES_REVOKED, device, actor=actor)
    if device.session_key:
        import_module(settings.SESSION_ENGINE).SessionStore(device.session_key).delete()


def support_revoke_device(device: Device, *, actor: User) -> Device:
    """« Déconnecter » depuis la console (5.4.2) : comme dans l'école, et noté aussi dans le
    journal de la plateforme. Déjà déconnecté : rien de plus."""
    with use_school(device.school), transaction.atomic():
        device = (
            Device.objects.select_related("school", "user")
            .select_for_update(of=("self",))
            .get(pk=device.pk)
        )
        if device.revoked_at is None:
            revoke_device(device, actor=actor)
            audit.record_platform(
                PlatformAction.DEVICE_REVOKED,
                device,
                actor=actor,
                label=f"{device.label} · {device.prefix} | {device.user} ({device.school.name})",
            )
    return device


def verify_signature(device: Device, message: bytes, signature: bytes) -> bool:
    """Signature ECDSA P-256 / SHA-256 faite par l'appareil avec WebCrypto (`r ‖ s`, 64 octets).
    Ne regarde pas la révocation : c'est à l'appelant de décider."""
    if len(signature) != 64:
        return False
    der = encode_dss_signature(
        int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    )
    try:
        _load_public_key(device.public_key).verify(der, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False
    return True


def _attach(device: Device, school: School, session) -> None:
    if session.session_key is None:
        session.save()
    device.session_key = session.session_key
    device.last_seen_at = timezone.now()
    session[DEVICE_SESSION_KEY] = {"id": str(device.pk), "school": str(school.pk)}


def _next_prefix() -> str:
    """`P1`, `P2`… dans l'école courante : jamais redonné (un appareil révoqué garde le sien),
    jamais égal au code d'une caisse."""
    taken = set(Device.objects.values_list("prefix", flat=True))
    taken |= set(CashRegister.objects.values_list("code", flat=True))
    number = Device.objects.count() + 1
    while f"{PREFIX_LETTER}{number}" in taken:
        number += 1
    return f"{PREFIX_LETTER}{number}"


def _load_public_key(value: str) -> ec.EllipticCurvePublicKey:
    try:
        key = load_der_public_key(base64.b64decode(value, validate=True))
    except (ValueError, binascii.Error):
        key = None
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise ValidationError(
            {"public_key": ValidationError(_("Invalid device key."), code="invalid_key")}
        )
    return key


def sync_device(session, school: School, user: User) -> Device:
    """L'appareil de la session, enregistré dans cette école par ce compte : seul un appareil
    enregistré se synchronise. Déconnecté : 409 `device_revoked` (il efface ses données).
    Chaque synchronisation note son dernier contact."""
    device_id = session_device(session, school)
    device = Device.objects.filter(pk=device_id, user=user).first() if device_id else None
    if device is None:
        raise BusinessError(DEVICE_REQUIRED)
    if device.revoked_at is not None:
        raise BusinessError(DEVICE_REVOKED)
    now = timezone.now()
    if device.last_seen_at is None or now - device.last_seen_at >= SEEN_EVERY:
        # Dernier contact (« Appareils de l'école ») : sans toucher au reste de l'appareil.
        Device.objects.filter(pk=device.pk).update(last_seen_at=now)
        device.last_seen_at = now
    return device


@dataclass(frozen=True)
class Reader:
    """Ce que le compte peut recevoir sur son appareil : les élèves avec `students.view` ou un
    droit sur les finances (un enseignant qui n'a que les notes n'en reçoit aucun, 8.2.3) ;
    frais dus, paiements, caisses et taux avec un droit sur les finances ; les paiements des autres
    caissiers seulement avec `finance.view_reports` (comme en ligne)."""

    user: User
    finance: bool
    all_payments: bool
    students: bool = True

    @classmethod
    def of(cls, user: User, permissions: frozenset[str]) -> "Reader":
        finance = bool(permissions & {FINANCE_COLLECT_PAYMENT, FINANCE_VIEW_REPORTS})
        return cls(
            user=user,
            finance=finance,
            all_payments=FINANCE_VIEW_REPORTS in permissions,
            students=finance or STUDENTS_VIEW in permissions,
        )


@dataclass
class Config:
    """Configuration de l'école sur l'appareil (entité `config`) : modifiée en ligne seulement."""

    school: School
    academic_year: AcademicYear | None
    class_groups: list[ClassGroup]
    fee_types: list[FeeType] | None
    cash_registers: list[CashRegister] | None
    exchange_rate: ExchangeRate | None


@dataclass
class Snapshot:
    cursor: int | None
    device: Device | None
    config: Config | None
    enrollments: list[Enrollment]
    next: UUID | None


@dataclass
class Change:
    seq: int
    entity_type: str
    entity_id: UUID
    operation: str
    enrollment: Enrollment | None = None
    config: Config | None = None


@dataclass
class Pull:
    changes: list[Change]
    cursor: int
    has_more: bool


def config(reader: Reader, school: School) -> Config:
    year = organisation.current_year()
    groups = ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
    return Config(
        school=school,
        academic_year=year,
        class_groups=sorted(groups, key=lambda group: (group.level.order, group.name)),
        fee_types=list(FeeType.objects.order_by("name")) if reader.finance else None,
        cash_registers=list(CashRegister.objects.order_by("code")) if reader.finance else None,
        exchange_rate=(finance.payment_rate()[0] if reader.finance and year is not None else None),
    )


def enrollments(reader: Reader, *, ids=None, after=None, limit=None) -> list[Enrollment]:
    """Inscriptions de l'année en cours avec l'élève et, avec un droit sur les finances, ses
    frais dus (réductions, payé, reste : `finance.charges_by_enrollment`), ses paiements, ses
    crédits à traiter (3.6.2) et les parts de crédit déjà utilisées (3.8.3). Quelques
    requêtes, quel que soit le nombre d'inscriptions."""
    items = Enrollment.objects.filter(academic_year=organisation.current_year()).select_related(
        "student__family"
    )
    if ids is not None:
        items = items.filter(pk__in=ids)
    if after is not None:
        items = items.filter(pk__gt=after)
    items = list(items.order_by("pk")[:limit])
    if not reader.finance:
        for item in items:
            item.sync_charges = item.sync_payments = item.sync_credits = None
            item.sync_credit_uses = None
        return items
    keys = [item.pk for item in items]
    charges = finance.charges_by_enrollment(keys)
    payments = finance.receipt_payments().filter(enrollment_id__in=keys)
    if not reader.all_payments:
        # Ses encaissements, et les reprises (E6) : sans elles, le solde d'un duplicata refait
        # sur l'appareil oublierait ce qui était payé avant.
        payments = payments.filter(
            Q(cash_session__cashier=reader.user) | Q(origin=Payment.Origin.PRIOR)
        )
    by_enrollment: dict[UUID, list[Payment]] = defaultdict(list)
    for payment in payments:
        by_enrollment[payment.enrollment_id].append(payment)
    credits: dict[UUID, list[StudentCredit]] = defaultdict(list)
    for credit in finance.open_credits(keys):
        credits[credit.enrollment_id].append(credit)
    uses: dict[UUID, list[CreditAllocation]] = defaultdict(list)
    for part in finance.credit_uses(keys):
        uses[part.credit.enrollment_id].append(part)
    for item in items:
        item.sync_charges = charges.get(item.pk, [])
        item.sync_payments = by_enrollment[item.pk]
        item.sync_credits = credits[item.pk]
        item.sync_credit_uses = uses[item.pk]
    return items


def snapshot(
    device: Device, reader: Reader, school: School, *, after=None, limit: int = 200
) -> Snapshot:
    """Instantané de l'école par pages d'inscriptions (`after` : la dernière de la page
    précédente). La première page donne aussi l'appareil (séquence de ses reçus, pour la
    reprendre après une réinstallation), la configuration et `cursor`, pris avant de lire les
    données : `pull` depuis ce numéro renvoie tout ce qui a changé ensuite."""
    first = after is None
    cursor = changes.sequence() if first else None
    items = enrollments(reader, after=after, limit=limit + 1) if reader.students else []
    return Snapshot(
        cursor=cursor,
        device=device if first else None,
        config=config(reader, school) if first and reader.students else None,
        enrollments=items[:limit],
        next=items[limit - 1].pk if len(items) > limit else None,
    )


def pull(reader: Reader, school: School, *, since: int, limit: int = 500) -> Pull:
    """Changements depuis le numéro `since`, dans l'ordre, avec l'état actuel de chaque entité.
    Une inscription qui n'est plus dans l'année en cours part de l'appareil (`delete`) ; une
    nouvelle année en cours se voit dans la configuration (l'appareil reprend un instantané).
    `since` plus grand que le dernier numéro (base restaurée) : 409 `snapshot_required`."""
    last = changes.sequence()
    if since > last:
        raise BusinessError(SNAPSHOT_REQUIRED)
    if not reader.students:
        return Pull([], last, False)
    rows = list(ChangeLog.objects.filter(seq__gt=since).order_by("seq")[: limit + 1])
    has_more, rows = len(rows) > limit, rows[:limit]
    wanted = [row.entity_id for row in rows if row.entity_type == ChangeLog.Entity.ENROLLMENT]
    found = {item.pk: item for item in enrollments(reader, ids=wanted)} if wanted else {}
    current = None
    if any(row.entity_type == ChangeLog.Entity.CONFIG for row in rows):
        current = config(reader, school)
    items = []
    for row in rows:
        if row.entity_type == ChangeLog.Entity.CONFIG:
            items.append(
                Change(row.seq, row.entity_type, row.entity_id, row.operation, None, current)
            )
            continue
        enrollment = found.get(row.entity_id)
        operation = ChangeLog.Operation.UPSERT if enrollment else ChangeLog.Operation.DELETE
        items.append(Change(row.seq, row.entity_type, row.entity_id, operation, enrollment))
    return Pull(items, rows[-1].seq if rows else since, has_more)
