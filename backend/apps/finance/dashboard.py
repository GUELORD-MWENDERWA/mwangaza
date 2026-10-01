"""Tableau de bord du directeur (G3) : encaissé aujourd'hui, ce mois et jour par jour, impayés
échus, taux de recouvrement, effectifs par classe et par sexe, derniers paiements, et alertes
selon les seuils de l'école (`schools/alerts.py`, M5). Montants par devise, jamais additionnés
entre devises ; paiements annulés exclus."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.core.money import Currency
from apps.core.tenancy import require_current_school
from apps.finance import services
from apps.finance.models import CancellationRequest, CashClosing, CashSession, Payment
from apps.schools.models import AcademicYear, ClassGroup
from apps.schools.organisation import current_year
from apps.students.models import Enrollment, Student

# Barres des encaissements jour par jour.
DAYS = 21
# Écarts de caisse et annulations signalés s'ils datent de ces derniers jours.
ALERT_DAYS = 7
RECENT_PAYMENTS = 5


def _start(day: date) -> datetime:
    """Minuit du jour dans le fuseau de l'école (activé par le middleware)."""
    return timezone.make_aware(datetime.combine(day, time()))


def _currencies(present) -> list[str]:
    """Devises de l'école et celles qui ont un montant, dollars d'abord."""
    enabled = require_current_school().enabled_currencies
    return [c for c in Currency.values if c in enabled or c in present]


def _payments():
    return Payment.objects.filter(cancellation__isnull=True)


def collected(start: datetime, end: datetime) -> list[dict]:
    """Encaissé entre deux instants, par devise reçue (même nul), et nombre de paiements."""
    rows = {
        row["received_currency"]: row
        for row in _payments()
        .filter(paid_at__gte=start, paid_at__lt=end)
        .values("received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"), count=Count("id"))
        .order_by()
    }
    return [
        {
            "currency": currency,
            "amount_minor": rows.get(currency, {}).get("amount_minor", 0),
            "count": rows.get(currency, {}).get("count", 0),
        }
        for currency in _currencies(rows)
    ]


def daily(day: date) -> list[dict]:
    """Encaissé chaque jour des `DAYS` derniers jours (aujourd'hui compris), par devise."""
    first = day - timedelta(days=DAYS - 1)
    amounts: dict[date, dict[str, int]] = defaultdict(dict)
    for row in (
        _payments()
        .filter(paid_at__gte=_start(first), paid_at__lt=_start(day + timedelta(days=1)))
        .annotate(day=TruncDate("paid_at"))
        .values("day", "received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"))
        .order_by()
    ):
        amounts[row["day"]][row["received_currency"]] = row["amount_minor"]
    currencies = _currencies({c for values in amounts.values() for c in values})
    return [
        {
            "date": current,
            "amounts": [
                {"currency": c, "amount_minor": amounts[current].get(c, 0)} for c in currencies
            ],
        }
        for current in (first + timedelta(days=n) for n in range(DAYS))
    ]


def _months(day: date) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    """Ce mois jusqu'à aujourd'hui, et la même période du mois d'avant (jusqu'au même jour,
    ou à son dernier jour)."""
    start = day.replace(day=1)
    previous_last = start - timedelta(days=1)
    previous_start = previous_last.replace(day=1)
    previous_until = min(previous_start + timedelta(days=day.day - 1), previous_last)
    tomorrow = _start(day + timedelta(days=1))
    return (
        (_start(start), tomorrow),
        (_start(previous_start), _start(previous_until + timedelta(days=1))),
    )


def _factors(year: AcademicYear) -> dict[str, Decimal]:
    """Poids de chaque devise dans un taux de recouvrement : la devise principale de l'école
    compte telle quelle, l'autre au taux de l'année (seulement pour un pourcentage, jamais pour
    un montant affiché) ; sans taux, seule la devise principale compte."""
    main = require_current_school().default_currency
    factors = {main: Decimal(1)}
    rate = services.current_rate(year)
    if rate is not None:
        # Plus petites unités : centimes (USD), francs (CDF) ; taux : francs pour 1 dollar.
        if main == Currency.USD:
            factors[Currency.CDF.value] = Decimal(100) / rate.rate
        else:
            factors[Currency.USD.value] = rate.rate / Decimal(100)
    return factors


def percent(paid: dict[str, int], due: dict[str, int], factors: dict[str, Decimal]) -> int | None:
    """Payé sur dû, en pour cent arrondi vers le bas (100 % seulement si tout est payé) ; rien
    à payer : `None`."""
    total = sum(Decimal(amount) * factors[c] for c, amount in due.items() if c in factors)
    if not total:
        return None
    received = sum(Decimal(paid.get(c, 0)) * factors[c] for c in due if c in factors)
    return int(received * 100 / total)


