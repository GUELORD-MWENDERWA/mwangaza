"""Reprise en cours d'année (E6, 4.19) : une école qui commence après la rentrée importe d'un
fichier Excel ce que chaque élève avait déjà payé. Chaque ligne devient un `Payment` d'origine
`prior` : hors caisse (pas de session, donc ni caisse du jour, ni clôture, ni « encaissé »), sans
reçu, réparti comme à la caisse sur les échéances les plus anciennes de sa devise. Une erreur se
corrige par l'annulation habituelle.

Ni table ni tâche de fond : `check` lit le fichier et rend l'aperçu ; à la validation, le même
fichier est renvoyé et `record` le vérifie de nouveau sous verrou, puis refuse si le résultat
n'est plus celui de l'aperçu. Un élève qui a déjà une reprise dans une devise n'en reçoit pas
d'autre d'un fichier suivant : un fichier envoyé deux fois ne double rien.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import workbook
from apps.core.errors import ApiError, BusinessError
from apps.core.money import Currency, Money
from apps.core.tenancy import require_current_school
from apps.finance import services
from apps.finance.models import FeeType, Payment, PaymentAllocation
from apps.schools import organisation
from apps.schools.models import School
from apps.students import imports
from apps.students.models import Enrollment
from apps.sync import changes as sync_changes

# Même plafond qu'à la caisse.
MAX_AMOUNT_MINOR = 10**12
AMOUNT = re.compile(r"\d+(\.\d{1,2})?")
# Aperçu : les erreurs d'abord (toutes celles qu'un écran peut montrer), quelques lignes prêtes.
MAX_ERRORS = 300
MAX_READY = 20

TITLES = {
    "matricule": {"matricule", "numeromatricule", "nmatricule", "studentnumber", "number"},
    "amount": {"montantpaye", "montant", "dejapaye", "paye", "amountpaid", "amount", "paid"},
    "currency": {"devise", "monnaie", "currency"},
    "fee": {"frais", "typedefrais", "fee", "feetype"},
}
CURRENCIES = {
    "usd": Currency.USD,
    "$": Currency.USD,
    "us$": Currency.USD,
    "dollar": Currency.USD,
    "dollars": Currency.USD,
    "cdf": Currency.CDF,
    "fc": Currency.CDF,
    "franc": Currency.CDF,
    "francs": Currency.CDF,
}

NO_CURRENT_YEAR = ApiError(
    "no_current_year", _("No current school year: choose one before this import."), 409
)
MISSING_COLUMN = ApiError(
    "missing_column",
    _("The file needs a student number column and an amount paid column: use the template."),
    400,
)
NOTHING_TO_RECORD = ApiError("nothing_to_record", _("No row can be recorded."), 409)
PREVIEW_OUTDATED = ApiError(
    "preview_outdated",
    _("The file or the students' accounts changed since the preview: check it again."),
    409,
)


@dataclass
class Line:
    """Une ligne du fichier qui porte un montant : prête (`allocation`) ou en erreur (`issues`,
    codes traduits par l'écran)."""

    number: int
    matricule: str
    amount: str
    currency: str = ""
    fee: str = ""
    amount_minor: int | None = None
    enrollment: Enrollment | None = None
    issues: list[dict] = field(default_factory=list)
    allocation: list = field(default_factory=list)

    def refuse(self, code: str, **params) -> None:
        self.issues.append({"code": code, **params})


@dataclass
class Preview:
    lines: list[Line]
    empty: int

    @property
    def ready(self) -> list[Line]:
        return [line for line in self.lines if not line.issues]

    @property
    def errors(self) -> list[Line]:
        return [line for line in self.lines if line.issues]

    @property
    def totals(self) -> list[dict]:
        """Par devise (dollars d'abord), jamais additionnées."""
        amounts = defaultdict(list)
        for line in self.ready:
            amounts[line.currency].append(line.amount_minor)
        return [
            {
                "currency": currency,
                "amount_minor": sum(amounts[currency]),
                "count": len(amounts[currency]),
            }
            for currency in Currency.values
            if currency in amounts
        ]


def _amount(text: str, currency: str) -> int | None:
    """« 1 500,50 » → 150050 pour des dollars ; `None` si le montant est illisible, nul, négatif
    ou plus précis que la devise (pas d'arrondi caché). Jamais de `float`. Trois chiffres après
    le séparateur sont refusés : « 25,000 » peut vouloir dire vingt-cinq mille."""
    cleaned = "".join(text.split()).replace(",", ".")
    if not AMOUNT.fullmatch(cleaned):
        return None
    try:
        amount = Money.from_major(cleaned, currency).amount_minor
    except ValueError:
        return None
    return amount if 0 < amount <= MAX_AMOUNT_MINOR else None


def _columns(headers: list[str]) -> dict[str, int | None]:
    keys = [imports._key(header) for header in headers]
    columns = {
        name: next((i for i, key in enumerate(keys) if key in titles), None)
        for name, titles in TITLES.items()
    }
    if columns["matricule"] is None or columns["amount"] is None:
        raise BusinessError(MISSING_COLUMN)
    return columns


def _read(file) -> tuple[list[Line], int]:
    """Lignes qui portent un montant, et nombre de lignes sans montant (élèves qui n'avaient
    rien payé : le modèle les liste tous)."""
    _sheet, headers, rows = imports.read_file(file, set().union(*TITLES.values()))
    columns = _columns(headers)

    def cell(cells: list[str], name: str) -> str:
        index = columns[name]
        return cells[index].strip() if index is not None and index < len(cells) else ""

    lines, empty = [], 0
    for number, cells in rows:
        amount = cell(cells, "amount")
        if not amount:
            empty += 1
            continue
        lines.append(
            Line(
                number=number,
                matricule=cell(cells, "matricule"),
                amount=amount,
                currency=cell(cells, "currency"),
                fee=cell(cells, "fee"),
            )
        )
    return lines, empty


def _enrolled(year) -> dict[str, Enrollment]:
    """Inscriptions actives de l'année par matricule (sans casse)."""
    enrollments = Enrollment.objects.filter(
        academic_year=year, status=Enrollment.Status.ACTIVE
    ).select_related("student", "class_group__level", "class_group__track")
    return {e.student.matricule.upper(): e for e in enrollments if e.student.matricule}


def _check(lines: list[Line], school: School, year, *, lock: bool = False) -> None:
    """Remplit chaque ligne : élève, montant, devise, frais, répartition ou erreurs. `lock` (à
    l'enregistrement) : inscriptions puis école verrouillées avant de lire les restes dus, dans
    l'ordre de `services.approve_cancellation`."""
    enabled = school.enabled_currencies
    by_matricule = _enrolled(year)
    fee_types = {imports._key(fee.name): fee for fee in FeeType.objects.all()}
    for line in lines:
        line.enrollment = by_matricule.get(line.matricule.upper())
        if line.enrollment is None:
            line.refuse("unknown_student" if line.matricule else "missing_matricule")
        currency = CURRENCIES.get(line.currency.lower()) if line.currency else None
        if not line.currency and len(enabled) == 1:
            currency = enabled[0]
        if currency is None or currency not in enabled:
            line.refuse("unknown_currency" if line.currency else "missing_currency")
            continue
        line.currency = str(currency)
        line.amount_minor = _amount(line.amount, currency)
        if line.amount_minor is None:
            line.refuse("invalid_amount")
        if line.fee and imports._key(line.fee) not in fee_types:
            line.refuse("unknown_fee")

    ids = sorted({line.enrollment.pk for line in lines if line.enrollment})
    if lock:
        list(Enrollment.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        School.objects.select_for_update().get(pk=school.pk)
    already = set(
        Payment.objects.filter(
            origin=Payment.Origin.PRIOR, cancellation__isnull=True, enrollment_id__in=ids
        ).values_list("enrollment_id", "received_currency")
    )
    charges = services.charges_by_enrollment(ids)
    for line in lines:
        if line.issues:
            continue
        if (line.enrollment.pk, line.currency) in already:
            line.refuse("already_recorded")
            continue
        owed = charges.get(line.enrollment.pk, [])
        if line.fee:
            fee_type = fee_types[imports._key(line.fee)]
            owed = [charge for charge in owed if charge.fee_type_id == fee_type.pk]
        received = Money(line.amount_minor, line.currency)
        allocation = services.allocate(owed, received, None)
        if sum(part for _charge, part, _amount in allocation) != line.amount_minor:
            due = sum(c.remaining_minor for c in owed if c.state and c.currency == line.currency)
            line.refuse("more_than_due", due_minor=due, currency=line.currency)
            continue
        # Deux lignes pour le même élève (deux frais) : la seconde voit ce que la première a pris.
        for charge, _part, amount in allocation:
            charge.remaining_minor -= amount
        line.allocation = allocation


def _year():
    year = organisation.current_year()
    if year is None:
        raise BusinessError(NO_CURRENT_YEAR)
    return year


def check(file) -> Preview:
    """Aperçu d'un fichier : rien n'est écrit."""
    school, year = require_current_school(), _year()
    lines, empty = _read(file)
    _check(lines, school, year)
    return Preview(lines, empty)


def _numbers(school: School, year, count: int) -> list[str]:
    """`ITIG-RP-26-000001`… : école, série des reprises, année scolaire, séquence. Appelé sous le
    verrou de l'école."""
    prefix = f"{school.code.upper()}-{services.PRIOR_SERIES}-{year.starts_on:%y}-"
    last = (
        Payment.objects.filter(receipt_number__startswith=prefix)
        .order_by("-receipt_number")
        .values_list("receipt_number", flat=True)
        .first()
    )
    first = int(last.removeprefix(prefix)) + 1 if last else 1
    return [f"{prefix}{sequence:06d}" for sequence in range(first, first + count)]


def record(file, *, actor: User, expected: list[dict]) -> Preview:
    """Enregistre les lignes prêtes du fichier, en une transaction ; les lignes en erreur sont
    laissées. `expected` : les totaux de l'aperçu que l'utilisateur a validés (devise, montant,
    nombre) ; 409 `preview_outdated` s'ils ne sont plus ceux du fichier."""
    school, year = require_current_school(), _year()
    lines, empty = _read(file)
    with transaction.atomic():
        _check(lines, school, year, lock=True)
        preview = Preview(lines, empty)
        ready = preview.ready
        if not ready:
            raise BusinessError(NOTHING_TO_RECORD)
        if preview.totals != sorted(expected, key=lambda t: Currency.values.index(t["currency"])):
            raise BusinessError(PREVIEW_OUTDATED)
        rate = services.payment_rate()[0]
        rate_used = rate.rate if rate is not None else None
        now = timezone.now()
        payments, allocations, entries = [], [], []
        for line, number in zip(ready, _numbers(school, year, len(ready)), strict=True):
            payment = Payment(
                enrollment=line.enrollment,
                origin=Payment.Origin.PRIOR,
                cashier=actor,
                received_amount_minor=line.amount_minor,
                received_currency=line.currency,
                rate_used=rate_used,
                paid_at=now,
                receipt_number=number,
                created_by=actor,
            )
            payments.append(payment)
            allocations += [
                PaymentAllocation(
                    payment=payment,
                    student_charge=charge,
                    received_minor=part,
                    amount_minor=amount,
                    created_by=actor,
                )
                for charge, part, amount in line.allocation
            ]
            entries.append(
                (
                    payment,
                    {
                        "reference": number,
                        "student": str(line.enrollment.student),
                        "amount_minor": line.amount_minor,
                        "currency": line.currency,
                        "file": file.name[:120],
                        "allocations": [
                            {
                                "fee": f"{charge.fee_type.name} — {charge.label}",
                                "amount_minor": amount,
                                "currency": charge.currency,
                            }
                            for charge, _part, amount in line.allocation
                        ],
                    },
                )
            )
        Payment.objects.bulk_create(payments, batch_size=500)
        PaymentAllocation.objects.bulk_create(allocations, batch_size=1000)
        audit.record_many(
            Action.FINANCE_PRIOR_PAYMENT_RECORDED,
            entries,
            actor=actor,
            label=lambda payment: f"{payment.receipt_number} · {payment.enrollment.student}",
        )
        sync_changes.touch_enrollments({payment.enrollment_id for payment in payments})
    return preview


def template_workbook() -> bytes:
    """Modèle à remplir, déjà garni : une ligne par élève inscrit cette année et par devise qu'il
    doit encore, avec son reste à payer ; l'école n'écrit que le montant déjà payé. Quelques
    requêtes pour toute l'école."""
    year = _year()
    enrollments = sorted(
        _enrolled(year).values(),
        key=lambda e: (e.class_group.name, e.student.last_name, e.student.first_name),
    )
    charges = services.charges_by_enrollment([e.pk for e in enrollments], light=True)
    rows = []
    for enrollment in enrollments:
        due = defaultdict(int)
        for charge in charges.get(enrollment.pk, []):
            if charge.state:
                due[charge.currency] += charge.remaining_minor
        student = enrollment.student
        for currency in [c for c in Currency.values if due.get(c)] or [""]:
            remaining = Money(due[currency], currency).to_major() if currency else None
            rows.append(
                [
                    student.matricule,
                    str(student),
                    enrollment.class_group.name,
                    remaining,
                    None,
                    currency,
                    None,
                ]
            )
    headers = [
        gettext("STUDENT NUMBER"),
        gettext("NAME"),
        gettext("CLASS"),
        gettext("LEFT TO PAY"),
        gettext("AMOUNT PAID"),
        gettext("CURRENCY"),
        gettext("FEE (optional)"),
    ]
    return workbook(headers, rows, title=year.name, widths=[18, 34, 16, 16, 16, 10, 24])
