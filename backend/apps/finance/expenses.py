"""Dépenses de l'école (FIN.1, `docs/04` § 4) : catégories, saisie avec justificatif, validation
au-delà d'un seuil, annulation. Montants en entiers (plus petite unité) + devise (skill `argent`).

Une dépense se saisit en une étape : sous le seuil de sa devise elle est « validée » tout de
suite ; au-dessus, elle attend `finance.approve_expense` d'une autre personne que celle qui l'a
saisie. Une dépense validée est « payée » aussitôt si elle sort de la banque ou du Mobile Money ;
payée en espèces, elle attend la sortie de caisse (`cash_outs.py`, FIN.2). Rien ne s'efface :
annuler écrit une `ExpenseCancellation` (motif, auteur, audit)."""

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.images import clean_image
from apps.core.money import Currency
from apps.core.tenancy import require_current_school
from apps.finance.models import CashOut, Expense, ExpenseCancellation, ExpenseCategory
from apps.schools.models import School

# Seuil de validation par devise, en plus petite unité : 200,00 $ et 500 000 FC (maquette).
DEFAULT_THRESHOLDS = {Currency.USD: 20_000, Currency.CDF: 500_000}
VOUCHER_MAX_SIZE = 5 * 1024 * 1024
PDF_MAGIC = b"%PDF-"

CATEGORY_NAME_TAKEN = ApiError(
    "expense_category_name_taken", _("A category with this name already exists."), 409
)
EXPENSE_ID_TAKEN = ApiError(
    "expense_id_taken", _("This identifier belongs to another expense."), 409
)
EXPENSE_DECIDED = ApiError("expense_decided", _("This expense was already decided."), 409)
OWN_EXPENSE = ApiError("own_expense", _("Someone else must approve an expense you recorded."), 403)
EXPENSE_CANCELLED = ApiError("expense_cancelled", _("This expense is cancelled."), 409)
PAID_FROM_CASH_DESK = ApiError(
    "expense_paid_from_cash_desk",
    _("This expense left the cash desk: cancel its cash-out while the session is open."),
    409,
)
CATEGORY_INACTIVE = ApiError(
    "expense_category_inactive", _("This category is no longer in use."), 409
)


# Seuils


def thresholds(school: School) -> dict[str, int]:
    saved = (school.settings or {}).get("expenses", {}).get("approval_threshold_minor", {})
    return {code: int(saved.get(code, default)) for code, default in DEFAULT_THRESHOLDS.items()}


def update_thresholds(*, actor: User, values: dict[str, int]) -> dict[str, int]:
    school = require_current_school()
    with transaction.atomic():
        before = thresholds(school)
        school.settings = {
            **(school.settings or {}),
            "expenses": {"approval_threshold_minor": {**before, **values}},
        }
        school.save(update_fields=["settings", "updated_at"])
        before, after = audit.changes(before, thresholds(school))
        if after:
            audit.record(
                Action.FINANCE_EXPENSE_SETTINGS_UPDATED,
                school,
                actor=actor,
                before=before,
                after=after,
            )
    return thresholds(school)


# Catégories


def create_category(*, actor: User, name: str) -> ExpenseCategory:
    require_current_school()
    with transaction.atomic():
        if ExpenseCategory.objects.filter(name__iexact=name).exists():
            raise BusinessError(CATEGORY_NAME_TAKEN)
        category = ExpenseCategory.objects.create(name=name, created_by=actor)
        audit.record(
            Action.FINANCE_EXPENSE_CATEGORY_CREATED,
            category,
            actor=actor,
            after={"name": name},
        )
    return category


def update_category(category: ExpenseCategory, *, actor: User, **fields) -> ExpenseCategory:
    with transaction.atomic():
        if (
            "name" in fields
            and ExpenseCategory.objects.filter(name__iexact=fields["name"])
            .exclude(pk=category.pk)
            .exists()
        ):
            raise BusinessError(CATEGORY_NAME_TAKEN)
        before = {"name": category.name, "is_active": category.is_active}
        label = str(category)
        for field, value in fields.items():
            setattr(category, field, value)
        before, after = audit.changes(
            before, {"name": category.name, "is_active": category.is_active}
        )
        if after:
            category.save()
            audit.record(
                Action.FINANCE_EXPENSE_CATEGORY_UPDATED,
                category,
                actor=actor,
                before=before,
                after=after,
                label=label,
            )
    return category


# Justificatif : photo (ré-encodée) ou PDF, 5 Mo au plus.


def clean_voucher(file) -> ContentFile:
    if file.size > VOUCHER_MAX_SIZE:
        raise ValidationError(_("The voucher must not exceed 5 MB."), code="voucher_too_large")
    file.seek(0)
    if file.read(len(PDF_MAGIC)) == PDF_MAGIC:
        file.seek(0)
        return ContentFile(file.read(), name="voucher.pdf")
    return clean_image(file, max_size=VOUCHER_MAX_SIZE)


# Dépenses


def expenses():
    """Avec le numéro du bon de sortie qui la paie (`cash_out_number`, FIN.2), une sous-requête."""
    live_cash_out = CashOut.objects.filter(
        expense=OuterRef("pk"), cancellation__isnull=True
    ).order_by("-paid_at")
    return Expense.objects.select_related(
        "category", "requested_by", "decided_by", "cancellation"
    ).annotate(cash_out_number=Subquery(live_cash_out.values("number")[:1]))


def _data(expense: Expense) -> dict:
    return {
        "number": expense.number,
        "category": expense.category.name,
        "beneficiary": expense.beneficiary,
        "amount_minor": expense.amount_minor,
        "currency": expense.currency,
        "account": expense.account,
        "status": expense.status,
    }


