"""Opérations envoyées par les appareils (`POST /api/sync/push`, 3.3.2), appliquées dans
l'ordre, chacune une seule fois (`SyncOperation`).

Chaque type d'opération donne le droit exigé, le contenu attendu (serializer) et le service
appelé : encaissement (3.3.2), ouverture de caisse et réimpression (3.5.2), crédit utilisé à la
caisse (3.6.2), demande d'annulation (3.8.1), clôture de caisse (3.8.2), sortie de caisse
(FIN.2), inscription d'un élève (HL.1), feuille de notes (8.2.3), infraction d'un élève (HL.2),
passage à l'entrée (6.3), prêt et retour d'un livre ou d'un outil (lot 11).
Une opération hors
ligne de plus est une entrée de plus dans `OPERATIONS` ; ce qu'elle crée porte l'identifiant
donné par l'appareil, car la trace d'une opération appliquée est effacée après `KEEP_DAYS`
jours (`purge`)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied

from apps.academics import discipline, grades
from apps.academics.discipline_serializers import IncidentCreateSerializer
from apps.academics.models import Course
from apps.academics.serializers import SheetUpdateSerializer
from apps.accounts.models import User
from apps.accounts.roles import (
    ATTENDANCE_SCAN,
    DISCIPLINE_RECORD,
    FINANCE_COLLECT_PAYMENT,
    FINANCE_REQUEST_CANCELLATION,
    FINANCE_VIEW_REPORTS,
    GRADES_ENTER,
    GRADES_ENTER_ANY,
    GRADES_VALIDATE,
    LIBRARY_LEND,
    STUDENTS_EDIT,
    WORKSHOPS_MANAGE,
)
from apps.attendance import cards as attendance_cards
from apps.attendance import scans
from apps.core.errors import ApiError, BusinessError, api_exception_handler
from apps.core.tenancy import use_all_schools
from apps.finance import cash_outs
from apps.finance import services as finance
from apps.finance.models import CashRegister, CashSession, Expense, Payment, StudentCredit
from apps.finance.serializers import CashCloseSerializer, PaymentCreateSerializer
from apps.inventory import loans as inventory_loans
from apps.inventory.serializers import OfflineLoanSerializer, OfflineReturnSerializer
from apps.schools.models import ClassGroup, Term
from apps.students import services as students
from apps.students.models import Student
from apps.students.serializers import StudentWriteSerializer
from apps.sync.models import Device, SyncOperation

UNKNOWN_OPERATION = ApiError(
    "unknown_operation", _("This application is out of date: update it."), 400
)
DUPLICATE = "duplicate"
# Opérations appliquées gardées (A.2). L'appareil retire une opération dès qu'il a sa réponse :
# seule une réponse perdue, puis ce délai sans réseau, la ferait renvoyer.
KEEP_DAYS = 90


class OfflinePaymentSerializer(PaymentCreateSerializer):
    """Encaissement hors ligne (F5) : comme en ligne, plus la session, le numéro de reçu et
    l'heure donnés par l'appareil."""

    id = serializers.UUIDField(help_text="UUID v7 donné par l'appareil.")
    cash_session = serializers.UUIDField(help_text="Session ouverte du caissier.")
    receipt_number = serializers.CharField(max_length=40, help_text="`ITIG-P1-26-000184`.")
    paid_at = serializers.DateTimeField(help_text="Heure de l'appareil à l'encaissement.")


def _create_payment(data: dict, device: Device, actor: User) -> dict:
    offline = finance.Offline(
        device=device,
        cash_session_id=data.pop("cash_session"),
        receipt_number=data.pop("receipt_number"),
        paid_at=data.pop("paid_at"),
    )
    payment, _created = finance.record_payment(
        data.pop("enrollment"), actor=actor, offline=offline, **data
    )
    # Séquence des reçus de l'appareil, reprise après une réinstallation (`snapshot`).
    save_receipt_seq(device, int(payment.receipt_number.rsplit("-", 1)[1]))
    return {"payment": str(payment.pk), "receipt_number": payment.receipt_number}


class OfflineSessionSerializer(serializers.Serializer):
    """Ouverture de caisse hors ligne (M13) : la session créée sur l'appareil."""

    id = serializers.UUIDField(help_text="UUID v7 donné par l'appareil.")
    cash_register = serializers.PrimaryKeyRelatedField(queryset=CashRegister.objects)
    opened_at = serializers.DateTimeField(help_text="Heure de l'appareil à l'ouverture.")

    def to_service(self) -> dict:
        return dict(self.validated_data)


