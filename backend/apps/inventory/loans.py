"""Prêts et retours (BIB.2, ATL.3), faits au guichet même sans réseau : ils arrivent par la
synchronisation (opérations `inventory.loan` et `inventory.return`, `sync/operations.py`), avec
l'identifiant et l'heure donnés par l'appareil.

L'appareil a déjà appliqué les règles de l'école d'après sa liste (`desk`) : nombre de prêts,
retard, ouvrage de référence. Le serveur ne refuse au rejeu que l'impossible : exemplaire perdu ou
retiré, élève qui n'est plus inscrit, et surtout **exemplaire déjà prêté à un autre** (deux
appareils hors ligne) : refusé, l'appareil le montre dans « à revoir ». Le même prêt rejoué rend
le prêt déjà enregistré ; un retour d'un exemplaire déjà rendu n'est pas un refus."""

import hashlib
from datetime import datetime, timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Membership, User
from apps.accounts.roles import LIBRARY_LEND, WORKSHOPS_MANAGE
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.inventory import losses, rules
from apps.inventory.catalogue import lock_school
from apps.inventory.models import Copy, Item, Loan
from apps.notifications import events
from apps.students.models import Enrollment, Student
from apps.sync.models import Device

COPY_UNAVAILABLE = ApiError(
    "copy_unavailable", _("This copy is lost or withdrawn: it cannot be lent."), 409
)
ALREADY_LENT = ApiError(
    "copy_already_lent",
    _("This copy is already lent to someone else: check who has it before lending it again."),
    409,
)
NOT_LENT = ApiError("copy_not_lent", _("This copy is not lent."), 409)
NOT_ENROLLED = ApiError("not_enrolled", _("This student is not enrolled this year."), 409)
MEMBER_INACTIVE = ApiError("member_inactive", _("This person no longer works at the school."), 409)
NO_MORE_EXTENSIONS = ApiError(
    "no_more_extensions", _("This loan cannot be extended any more."), 409
)
LOAN_CLOSED = ApiError("loan_closed", _("This loan is already closed."), 409)
CLOCK_AHEAD = ApiError(
    "device_clock_ahead", _("The clock of this device is ahead: set the right time."), 400
)
TAKEN_ID = ApiError("id_taken", _("This identifier is already used: update the application."), 409)
CLOCK_MARGIN = timedelta(minutes=10)
# Liste de l'appareil : exemplaires par pages.
DESK_PAGE = 2000


def permission_for(item: Item) -> str:
    """Droit de prêter cet article : guichet de la bibliothèque, ou gestion de l'atelier."""
    return LIBRARY_LEND if item.kind == Item.Kind.BOOK else WORKSHOPS_MANAGE


def check_permission(item: Item, permissions: frozenset[str]) -> None:
    if permission_for(item) not in permissions:
        raise PermissionDenied()


def current_enrollment(student: Student) -> Enrollment | None:
    return (
        Enrollment.objects.filter(
            student=student, academic_year__is_current=True, status=Enrollment.Status.ACTIVE
        )
        .select_related("class_group")
        .first()
    )


def _check_time(moment: datetime) -> None:
    if moment > timezone.now() + CLOCK_MARGIN:
        raise BusinessError(CLOCK_AHEAD)


def _loan_data(loan: Loan) -> dict:
    holder = loan.student or loan.member.user
    return {
        "number": loan.number,
        "copy": loan.copy.code,
        "item": loan.copy.item.name,
        "borrower": str(holder),
        "due_on": loan.due_on.isoformat(),
    }