def schooling(year: AcademicYear, day: date) -> dict:
    """Effectifs, impayés échus et recouvrement de l'année, par classe et pour l'école : trois
    requêtes pour les frais dus (`charges_by_enrollment`), une pour les inscriptions, une pour
    les classes. Recouvrement : payé sur dû (après réductions) des frais dont l'échéance est
    passée, comme les impayés (G1)."""
    enrollments = Enrollment.objects.filter(academic_year=year, status=Enrollment.Status.ACTIVE)
    students = {row["pk"]: row for row in enrollments.values("pk", "class_group", "student__sex")}
    due: dict = defaultdict(lambda: defaultdict(int))
    paid: dict = defaultdict(lambda: defaultdict(int))
    overdue: dict[str, int] = defaultdict(int)
    late_students = set()
    for enrollment_id, charges in services.charges_by_enrollment(
        enrollments.values("pk"), light=True
    ).items():
        group = students[enrollment_id]["class_group"]
        for charge in charges:
            if charge.state is None or charge.due_on >= day:
                continue
            due[group][charge.currency] += charge.amount_minor - charge.discount_minor
            paid[group][charge.currency] += charge.paid_minor
            if charge.state == services.OVERDUE:
                overdue[charge.currency] += charge.remaining_minor
                late_students.add(enrollment_id)
    counts: dict = defaultdict(lambda: {Student.Sex.MALE: 0, Student.Sex.FEMALE: 0})
    for row in students.values():
        counts[row["class_group"]][row["student__sex"]] += 1
    factors = _factors(year)
    classes = [
        {
            "id": group.pk,
            "name": group.name,
            "track": group.track.name if group.track else "",
            "cycle": group.level.cycle,
            "enrolled": sum(counts[group.pk].values()),
            "male": counts[group.pk][Student.Sex.MALE],
            "female": counts[group.pk][Student.Sex.FEMALE],
            "recovery_percent": percent(paid[group.pk], due[group.pk], factors),
        }
        for group in ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
    ]
    school_due, school_paid = defaultdict(int), defaultdict(int)
    for group in due:
        for currency, amount in due[group].items():
            school_due[currency] += amount
            school_paid[currency] += paid[group][currency]
    return {
        "classes": classes,
        "enrolled": len(students),
        "male": sum(1 for row in students.values() if row["student__sex"] == Student.Sex.MALE),
        "female": sum(1 for row in students.values() if row["student__sex"] == Student.Sex.FEMALE),
        "overdue": [
            {"currency": c, "amount_minor": overdue.get(c, 0)} for c in _currencies(overdue)
        ],
        "overdue_students": len(late_students),
        "recovery_percent": percent(school_paid, school_due, factors),
    }


# Pas d'année en cours : rien à compter.
NO_YEAR = {
    "classes": [],
    "enrolled": 0,
    "male": 0,
    "female": 0,
    "overdue": [],
    "overdue_students": 0,
    "recovery_percent": None,
}


def recent_payments() -> list[Payment]:
    return list(
        _payments()
        .select_related(
            "enrollment__student",
            "enrollment__class_group__level",
            "enrollment__class_group__track",
            "cash_session__cash_register",
        )
        .order_by("-paid_at", "-id")[:RECENT_PAYMENTS]
    )


def school_alerts(day: date, now: datetime) -> dict:
    """Ce qui demande l'attention du directeur : annulations en attente de validation ; caisses
    pas clôturées (ouvertes avant aujourd'hui, ou aujourd'hui passé l'heure de clôture) ; et, sur
    les `ALERT_DAYS` derniers jours, clôtures dont l'écart dépasse le seuil de sa devise et
    caissiers qui ont demandé plus d'annulations dans une journée que le seuil."""
    thresholds = require_current_school().alerts
    since = _start(day - timedelta(days=ALERT_DAYS - 1))
    closing_time = time.fromisoformat(thresholds["closing_time"])
    late = timezone.localtime(now).time() >= closing_time
    unclosed_until = _start(day + timedelta(days=1)) if late else _start(day)
    differences = [
        line
        for line in CashClosing.objects.filter(closed_at__gte=since)
        .select_related("cash_session__cash_register", "cash_session__cashier")
        .order_by("-closed_at", "currency")
        if abs(line.difference_minor) > thresholds["difference_minor"].get(line.currency, 0)
    ]
    cancellations = list(
        CancellationRequest.objects.filter(requested_at__gte=since)
        .annotate(day=TruncDate("requested_at"))
        .values("requested_by", "day")
        .annotate(count=Count("id"))
        .filter(count__gt=thresholds["cancellations_per_day"])
        .order_by("-day", "-count")
    )
    people = User.objects.in_bulk({row["requested_by"] for row in cancellations})
    return {
        "pending_cancellations": CancellationRequest.objects.filter(
            status=CancellationRequest.Status.PENDING
        ).count(),
        "unclosed": list(
            CashSession.objects.filter(closed_at__isnull=True, opened_at__lt=unclosed_until)
            .select_related("cash_register", "cashier")
            .order_by("opened_at")
        ),
        "differences": differences,
        "cancellations": [
            {"cashier": people[row["requested_by"]], "date": row["day"], "count": row["count"]}
            for row in cancellations
        ],
    }


def overview() -> dict:
    """Tout le tableau de bord, pour l'école de l'adresse."""
    day, now = services.today(), timezone.now()
    year = current_year()
    month, previous_month = _months(day)
    return {
        "date": day,
        "academic_year": year,
        "today": collected(_start(day), _start(day + timedelta(days=1))),
        "month": collected(*month),
        "previous_month": collected(*previous_month),
        "daily": daily(day),
        **(schooling(year, day) if year else NO_YEAR),
        "recent_payments": recent_payments(),
        "alerts": school_alerts(day, now),
    }
