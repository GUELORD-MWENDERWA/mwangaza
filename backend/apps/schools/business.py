"""Tableau de bord des affaires de la plateforme (CON.1) : où en sont les écoles payantes, ce qui
est facturé, encaissé et dû, les contrats à renouveler, les demandes de démonstration ouvertes.

Espaces réels seulement. Calculé en SQL (agrégats par statut et par devise) et **gardé 5 minutes**
dans le cache : dix ouvertures de l'écran ne font qu'un calcul. Les montants ne sont jamais
additionnés entre devises. Ce que chaque membre de l'équipe voit dépend de ses droits (EQ.1) ; le
cache garde tout, le filtre se fait à la sortie (`for_rights`)."""

from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts import platform_roles as team
from apps.billing import invoicing
from apps.billing.models import Contract, Invoice, InvoicePayment
from apps.core.models import DemoRequest
from apps.schools.models import School
from apps.students.models import Enrollment

TTL_SECONDS = 300
CACHE_KEY = "console.business"
RENEWAL_DAYS = 30
RENEWALS_SHOWN = 10
LIVE = School.Environment.LIVE
# Une demande est « ouverte » tant qu'on n'a ni signé ni perdu le prospect.
OPEN_PROSPECTS = (DemoRequest.Status.NEW, DemoRequest.Status.CALLED, DemoRequest.Status.TRIAL)
STATES = ("trial", "active", "readonly", "suspended", "stopped")


def _schools_by_state() -> dict:
    counts = dict(
        School.objects.filter(environment=LIVE)
        .values_list("status")
        .annotate(count=Count("id"))
        .order_by()
    )
    return {state: counts.get(state, 0) for state in STATES}


def _billed_students() -> int:
    """Élèves des écoles qui paient (active ou lecture seule), année en cours de chacune."""
    return Enrollment.all_schools.filter(
        school__environment=LIVE,
        school__status__in=[School.Status.ACTIVE, School.Status.READ_ONLY],
        status="active",
        academic_year__is_current=True,
    ).count()


def _money(day: date) -> list[dict]:
    """Par devise : facturé et encaissé ce mois-ci, reste dû, dont échu."""
    first = day.replace(day=1)
    rows: dict[str, dict] = {}

    def row(currency: str) -> dict:
        return rows.setdefault(
            currency,
            {"currency": currency, "invoiced": 0, "collected": 0, "outstanding": 0, "overdue": 0},
        )

    live_invoices = Invoice.all_schools.filter(
        school__environment=LIVE, kind=Invoice.Kind.INVOICE, credit_note__isnull=True
    )
    for item in (
        live_invoices.filter(issued_on__gte=first, issued_on__lte=day)
        .values("currency")
        .annotate(total=Sum("total"))
        .order_by()
    ):
        row(item["currency"])["invoiced"] = item["total"]

    payments = InvoicePayment.all_schools.filter(
        school__environment=LIVE, paid_on__gte=first, paid_on__lte=day
    )
    for item in payments.values("invoice__currency", "reverses").annotate(total=Sum("amount")):
        sign = -1 if item["reverses"] else 1
        row(item["invoice__currency"])["collected"] += sign * item["total"]

    # Reste dû : factures dont le solde est positif (peu nombreuses, une requête annotée).
    for invoice in invoicing.with_balance(live_invoices):
        due = invoicing.balance(invoice)
        if due > 0:
            entry = row(invoice.currency)
            entry["outstanding"] += due
            if invoice.due_on < day:
                entry["overdue"] += due
    return sorted(rows.values(), key=lambda r: r["currency"])


def _renewals(day: date) -> dict:
    contracts = Contract.all_schools.filter(
        school__environment=LIVE,
        status=Contract.Status.ACTIVE,
        end_date__lte=day + timedelta(days=RENEWAL_DAYS),
    ).select_related("school")
    items = [
        {
            "school_id": c.school_id,
            "code": c.school.code,
            "name": c.school.name,
            "end_date": c.end_date,
            "auto_renew": c.auto_renew,
        }
        for c in contracts.order_by("end_date")[:RENEWALS_SHOWN]
    ]
    return {"count": contracts.count(), "items": items}