def _next_number(school: School, spent_on) -> str:
    """DEP-26-0048 : suite de l'année civile de la dépense, sous verrou de l'école (deux saisies
    en même temps ne prennent pas le même numéro)."""
    School.objects.select_for_update().get(pk=school.pk)
    year = spent_on.year
    count = Expense.objects.filter(spent_on__year=year).count()
    return f"DEP-{year % 100:02d}-{count + 1:04d}"


def record_expense(
    *,
    actor: User,
    category: ExpenseCategory,
    beneficiary: str,
    reason: str,
    amount_minor: int,
    currency: str,
    spent_on,
    account: str,
    voucher=None,
    expense_id=None,
) -> tuple[Expense, bool]:
    """Saisir une dépense. Rejouer le même `expense_id` rend la dépense déjà enregistrée
    (`created` faux)."""
    school = require_current_school()
    with transaction.atomic():
        if expense_id is not None:
            existing = Expense.objects.filter(pk=expense_id).first()
            if existing is not None:
                if existing.requested_by_id != actor.pk:
                    raise BusinessError(EXPENSE_ID_TAKEN)
                return existing, False
        if not category.is_active:
            raise BusinessError(CATEGORY_INACTIVE)
        needs_approval = amount_minor > thresholds(school)[currency]
        expense = Expense(
            number=_next_number(school, spent_on),
            category=category,
            beneficiary=beneficiary,
            reason=reason,
            amount_minor=amount_minor,
            currency=currency,
            spent_on=spent_on,
            account=account,
            requested_by=actor,
            created_by=actor,
            status=Expense.Status.PENDING if needs_approval else Expense.Status.APPROVED,
        )
        if expense_id is not None:
            expense.pk = expense_id
        if not needs_approval:
            expense.decided_at = timezone.now()
        if voucher is not None:
            expense.voucher.save(voucher.name, clean_voucher(voucher), save=False)
        _pay_if_not_cash(expense)
        expense.save()
        audit.record(Action.FINANCE_EXPENSE_RECORDED, expense, actor=actor, after=_data(expense))
    return expense, True


def _pay_if_not_cash(expense: Expense) -> None:
    """Banque, Mobile Money : payée dès la validation. Espèces : sortie de caisse (FIN.2)."""
    if expense.status == Expense.Status.APPROVED and expense.account != Expense.Account.CASH:
        expense.status = Expense.Status.PAID
        expense.paid_at = timezone.now()


def decide_expense(expense: Expense, *, actor: User, approve: bool, note: str = "") -> Expense:
    """Valider ou refuser une dépense en attente ; jamais la sienne."""
    with transaction.atomic():
        expense = Expense.objects.select_for_update(of=("self",)).get(pk=expense.pk)
        if expense.status != Expense.Status.PENDING:
            raise BusinessError(EXPENSE_DECIDED)
        if expense.requested_by_id == actor.pk:
            raise BusinessError(OWN_EXPENSE)
        before = _data(expense)
        expense.status = Expense.Status.APPROVED if approve else Expense.Status.REJECTED
        expense.decided_by = actor
        expense.decided_at = timezone.now()
        expense.decision_note = note
        if approve:
            _pay_if_not_cash(expense)
        expense.save()
        before, after = audit.changes(before, _data(expense))
        audit.record(
            Action.FINANCE_EXPENSE_APPROVED if approve else Action.FINANCE_EXPENSE_REJECTED,
            expense,
            actor=actor,
            before=before,
            after={**after, "note": note},
        )
    return expense


def cancel_expense(expense: Expense, *, actor: User, reason: str) -> ExpenseCancellation:
    """Annuler : une nouvelle ligne liée, la dépense reste (FIN.1). Sortie de la caisse
    (FIN.2) : l'argent est parti, seule la sortie s'annule, tant que sa session est ouverte."""
    with transaction.atomic():
        expense = Expense.objects.select_for_update(of=("self",)).get(pk=expense.pk)
        if ExpenseCancellation.objects.filter(expense=expense).exists():
            raise BusinessError(EXPENSE_CANCELLED)
        if CashOut.objects.filter(expense=expense, cancellation__isnull=True).exists():
            raise BusinessError(PAID_FROM_CASH_DESK)
        cancellation = ExpenseCancellation.objects.create(
            expense=expense, reason=reason, cancelled_by=actor, created_by=actor
        )
        audit.record(
            Action.FINANCE_EXPENSE_CANCELLED,
            expense,
            actor=actor,
            before=_data(expense),
            after={"cancelled": True, "reason": reason},
        )
    return cancellation


def summary(queryset) -> dict:
    """Chiffres de l'écran « Dépenses » pour la liste filtrée, par devise : une requête."""
    live = queryset.filter(cancellation__isnull=True)
    rows = live.values("currency").annotate(
        spent=Sum("amount_minor", filter=Q(status=Expense.Status.PAID)),
        pending=Sum("amount_minor", filter=Q(status=Expense.Status.PENDING)),
        pending_count=Count("pk", filter=Q(status=Expense.Status.PENDING)),
        cash=Sum(
            "amount_minor",
            filter=Q(account=Expense.Account.CASH, status=Expense.Status.PAID),
        ),
    )
    cancelled = (
        queryset.filter(cancellation__isnull=False)
        .values("currency")
        .annotate(total=Sum("amount_minor"), count=Count("pk"))
    )
    return {"by_currency": list(rows), "cancelled": list(cancelled)}
