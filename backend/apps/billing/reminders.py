"""Échéances de l'abonnement (ABO.3) : rappels avant et après la date, puis **lecture seule**
plutôt que coupure. L'école garde ses données, ses reçus et ses bulletins ; l'écriture se ferme
(caisse comprise) jusqu'au paiement. Décidé le 2026-10-13.

Appelé par le passage `tick` des notifications (pas de tâche planifiée en plus) : une requête sur
les factures impayées, puis seules les écoles concernées sont servies."""

from datetime import date, timedelta

from django.utils import translation
from django.utils.translation import gettext as _

from apps.billing import invoicing
from apps.billing.models import Invoice
from apps.core.tenancy import use_all_schools
from apps.schools.models import School

# Jours après l'échéance avant la lecture seule ; rappels : N jours avant, le jour même, et 7 jours
# après.
GRACE_DAYS = 15
REMINDER_OFFSETS = (-7, 0, 7)
SWITCHABLE = (School.Status.ACTIVE, School.Status.READ_ONLY)


def unpaid(day: date) -> dict[int, list[Invoice]]:
    """Factures encore dues, par école : celles qui tombent d'ici une semaine ou sont échues."""
    with use_all_schools():
        rows = invoicing.with_balance(
            Invoice.all_schools.filter(kind=Invoice.Kind.INVOICE, credit_note__isnull=True)
        ).select_related("school")
        result: dict[int, list[Invoice]] = {}
        for invoice in rows:
            if invoicing.balance(invoice) > 0:
                result.setdefault(invoice.school_id, []).append(invoice)
    return result


def sync_status(school: School, invoices: list[Invoice], day: date, *, actor=None) -> str | None:
    """Passe l'école en lecture seule si une facture est impayée au-delà du délai de grâce, et la
    rouvre quand plus aucune ne l'est. Rend le nouvel état, ou `None` si rien ne change. Ne touche
    ni un essai, ni une école suspendue ou arrêtée."""
    from apps.schools import lifecycle
    from apps.schools.services import tell_school, update_school

    if school.status not in SWITCHABLE:
        return None
    overdue = any(i.due_on + timedelta(days=GRACE_DAYS) < day for i in invoices)
    wanted = School.Status.READ_ONLY if overdue else School.Status.ACTIVE
    if wanted == school.status:
        return None
    update_school(school, actor=actor, status=wanted)
    tell_school(
        school, lifecycle.READ_ONLY if wanted == School.Status.READ_ONLY else lifecycle.REOPENED
    )
    return wanted


def refresh(school: School, *, actor=None, day: date | None = None) -> str | None:
    """Même vérification tout de suite pour une école (après un paiement ou un avoir)."""
    return sync_status(
        school, unpaid(day or date.today()).get(school.pk, []), day or date.today(), actor=actor
    )


def reminder_text(invoice: Invoice, offset: int, language: str) -> tuple[str, str]:
    from django.utils import formats

    from apps.core.money import format_amount

    with translation.override(language):
        amount = format_amount(invoicing.balance(invoice), invoice.currency)
        when = formats.date_format(invoice.due_on, "j F Y")
        if offset < 0:
            return (_("Invoice %(n)s due on %(d)s") % {"n": invoice.number, "d": when}, amount)
        if offset == 0:
            return (_("Invoice %(n)s is due today") % {"n": invoice.number}, amount)
        return (
            _("Invoice %(n)s is late (due on %(d)s)") % {"n": invoice.number, "d": when},
            _("%(a)s. Without payment, the school becomes read-only.") % {"a": amount},
        )