def lend(
    *,
    actor: User,
    permissions: frozenset[str],
    id: UUID,
    copy: Copy,
    lent_at: datetime,
    student: Student | None = None,
    member: Membership | None = None,
    device: Device | None = None,
) -> tuple[Loan, bool]:
    """Prêt fait au guichet. Rend le prêt et `True` s'il était déjà enregistré (même identifiant,
    ou même exemplaire déjà prêté à la même personne)."""
    _check_time(lent_at)
    item = copy.item
    check_permission(item, permissions)
    existing = Loan.objects.filter(pk=id).first()
    if existing is not None:
        if existing.copy_id != copy.pk:
            raise BusinessError(TAKEN_ID)
        return existing, True
    if student is not None and current_enrollment(student) is None:
        raise BusinessError(NOT_ENROLLED)
    if member is not None and (
        not member.is_active or member.school_id != require_current_school().pk
    ):
        raise BusinessError(MEMBER_INACTIVE)
    holder = {"student": student} if student is not None else {"member": member}
    settings = rules.rules()
    with transaction.atomic():
        lock_school()
        copy = Copy.objects.select_for_update().select_related("item").get(pk=copy.pk)
        open_loan = Loan.objects.filter(copy=copy, returned_at__isnull=True).first()
        if open_loan is not None:
            same = (open_loan.student_id, open_loan.member_id) == (
                student.pk if student else None,
                member.pk if member else None,
            )
            if same:
                return open_loan, True
            raise BusinessError(ALREADY_LENT)
        if copy.state in (Copy.State.LOST, Copy.State.WITHDRAWN):
            raise BusinessError(COPY_UNAVAILABLE)
        number = (Loan.objects.aggregate(last=Max("number"))["last"] or 0) + 1
        try:
            with transaction.atomic():
                loan = Loan.objects.create(
                    id=id,
                    number=number,
                    copy=copy,
                    lent_at=lent_at,
                    due_on=rules.due_on(
                        lent_at,
                        staff=member is not None,
                        tool=item.kind == Item.Kind.TOOL,
                        settings=settings,
                    ),
                    device=device,
                    created_by=actor,
                    **holder,
                )
        except IntegrityError:
            raise BusinessError(TAKEN_ID) from None
        copy.state = Copy.State.LENT
        copy.save(update_fields=["state", "updated_at"])
        audit.record(Action.LOAN_CREATED, loan, actor=actor, after=_loan_data(loan))
        if student is not None and settings["notify_parent"]:
            events.loan_made(loan)
    return loan, False


def give_back(
    *,
    actor: User,
    permissions: frozenset[str],
    copy: Copy,
    returned_at: datetime,
    condition: str = Loan.Condition.GOOD,
) -> tuple[Loan, bool]:
    """Retour d'un exemplaire, avec son état. Rend le prêt fermé et `True` s'il l'était déjà.
    Rendu en retard par un élève : pénalité si l'école en a une (`losses.late_fee`)."""
    _check_time(returned_at)
    check_permission(copy.item, permissions)
    with transaction.atomic():
        copy = Copy.objects.select_for_update().select_related("item").get(pk=copy.pk)
        loan = (
            Loan.objects.select_for_update(of=("self",))
            .filter(copy=copy, returned_at__isnull=True)
            .select_related("student", "member__user")
            .first()
        )
        if loan is None:
            last = Loan.objects.filter(copy=copy).order_by("-lent_at").first()
            if last is None:
                raise BusinessError(NOT_LENT)
            return last, True
        loan.returned_at = max(returned_at, loan.lent_at)
        loan.return_condition = condition
        loan.returned_by = actor
        loan.save(update_fields=["returned_at", "return_condition", "returned_by", "updated_at"])
        if copy.state == Copy.State.LENT:
            copy.state = Copy.State.AVAILABLE
            copy.save(update_fields=["state", "updated_at"])
        fee = losses.late_fee(loan, actor=actor)
        audit.record(
            Action.LOAN_RETURNED,
            loan,
            actor=actor,
            after={
                **_loan_data(loan),
                "condition": condition,
                **({"late_fee": fee.amount_minor, "currency": fee.currency} if fee else {}),
            },
        )
    return loan, False


