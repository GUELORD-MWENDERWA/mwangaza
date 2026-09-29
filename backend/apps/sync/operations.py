"""Opérations envoyées par les appareils (`POST /api/sync/push`, 3.3.2), appliquées dans
l'ordre, chacune une seule fois (`SyncOperation`).

Chaque type d'opération donne le droit exigé, le contenu attendu (serializer) et le service
appelé : encaissement (3.3.2), ouverture de caisse et réimpression (3.5.2), crédit utilisé à la
caisse (3.6.2), demande d'annulation (3.8.1). Une opération hors ligne de plus (clôture de
caisse : 3.8.2) est une entrée de plus dans `OPERATIONS`."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied

from apps.accounts.models import User
from apps.accounts.roles import (
    FINANCE_COLLECT_PAYMENT,
    FINANCE_REQUEST_CANCELLATION,
    FINANCE_VIEW_REPORTS,
)
from apps.core.errors import ApiError, BusinessError, api_exception_handler
from apps.finance import services as finance
from apps.finance.models import CashRegister, Payment, StudentCredit
from apps.finance.serializers import PaymentCreateSerializer
from apps.sync.models import Device, SyncOperation

UNKNOWN_OPERATION = ApiError(
    "unknown_operation", _("This application is out of date: update it."), 400
)
DUPLICATE = "duplicate"


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
    """Caisse prise entre-temps, ou caissier qui a déjà une autre caisse ouverte : refusée (les
    encaissements de cette session le seront aussi : 3.8)."""
    session = finance.open_cash_session(
        actor=actor,
        cash_register=data["cash_register"],
        session_id=data["id"],
        opened_at=data["opened_at"],
    )
    return {"cash_session": str(session.pk)}


class OfflineReprintSerializer(serializers.Serializer):
    """Réimpression hors ligne (F6) : le duplicata est déjà imprimé par l'appareil."""

    payment = serializers.PrimaryKeyRelatedField(queryset=Payment.objects)
    reprinted_at = serializers.DateTimeField(help_text="Heure de l'appareil à la réimpression.")

    def to_service(self) -> dict:
        return dict(self.validated_data)


def _reprint(data: dict, device: Device, actor: User) -> dict:
    payment = data["payment"]
    # La caisse de l'appareil ne montre que les paiements de la session du caissier.
    if payment.cash_session.cashier_id != actor.pk:
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
    if data["own_only"] and payment.cash_session.cashier_id != actor.pk:
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


@dataclass(frozen=True)
class OperationType:
    permission: str
    serializer: type[serializers.Serializer]
    apply: Callable[[dict, Device, User], dict]


OPERATIONS = {
    "payment.create": OperationType(
        FINANCE_COLLECT_PAYMENT, OfflinePaymentSerializer, _create_payment
    ),
    "cash_session.open": OperationType(
        FINANCE_COLLECT_PAYMENT, OfflineSessionSerializer, _open_session
    ),
    "payment.reprint": OperationType(FINANCE_COLLECT_PAYMENT, OfflineReprintSerializer, _reprint),
    "credit.use": OperationType(FINANCE_COLLECT_PAYMENT, OfflineCreditSerializer, _use_credit),
    "cancellation.request": OperationType(
        FINANCE_REQUEST_CANCELLATION, OfflineCancellationSerializer, _request_cancellation
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
    if kind.permission not in permissions:
        raise PermissionDenied()
    serializer = kind.serializer(data=incoming.payload, context={"permissions": permissions})
    serializer.is_valid(raise_exception=True)
    return kind.apply(serializer.to_service(), device, actor)