def _open_session(data: dict, device: Device, actor: User) -> dict:
    """Jamais refusée pour une caisse prise entre-temps ou une autre caisse ouverte ailleurs :
    ses encaissements sont déjà faits (3.8.2)."""
    session = finance.open_cash_session(
        actor=actor,
        cash_register=data["cash_register"],
        session_id=data["id"],
        opened_at=data["opened_at"],
        device=device,
    )
    return {"cash_session": str(session.pk)}


class OfflineClosingSerializer(CashCloseSerializer):
    """Clôture de caisse hors ligne (F8) : l'argent compté sur l'appareil, à son heure."""

    cash_session = serializers.PrimaryKeyRelatedField(queryset=CashSession.objects)
    closed_at = serializers.DateTimeField(help_text="Heure de l'appareil à la clôture.")

    def to_service(self) -> dict:
        data = self.validated_data
        return {
            **super().to_service(),
            "session": data["cash_session"],
            "closed_at": data["closed_at"],
        }


def _close_session(data: dict, device: Device, actor: User) -> dict:
    session = data.pop("session")
    finance.close_cash_session(session, actor=actor, device=device, **data)
    return {"cash_session": str(session.pk)}


class OfflineCashOutSerializer(serializers.Serializer):
    """Sortie de caisse hors ligne (FIN.2) : l'argent est sorti, le bon signé sur l'appareil."""

    id = serializers.UUIDField(help_text="UUID v7 donné par l'appareil.")
    expense = serializers.PrimaryKeyRelatedField(queryset=Expense.objects)
    cash_session = serializers.UUIDField(help_text="Session ouverte du caissier.")
    number = serializers.CharField(max_length=40, help_text="`ITIG-P1-26-S0003`.")
    received_by = serializers.CharField(max_length=120)
    paid_at = serializers.DateTimeField(help_text="Heure de l'appareil à la sortie.")

    def to_service(self) -> dict:
        return dict(self.validated_data)


def _create_cash_out(data: dict, device: Device, actor: User) -> dict:
    offline = cash_outs.OfflineCashOut(
        device=device,
        cash_session_id=data["cash_session"],
        number=data["number"],
        paid_at=data["paid_at"],
    )
    cash_out, _created = cash_outs.record_cash_out(
        actor=actor,
        expense=data["expense"],
        received_by=data["received_by"],
        cash_out_id=data["id"],
        offline=offline,
    )
    return {"cash_out": str(cash_out.pk), "number": cash_out.number}


class OfflineReprintSerializer(serializers.Serializer):
    """Réimpression hors ligne (F6) : le duplicata est déjà imprimé par l'appareil."""

    payment = serializers.PrimaryKeyRelatedField(queryset=Payment.objects)
    reprinted_at = serializers.DateTimeField(help_text="Heure de l'appareil à la réimpression.")

    def to_service(self) -> dict:
        return dict(self.validated_data)


def _reprint(data: dict, device: Device, actor: User) -> dict:
    payment = data["payment"]
    # La caisse de l'appareil ne montre que les paiements de la session du caissier ; une
    # reprise (E6) n'a ni session ni reçu.
    if payment.cash_session_id is None or payment.cashier_id != actor.pk:
        raise PermissionDenied()
    finance.reprint_payment(payment, actor=actor, device_time=data["reprinted_at"])
    return {"payment": str(payment.pk)}


class OfflineCreditSerializer(serializers.Serializer):
    """Crédit utilisé à la caisse hors ligne (3.6.2) : le serveur le répartit à l'arrivée, sur ce
    que l'élève doit alors ; déjà utilisé ou annulé entre-temps : refusé, sans argent en jeu."""

    credit = serializers.PrimaryKeyRelatedField(queryset=StudentCredit.objects)

    def to_service(self) -> dict:
        return dict(self.validated_data)


def _use_credit(data: dict, device: Device, actor: User) -> dict:
    credit = finance.use_credit(data["credit"], actor=actor)
    return {"credit": str(credit.pk)}


