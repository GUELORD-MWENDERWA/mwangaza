"""Constats de perte ou d'abîmé, et pénalité de retard (BIB.3, ATL.3).

Un constat ferme le prêt ouvert de l'exemplaire et le sort du catalogue (« perdu » ou « retiré »).
Pour un élève, des frais de remplacement (le prix de l'article par défaut, modifiable avec la
remarque) deviennent une dette : un `StudentCharge` (source `item`), payé à la caisse avec un reçu
normal, solde et crédit comme tout frais (règles de l'argent : entiers et devise). Le personnel
n'a pas de dette dans Mwangaza : le constat est seulement noté.

Jamais effacé : une erreur se corrige par un constat de rectification (droit `inventory.validate`),
qui remet l'exemplaire en service et retire la dette tant qu'elle n'a rien reçu (sinon, annuler
d'abord le paiement). Les frais vont sous un type de frais de l'école, « Matériel perdu ou
abîmé », créé au premier besoin (nommé dans la langue de la plateforme, renommable)."""

from django.conf import settings as django_settings
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.money import Currency
from apps.core.tenancy import require_current_school
from apps.finance import services as finance
from apps.finance.models import FeeType, StudentCharge
from apps.inventory import rules
from apps.inventory.models import Copy, Loan, LossReport
from apps.notifications import events
from apps.schools.models import School
from apps.students.models import Enrollment, Student
from apps.sync import changes as sync_changes

ALREADY_OUT = ApiError("copy_already_out", _("This copy is already lost or withdrawn."), 409)
ALREADY_CORRECTED = ApiError(
    "report_already_corrected", _("This report has already been corrected."), 409
)
NOT_CORRECTABLE = ApiError("report_not_correctable", _("A correction cannot be corrected."), 409)
CHARGE_PAID = ApiError(
    "charge_paid",
    _("The fees of this report have already received a payment: cancel the payment first."),
    409,
)
AMOUNT_CURRENCY = ApiError("amount_currency", _("Give the currency of the replacement fees."), 400)
# Libellé d'un frais dû : 40 signes au plus (`StudentCharge.label`).
LABEL_LENGTH = 40
FEE_TYPE_KEY = "inventory_fee_type"


def fee_type(actor: User | None) -> tuple[FeeType, bool]:
    """Type de frais des objets perdus, abîmés ou rendus en retard ; `True` s'il vient d'être
    créé (les appareils de la caisse doivent le recevoir)."""
    school = School.objects.select_for_update().get(pk=require_current_school().pk)
    found = FeeType.objects.filter(pk=school.settings.get(FEE_TYPE_KEY)).first()
    if found is not None:
        return found, False
    with translation.override(django_settings.LANGUAGE_CODE):
        name = gettext("Lost or damaged items")
    found = FeeType.objects.filter(name__iexact=name).first()
    created = found is None
    if created:
        found = FeeType.objects.create(
            name=name, category=FeeType.Category.CUSTOM, created_by=actor
        )
    school.settings = {**school.settings, FEE_TYPE_KEY: str(found.pk)}
    school.save(update_fields=["settings", "updated_at"])
    return found, created


def _enrollment(student: Student) -> Enrollment | None:
    """Inscription de l'année en cours, sinon la dernière : un élève parti doit encore son livre."""
    enrollments = Enrollment.objects.filter(student=student)
    return (
        enrollments.filter(academic_year__is_current=True).first()
        or enrollments.order_by("-created_at").first()
    )


def _charge(student: Student, *, label: str, amount_minor: int, currency: str, actor: User):
    enrollment = _enrollment(student)
    if enrollment is None:
        return None
    kind, created = fee_type(actor)
    charge = StudentCharge.objects.create(
        enrollment=enrollment,
        fee_type=kind,
        label=label[:LABEL_LENGTH],
        amount_minor=amount_minor,
        currency=currency,
        due_on=timezone.localdate(),
        source=StudentCharge.Source.ITEM,
        created_by=actor,
    )
    if created:
        sync_changes.touch_config()
    sync_changes.touch_enrollments([enrollment.pk])
    return charge