def compute(day: date | None = None) -> dict:
    day = day or timezone.localdate()
    live = School.objects.filter(environment=LIVE)
    return {
        "day": day,
        "schools": _schools_by_state(),
        "trials_ending": live.filter(
            status=School.Status.TRIAL, trial_ends_on__lte=day + timedelta(days=RENEWAL_DAYS)
        ).count(),
        "billed_students": _billed_students(),
        "money": _money(day),
        "renewals": _renewals(day),
        "prospects_open": DemoRequest.objects.filter(status__in=OPEN_PROSPECTS).count(),
    }


def for_rights(rights: frozenset[str] | set[str]) -> dict:
    """Chiffres gardés 5 minutes, réduits à ce que les droits permettent : une section sans le
    droit est absente (`None`), jamais seulement cachée par l'écran."""
    data = cache.get(CACHE_KEY)
    if data is None:
        data = compute()
        cache.set(CACHE_KEY, data, TTL_SECONDS)
    schools = team.SCHOOLS_VIEW in rights
    billing = team.BILLING_MANAGE in rights
    return {
        "day": data["day"],
        "schools": data["schools"] if schools else None,
        "trials_ending": data["trials_ending"] if schools else None,
        "billed_students": data["billed_students"] if schools else None,
        "money": data["money"] if billing else None,
        "renewals": data["renewals"] if billing else None,
        "prospects_open": data["prospects_open"] if team.LEADS_MANAGE in rights else None,
    }


# Exports Excel de la console (CON.1) : espaces réels seulement, un classeur d'une feuille. Les
# lignes sont lues en flux (`iterator`) et écrites en mode `write_only` ; un classeur de quelques
# centaines de lignes (une par école, par facture ou par paiement) se génère dans la requête.
EXPORTS = {
    "schools": team.SCHOOLS_VIEW,
    "invoices": team.BILLING_MANAGE,
    "payments": team.BILLING_MANAGE,
}


def _rows(kind: str):
    """(en-têtes, lignes) de l'export `kind`, montants en unités entières de la devise (centimes
    ou francs) avec leur code de devise."""
    if kind == "schools":
        from apps.schools.console import schools as school_rows

        rows = school_rows().filter(environment=LIVE).order_by("name")
        return (
            [
                _("Code"),
                _("Name"),
                _("Status"),
                _("Plan"),
                _("Students"),
                _("Trial until"),
                _("Paid until"),
                _("Contact"),
                _("Phone"),
                _("Email"),
                _("Last activity"),
            ],
            (
                [
                    s.code,
                    s.name,
                    s.status,
                    s.plan,
                    s.student_count,
                    s.trial_ends_on,
                    s.paid_until,
                    s.contact_name,
                    s.contact_phone,
                    s.contact_email,
                    s.last_activity_at.replace(tzinfo=None) if s.last_activity_at else None,
                ]
                for s in rows.iterator(chunk_size=500)
            ),
        )
    if kind == "invoices":
        invoices = (
            Invoice.all_schools.filter(school__environment=LIVE)
            .select_related("school")
            .order_by("-issued_on", "number")
        )
        return (
            [
                _("Number"),
                _("Type"),
                _("School"),
                _("Issued on"),
                _("Due on"),
                _("Currency"),
                _("Total"),
            ],
            (
                [i.number, i.kind, i.school.name, i.issued_on, i.due_on, i.currency, i.total]
                for i in invoices.iterator(chunk_size=500)
            ),
        )
    payments = (
        InvoicePayment.all_schools.filter(school__environment=LIVE)
        .select_related("school", "invoice")
        .order_by("-paid_on")
    )
    return (
        [
            _("Invoice"),
            _("School"),
            _("Paid on"),
            _("Method"),
            _("Reference"),
            _("Currency"),
            _("Amount"),
            _("Reversal"),
        ],
        (
            [
                p.invoice.number,
                p.school.name,
                p.paid_on,
                p.method,
                p.reference,
                p.invoice.currency,
                -p.amount if p.reverses_id else p.amount,
                _("yes") if p.reverses_id else "",
            ]
            for p in payments.iterator(chunk_size=500)
        ),
    )


def export_workbook(kind: str) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    headers, rows = _rows(kind)
    book = Workbook(write_only=True)
    sheet = book.create_sheet(kind)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()