class OfflineCancellationSerializer(serializers.Serializer):
    """Demande d'annulation hors ligne (F7) : la validation, elle, se fait en ligne."""

    id = serializers.UUIDField(help_text="UUID v7 donné par l'appareil.")
    payment = serializers.PrimaryKeyRelatedField(queryset=Payment.objects)
    reason = serializers.CharField(max_length=200)
    requested_at = serializers.DateTimeField(help_text="Heure de l'appareil à la demande.")

    def to_service(self) -> dict:
        # Sans `finance.view_reports`, l'appareil ne montre que les paiements du caissier.
        own_only = FINANCE_VIEW_REPORTS not in self.context["permissions"]
        return {**self.validated_data, "own_only": own_only}


def _request_cancellation(data: dict, device: Device, actor: User) -> dict:
    payment = data["payment"]
    if data["own_only"] and payment.cashier_id != actor.pk:
        raise PermissionDenied()
    request, _created = finance.request_cancellation(
        payment,
        actor=actor,
        reason=data["reason"],
        request_id=data["id"],
        device=device,
        requested_at=data["requested_at"],
    )
    return {"cancellation": str(request.pk)}


class OfflineGradesSerializer(SheetUpdateSerializer):
    """Feuille de notes enregistrée hors ligne (8.2.3) : comme `PUT …/grades/`, plus le cours et
    la période. L'identifiant d'une évaluation ajoutée est celui de l'appareil."""

    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects)
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects)

    def to_service(self) -> dict:
        return {
            "course": self.validated_data["course"],
            "term": self.validated_data["term"],
            "permissions": self.context["permissions"],
            **self.inputs(),
        }


def _save_grades(data: dict, device: Device, actor: User) -> dict:
    """Mêmes règles qu'en ligne : seul l'enseignant du cours tient son carnet, `grades.enter_any`,
    le titulaire, le cotitulaire et le remplaçant n'y mettent qu'un total (NB.1, NB.7, 8.2.5), tout
    autre compte est refusé ; date limite passée, feuille validée
    ou envoyée sans motif : refusée, la feuille du serveur reste."""
    course, term, permissions = data.pop("course"), data.pop("term"), data.pop("permissions")
    access = grades.notebook_access(actor, permissions, course)
    if access is None:
        raise PermissionDenied()
    grades.save_sheet(
        course,
        term,
        actor=actor,
        may_validate=GRADES_VALIDATE in permissions,
        total_only=grades.limited_to_totals(access, course, term, actor),
        **data,
    )
    return {"course": str(course.pk), "term": str(term.pk)}


class OfflineIncidentSerializer(IncidentCreateSerializer):
    """Infraction attribuée hors ligne (HL.2) : comme `POST /api/discipline/incidents/`, avec
    l'identifiant de l'appareil."""

    id = serializers.UUIDField(help_text="UUID v7 de l'incident, donné par l'appareil.")

    def to_service(self) -> dict:
        data = dict(self.validated_data)
        return {"incident_id": data.pop("id"), **data}


def _record_incident(data: dict, device: Device, actor: User) -> dict:
    """Mêmes règles qu'en ligne (infraction de la liste, élève inscrit, date passée)."""
    incident = discipline.record_incident(actor=actor, **data)
    return {"incident": str(incident.pk)}


class OfflineChargeSerializer(serializers.Serializer):
    id = serializers.UUIDField(help_text="UUID v7 du frais dû créé par l'appareil.")
    installment_template = serializers.UUIDField(help_text="Tranche du barème.")


class OfflineEnrollmentSerializer(StudentWriteSerializer):
    """Élève inscrit hors ligne (HL.1) : comme « Inscrire un élève », avec les identifiants de
    l'appareil (élève, nouvelle famille, inscription, frais dus calculés d'après `fee_rules`)."""

    id = serializers.UUIDField(help_text="UUID v7 de l'élève, donné par l'appareil.")
    family_id = serializers.UUIDField(
        required=False, help_text="Nouvelle famille (`guardians`) : son UUID v7."
    )
    enrollment_id = serializers.UUIDField(help_text="UUID v7 de l'inscription.")
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects)
    enrolled_on = serializers.DateField(help_text="Jour de l'appareil.")
    charges = OfflineChargeSerializer(many=True, required=False, default=list, max_length=100)
    distinct_from = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=20,
        help_text="Élèves aux mêmes noms dits différents sur l'appareil (« Ce sont deux élèves »).",
    )

    class Meta(StudentWriteSerializer.Meta):
        fields = [
            *StudentWriteSerializer.Meta.fields,
            "family_id",
            "enrollment_id",
            "class_group",
            "enrolled_on",
            "charges",
            "distinct_from",
        ]

    def to_service(self) -> dict:
        data = dict(self.validated_data)
        for ignored in ("matricule", "allow_duplicate"):
            data.pop(ignored, None)
        return data