def report(
    copy: Copy,
    *,
    actor: User,
    kind: str,
    note: str,
    amount_minor: int | None = None,
    currency: str = "",
) -> LossReport:
    """Constat de perte (`lost`) ou d'abîmé (`damaged`) d'un exemplaire, prêté ou non. Sans
    montant donné : le prix de l'article."""
    with transaction.atomic():
        copy = Copy.objects.select_for_update().select_related("item").get(pk=copy.pk)
        if copy.state in (Copy.State.LOST, Copy.State.WITHDRAWN):
            raise BusinessError(ALREADY_OUT)
        item = copy.item
        if amount_minor is None:
            amount_minor, currency = item.price_minor or 0, item.currency
        if amount_minor and currency not in Currency.values:
            raise BusinessError(AMOUNT_CURRENCY)
        loan = (
            Loan.objects.select_for_update(of=("self",))
            .filter(copy=copy, returned_at__isnull=True)
            .select_related("student", "member__user")
            .first()
        )
        lost = kind == LossReport.Kind.LOST
        if loan is not None:
            loan.returned_at = timezone.now()
            loan.return_condition = Loan.Condition.LOST if lost else Loan.Condition.DAMAGED
            loan.returned_by = actor
            loan.save(
                update_fields=["returned_at", "return_condition", "returned_by", "updated_at"]
            )
        copy.state = Copy.State.LOST if lost else Copy.State.WITHDRAWN
        copy.save(update_fields=["state", "updated_at"])
        charge = None
        student = loan.student if loan is not None else None
        if student is not None and amount_minor > 0:
            label = gettext("Lost") if lost else gettext("Damaged")
            charge = _charge(
                student,
                label=f"{label} — {copy.code}",
                amount_minor=amount_minor,
                currency=currency,
                actor=actor,
            )
        created = LossReport.objects.create(
            copy=copy,
            loan=loan,
            kind=kind,
            note=note,
            amount_minor=amount_minor,
            currency=currency if amount_minor else "",
            charge=charge,
            created_by=actor,
        )
        audit.record(
            Action.LOSS_REPORTED,
            created,
            actor=actor,
            label=f"{copy.code} · {item.name}",
            after={
                "kind": kind,
                "note": note,
                "borrower": str(student or (loan.member.user if loan else "")),
                "amount_minor": amount_minor,
                "currency": currency if amount_minor else "",
                "charged": charge is not None,
            },
        )
        if charge is not None:
            events.loss_reported(created, student)
    return created


def correct(original: LossReport, *, actor: User, note: str) -> LossReport:
    """Rectification d'un constat fait par erreur : l'exemplaire revient en service, la dette
    encore impayée est retirée. Le prêt reste fermé (l'exemplaire est de retour)."""
    with transaction.atomic():
        original = LossReport.objects.select_for_update().get(pk=original.pk)
        if original.kind == LossReport.Kind.CORRECTION:
            raise BusinessError(NOT_CORRECTABLE)
        if LossReport.objects.filter(corrects=original).exists():
            raise BusinessError(ALREADY_CORRECTED)
        if original.charge_id is not None:
            charges = StudentCharge.objects.filter(pk=original.charge_id)
            if finance.paid_charge_ids(charges):
                raise BusinessError(CHARGE_PAID)
            charge = charges.select_for_update().get()
            charge.status = StudentCharge.Status.REMOVED
            charge.save(update_fields=["status", "updated_at"])
            sync_changes.touch_enrollments([charge.enrollment_id])
        copy = Copy.objects.select_for_update().select_related("item").get(pk=original.copy_id)
        copy.state = Copy.State.AVAILABLE
        copy.save(update_fields=["state", "updated_at"])
        correction = LossReport.objects.create(
            copy=copy,
            loan=original.loan,
            kind=LossReport.Kind.CORRECTION,
            note=note,
            corrects=original,
            created_by=actor,
        )
        audit.record(
            Action.LOSS_CORRECTED,
            correction,
            actor=actor,
            label=f"{copy.code} · {copy.item.name}",
            before={"kind": original.kind, "charge_removed": original.charge_id is not None},
            after={"note": note},
        )
    return correction


def late_fee(loan: Loan, *, actor: User) -> StudentCharge | None:
    """Pénalité d'un prêt rendu en retard par un élève, si l'école en a une : tant par jour de
    retard, plafonnée au prix de l'article dans la même devise."""
    settings = rules.rules()
    per_day = settings["late_fee_minor"]
    if not per_day or loan.student_id is None or loan.returned_at is None:
        return None
    days = (timezone.localdate(loan.returned_at) - loan.due_on).days
    if days <= 0:
        return None
    currency = settings["late_fee_currency"]
    amount = per_day * days
    item = loan.copy.item
    if item.price_minor and item.currency == currency:
        amount = min(amount, item.price_minor)
    if amount <= 0:
        return None
    return _charge(
        loan.student,
        label=f"{gettext('Late')} — {loan.copy.code}",
        amount_minor=amount,
        currency=currency,
        actor=actor,
    )