def extend(loan: Loan, *, actor: User, permissions: frozenset[str]) -> Loan:
    """Prolongation : la durée de l'emprunteur de plus, à partir de la date de retour (ou
    d'aujourd'hui pour un prêt en retard), autant de fois que les règles le permettent."""
    check_permission(loan.copy.item, permissions)
    settings = rules.rules()
    allowed = settings["staff_extensions"] if loan.member_id else settings["student_extensions"]
    with transaction.atomic():
        loan = Loan.objects.select_for_update().select_related("copy__item").get(pk=loan.pk)
        if loan.returned_at is not None:
            raise BusinessError(LOAN_CLOSED)
        if loan.extensions >= allowed or loan.copy.item.kind == Item.Kind.TOOL:
            raise BusinessError(NO_MORE_EXTENSIONS)
        before = loan.due_on
        start = max(loan.due_on, timezone.localdate())
        days = settings["staff_days"] if loan.member_id else settings["student_days"]
        loan.due_on = start + timedelta(days=days)
        loan.extensions += 1
        loan.save(update_fields=["due_on", "extensions", "updated_at"])
        audit.record(
            Action.LOAN_EXTENDED,
            loan,
            actor=actor,
            before={"due_on": before.isoformat()},
            after={"due_on": loan.due_on.isoformat(), "extensions": loan.extensions},
        )
    return loan


def open_loans() -> QuerySet[Loan]:
    return Loan.objects.filter(returned_at__isnull=True).select_related(
        "copy__item__location", "student", "member__user"
    )


def loans(*, location=None, state: str = "open", search: str = "") -> QuerySet[Loan]:
    """Prêts pour la liste : `open`, `overdue` (date de retour passée) ou `returned`."""
    queryset = Loan.objects.select_related("copy__item__location", "student", "member__user")
    if location is not None:
        queryset = queryset.filter(copy__item__location=location)
    if state == "returned":
        queryset = queryset.filter(returned_at__isnull=False).order_by("-returned_at")
    else:
        queryset = queryset.filter(returned_at__isnull=True).order_by("due_on", "number")
        if state == "overdue":
            queryset = queryset.filter(due_on__lt=timezone.localdate())
    for word in search.split():
        queryset = queryset.filter(
            Q(copy__item__name__icontains=word)
            | Q(student__last_name__icontains=word)
            | Q(student__first_name__icontains=word)
            | Q(student__matricule__icontains=word)
            | Q(member__user__last_name__icontains=word)
        )
    return queryset


# Liste de l'appareil du guichet


def desk_version(location) -> str:
    """Change dès qu'un exemplaire, un prêt ou une règle change : l'appareil ne recharge sa liste
    que dans ce cas (deux requêtes d'agrégats)."""
    copies = Copy.objects.filter(item__location=location).aggregate(
        last=Max("updated_at"), item=Max("item__updated_at"), count=Count("pk")
    )
    lent = Loan.objects.filter(copy__item__location=location).aggregate(
        last=Max("updated_at"), count=Count("pk")
    )
    raw = "|".join(str(value) for part in (copies, lent) for value in part.values())
    raw += "|" + "|".join(f"{key}={value}" for key, value in sorted(rules.rules().items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def desk_copies(location, after=None) -> list[Copy]:
    """Exemplaires en service du lieu, par pages de `DESK_PAGE` (dans l'ordre des numéros), avec
    leur prêt ouvert (`open_loan`, ou rien)."""
    queryset = (
        Copy.objects.filter(item__location=location, item__is_active=True)
        .exclude(state__in=[Copy.State.LOST, Copy.State.WITHDRAWN])
        .select_related("item")
        .order_by("number")
    )
    if after is not None:
        queryset = queryset.filter(number__gt=after)
    copies = list(queryset[: DESK_PAGE + 1])
    open_by_copy = {
        loan.copy_id: loan
        for loan in Loan.objects.filter(
            copy__in=[copy.pk for copy in copies], returned_at__isnull=True
        )
    }
    for copy in copies:
        copy.open_loan = open_by_copy.get(copy.pk)
    return copies