def _enroll_student(data: dict, device: Device, actor: User) -> dict:
    """Jamais refusée pour un doublon possible : signalé au secrétariat (`enroll_offline`)."""
    student, enrollment, duplicates = students.enroll_offline(actor=actor, **data)
    return {
        "student": str(student.pk),
        "enrollment": str(enrollment.pk),
        "matricule": student.matricule,
        "family_code": student.family.code,
        "possible_duplicates": [str(other.pk) for other in duplicates],
    }


class _StaffField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return attendance_cards.staff()


class OfflineScanSerializer(serializers.Serializer):
    """Passage à l'entrée (6.3) : la carte lue (empreinte SHA-256 du jeton, jamais le jeton) ou
    l'élève / le membre du personnel dont on a tapé le matricule."""

    id = serializers.UUIDField(help_text="UUID v7 du passage, donné par l'appareil.")
    seen_at = serializers.DateTimeField(help_text="Heure de l'appareil à la lecture.")
    card_hash = serializers.RegexField(r"^[0-9a-f]{64}$", required=False)
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects, required=False)
    member = _StaffField(required=False)

    def validate(self, data):
        if sum(key in data for key in ("card_hash", "student", "member")) != 1:
            raise serializers.ValidationError(_("Give the card, the student or the staff member."))
        return data

    def to_service(self) -> dict:
        return dict(self.validated_data)


def _scan(data: dict, device: Device, actor: User) -> dict:
    """Mêmes règles que sur l'appareil ; « déjà passé » n'est pas un refus."""
    record, already = scans.record_scan(actor=actor, device=device, **data)
    return {
        "record": str(record.pk),
        "status": record.status,
        "already": already,
        "seen_at": record.seen_at.isoformat(),
        "student": str(record.student_id) if record.student_id else None,
        "member": str(record.member_id) if record.member_id else None,
    }


def _lend(data: dict, device: Device, actor: User) -> dict:
    """« Déjà prêté à un autre » est un refus (à revoir sur l'appareil) ; le même prêt rejoué
    ne l'est pas."""
    loan, already = inventory_loans.lend(actor=actor, device=device, **data)
    return {
        "loan": str(loan.pk),
        "number": loan.number,
        "due_on": str(loan.due_on),
        "already": already,
    }


def _give_back(data: dict, device: Device, actor: User) -> dict:
    loan, already = inventory_loans.give_back(actor=actor, **data)
    return {"loan": str(loan.pk), "already": already}


@dataclass(frozen=True)
class OperationType:
    permission: str | tuple[str, ...]
    serializer: type[serializers.Serializer]
    apply: Callable[[dict, Device, User], dict]


OPERATIONS = {
    "payment.create": OperationType(
        FINANCE_COLLECT_PAYMENT, OfflinePaymentSerializer, _create_payment
    ),
    "cash_session.open": OperationType(
        FINANCE_COLLECT_PAYMENT, OfflineSessionSerializer, _open_session
    ),
    "cash_session.close": OperationType(
        FINANCE_COLLECT_PAYMENT, OfflineClosingSerializer, _close_session
    ),
    "cash_out.create": OperationType(
        FINANCE_COLLECT_PAYMENT, OfflineCashOutSerializer, _create_cash_out
    ),
    "payment.reprint": OperationType(FINANCE_COLLECT_PAYMENT, OfflineReprintSerializer, _reprint),
    "credit.use": OperationType(FINANCE_COLLECT_PAYMENT, OfflineCreditSerializer, _use_credit),
    "cancellation.request": OperationType(
        FINANCE_REQUEST_CANCELLATION, OfflineCancellationSerializer, _request_cancellation
    ),
    "student.enroll": OperationType(STUDENTS_EDIT, OfflineEnrollmentSerializer, _enroll_student),
    "grades.save": OperationType(
        (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE), OfflineGradesSerializer, _save_grades
    ),
    "incident.record": OperationType(
        DISCIPLINE_RECORD, OfflineIncidentSerializer, _record_incident
    ),
    "attendance.scan": OperationType(ATTENDANCE_SCAN, OfflineScanSerializer, _scan),
    # Guichet de la bibliothèque, ou outils d'un atelier : le service vérifie le droit du lieu.
    "inventory.loan": OperationType((LIBRARY_LEND, WORKSHOPS_MANAGE), OfflineLoanSerializer, _lend),
    "inventory.return": OperationType(
        (LIBRARY_LEND, WORKSHOPS_MANAGE), OfflineReturnSerializer, _give_back
    ),
}


@dataclass(frozen=True)
class Incoming:
    op_id: UUID
    type: str
    payload: dict
    created_at: datetime | None = None


@dataclass
class Outcome:
    op_id: UUID
    status: str
    result: dict
    error: dict | None


def push(
    device: Device,
    actor: User,
    permissions: frozenset[str],
    operations: list[Incoming],
    *,
    receipt_seq: int | None = None,
) -> list[Outcome]:
    """Applique les opérations dans l'ordre. Une opération déjà reçue (même `op_id`, même en
    même temps depuis un autre envoi) n'est pas rejouée : `duplicate` avec son résultat, ou
    `rejected` avec la même erreur. Une opération refusée n'empêche pas les suivantes.
    `receipt_seq` : dernier numéro de reçu donné par l'appareil."""
    outcomes = [_apply(device, actor, permissions, operation) for operation in operations]
    if receipt_seq:
        save_receipt_seq(device, receipt_seq)
    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_seen_at", "updated_at"])
    return outcomes


def save_receipt_seq(device: Device, seq: int) -> None:
    """Dernier numéro de reçu de l'appareil : ne recule jamais."""
    Device.objects.filter(pk=device.pk).update(
        last_receipt_seq=Greatest(F("last_receipt_seq"), Value(seq))
    )


def _outcome(operation: SyncOperation, *, duplicate: bool = False) -> Outcome:
    if operation.status == SyncOperation.Status.REJECTED:
        return Outcome(operation.op_id, operation.status, {}, operation.result)
    status = DUPLICATE if duplicate else operation.status
    return Outcome(operation.op_id, status, operation.result, None)


def _apply(device: Device, actor: User, permissions: frozenset[str], incoming: Incoming) -> Outcome:
    existing = SyncOperation.objects.filter(op_id=incoming.op_id).first()
    if existing is not None:
        return _outcome(existing, duplicate=True)
    with transaction.atomic():
        try:
            with transaction.atomic():
                operation = SyncOperation.objects.create(
                    op_id=incoming.op_id,
                    device=device,
                    type=incoming.type,
                    payload=incoming.payload,
                    status=SyncOperation.Status.APPLIED,
                    created_by=actor,
                )
        except IntegrityError:
            # Même opération reçue par un autre envoi pendant celui-ci : il l'a enregistrée.
            return _outcome(SyncOperation.objects.get(op_id=incoming.op_id), duplicate=True)
        try:
            with transaction.atomic():
                operation.result = _run(device, actor, permissions, incoming)
        except (BusinessError, DjangoValidationError, APIException) as exc:
            operation.status = SyncOperation.Status.REJECTED
            operation.result = api_exception_handler(exc, {}).data
        operation.save(update_fields=["status", "result", "updated_at"])
    return _outcome(operation)


def _run(device: Device, actor: User, permissions: frozenset[str], incoming: Incoming) -> dict:
    kind = OPERATIONS.get(incoming.type)
    if kind is None:
        raise BusinessError(UNKNOWN_OPERATION)
    needed = (kind.permission,) if isinstance(kind.permission, str) else kind.permission
    if not permissions.intersection(needed):
        raise PermissionDenied()
    serializer = kind.serializer(data=incoming.payload, context={"permissions": permissions})
    serializer.is_valid(raise_exception=True)
    return kind.apply(serializer.to_service(), device, actor)


def purge(now: datetime | None = None) -> int:
    """Efface, dans toutes les écoles et en une requête, les opérations appliquées de plus de
    `KEEP_DAYS` jours. Renvoyée plus tard, une opération effacée est appliquée de nouveau sans
    doublon : encaissement, ouverture de caisse et demande d'annulation gardent l'identifiant
    donné par l'appareil. Les refusées restent : un reçu hors ligne refusé reste « inconnu »
    (`finance/verification.py`). Rend le nombre d'opérations effacées."""
    before = (now or timezone.now()) - timedelta(days=KEEP_DAYS)
    with use_all_schools():
        deleted, _by_model = SyncOperation.all_schools.filter(
            status=SyncOperation.Status.APPLIED, created_at__lt=before
        ).delete()
    return deleted
