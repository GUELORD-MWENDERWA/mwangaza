"""Impayés (G1) : élèves de l'année dont au moins un frais dû est en retard (échéance passée et
reste > 0), avec les filtres de l'écran et des exports. Même calcul que le solde (2.7) :
réductions déduites, paiements annulés exclus, crédits utilisés comptés. Montants par devise,
jamais convertis ni additionnés entre devises."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from django.db.models import Count, Min, QuerySet

from apps.core.money import Currency
from apps.core.tenancy import require_current_school
from apps.finance import services
from apps.finance.models import FeeType, Payment, StudentCharge
from apps.schools.models import AcademicYear, ClassGroup
from apps.students.models import Enrollment, Guardian

AMOUNT, DAYS, NAME, CLASS = "amount", "days", "name", "class"
ORDERS = (AMOUNT, DAYS, NAME, CLASS)
# « Retard de plus de 30 jours » (chiffre clé de l'écran).
LONG_DELAY = 30


@dataclass(frozen=True)
class Filters:
    """`over_days` : seulement les frais en retard de plus de ce nombre de jours (0 : tous) ;
    `installment` : libellé de la tranche (« 1re tranche », « Octobre ») ; `currency` : seulement
    les frais dans cette devise."""

    academic_year: AcademicYear
    class_group: ClassGroup | None = None
    fee_type: FeeType | None = None
    installment: str = ""
    over_days: int = 0
    currency: str = ""
    order: str = AMOUNT


@dataclass
class Amount:
    currency: str
    overdue_minor: int


@dataclass(slots=True)
class LateCharge:
    """Un frais en retard : dû après réductions, payé, reste et jours de retard."""

    fee_type: FeeType
    label: str
    due_on: date
    currency: str
    due_minor: int
    paid_minor: int
    remaining_minor: int
    days_late: int


@dataclass
class UnpaidStudent:
    """`charges` : frais en retard retenus par les filtres, les plus anciens d'abord.
    `enrollment` (élève, classe), `guardian` et `last_payment` : remplis par `with_contacts`,
    seulement pour la page affichée ou l'export."""

    enrollment_id: UUID
    charges: list[LateCharge]
    amounts: list[Amount]
    days_late: int
    enrollment: Enrollment | None = None
    guardian: Guardian | None = None
    last_payment: Payment | None = None


@dataclass
class Summary:
    students: int
    enrolled: int
    amounts: list[Amount]
    long_overdue: int
    class_groups: list[ClassGroup] = field(default_factory=list)
    fee_types: list[FeeType] = field(default_factory=list)
    installments: list[str] = field(default_factory=list)


def _enrollments(filters: Filters) -> QuerySet[Enrollment]:
    """Inscriptions actives de l'année (et de la classe) : un élève parti n'est plus relancé."""
    enrollments = Enrollment.objects.filter(
        academic_year=filters.academic_year, status=Enrollment.Status.ACTIVE
    )
    if filters.class_group:
        enrollments = enrollments.filter(class_group=filters.class_group)
    return enrollments


def _counts(charge: StudentCharge, filters: Filters) -> bool:
    return (
        charge.state == services.OVERDUE
        and charge.days_late > filters.over_days
        and (not filters.fee_type or charge.fee_type_id == filters.fee_type.pk)
        and (not filters.installment or charge.label == filters.installment)
        and (not filters.currency or charge.currency == filters.currency)
    )


def _amounts(charges: list[LateCharge]) -> list[Amount]:
    """Par devise, dollars d'abord ; seulement les devises où il reste quelque chose."""
    totals = defaultdict(int)
    for charge in charges:
        totals[charge.currency] += charge.remaining_minor
    return [Amount(c, totals[c]) for c in Currency.values if totals.get(c)]


def totals(rows: list[UnpaidStudent]) -> list[Amount]:
    """Total en retard des élèves, par devise."""
    return _amounts([charge for row in rows for charge in row.charges])


def enrolled(filters: Filters) -> int:
    """Élèves inscrits (actifs) de l'année ou de la classe choisie."""
    return _enrollments(filters).count()


def surname(enrollment: Enrollment) -> tuple:
    student = enrollment.student
    return tuple(
        name.casefold() for name in (student.last_name, student.middle_name, student.first_name)
    )


def class_key(enrollment: Enrollment) -> tuple:
    group = enrollment.class_group
    return (group.level.order, group.level.name, group.track.name if group.track else "")


def _keys(rows: list[UnpaidStudent]) -> dict:
    """Clés de tri (nom, classe) des élèves en retard, sans charger leurs fiches : une requête."""
    keys = {}
    for pk, last, middle, first, order, level, track, section in Enrollment.objects.filter(
        pk__in=[row.enrollment_id for row in rows]
    ).values_list(
        "pk",
        "student__last_name",
        "student__middle_name",
        "student__first_name",
        "class_group__level__order",
        "class_group__level__name",
        "class_group__track__name",
        "class_group__section",
    ):
        name = tuple(part.casefold() for part in (last, middle, first))
        keys[pk] = (name, (order, level, track or ""), section)
    return keys


def _sort(rows: list[UnpaidStudent], filters: Filters) -> None:
    keys = _keys(rows)

    def name(row: UnpaidStudent) -> tuple:
        return keys[row.enrollment_id][0]

    if filters.order == NAME:
        rows.sort(key=name)
    elif filters.order == CLASS:
        rows.sort(key=lambda row: (*keys[row.enrollment_id][1:], name(row)))
    elif filters.order == DAYS:
        rows.sort(key=lambda row: (-row.days_late, name(row)))
    else:
        # Jamais deux devises additionnées : la devise choisie, sinon les dollars puis les francs.
        currencies = [filters.currency] if filters.currency else Currency.values

        def amounts(row: UnpaidStudent) -> tuple:
            owed = {amount.currency: amount.overdue_minor for amount in row.amounts}
            return tuple(-owed.get(currency, 0) for currency in currencies)

        rows.sort(key=lambda row: (amounts(row), name(row)))


def _late(filters: Filters) -> dict[UUID, list[LateCharge]]:
    """Frais en retard retenus par les filtres, par inscription, les plus anciens d'abord. Sans
    réduction : seuls ces frais remontent de la base, reste calculé par elle (une requête, plus
    une pour leurs types) ; avec une réduction en cours : `charges_by_enrollment` (trois)."""
    day = services.today()
    enrollments = _enrollments(filters)
    charges = services.settled_charges(enrollments).filter(
        due_on__lt=day - timedelta(days=filters.over_days), remaining_minor__gt=0
    )
    if filters.fee_type:
        charges = charges.filter(fee_type=filters.fee_type)
    if filters.installment:
        charges = charges.filter(label=filters.installment)
    if filters.currency:
        charges = charges.filter(currency=filters.currency)
    rows = list(
        charges.order_by("enrollment", "due_on", "fee_type__name", "label").values_list(
            "enrollment",
            "fee_type",
            "label",
            "due_on",
            "currency",
            "amount_minor",
            "settled_minor",
            "remaining_minor",
        )
    )
    fee_types = FeeType.objects.in_bulk({row[1] for row in rows})
    late = defaultdict(list)
    for enrollment_id, fee_type, label, due_on, currency, due, paid, remaining in rows:
        late[enrollment_id].append(
            LateCharge(
                fee_types[fee_type],
                label,
                due_on,
                currency,
                due,
                paid,
                remaining,
                (day - due_on).days,
            )
        )
    discounted = services.charges_by_enrollment(services.discounted(enrollments), light=True)
    for enrollment_id, items in discounted.items():
        for charge in items:
            charge.days_late = (day - charge.due_on).days
        kept = [
            LateCharge(
                charge.fee_type,
                charge.label,
                charge.due_on,
                charge.currency,
                charge.amount_minor - charge.discount_minor,
                charge.paid_minor,
                charge.remaining_minor,
                charge.days_late,
            )
            for charge in items
            if _counts(charge, filters)
        ]
        if kept:
            late[enrollment_id] = kept
    return late


def unpaid_students(filters: Filters) -> list[UnpaidStudent]:
    """Élèves en retard selon les filtres, triés, sans leurs fiches (`with_contacts`). Un
    nombre fixe de requêtes quelle que soit la taille de l'école, et aucun objet par frais dû
    sauf pour les élèves qui ont une réduction."""
    rows = [
        UnpaidStudent(
            enrollment_id=enrollment_id,
            charges=charges,
            amounts=_amounts(charges),
            days_late=max(charge.days_late for charge in charges),
        )
        for enrollment_id, charges in _late(filters).items()
    ]
    _sort(rows, filters)
    return rows


def with_contacts(rows: list[UnpaidStudent]) -> list[UnpaidStudent]:
    """Inscription (élève, classe), tuteur principal de la famille et dernier paiement non
    annulé, pour une page de la liste ou un export : trois requêtes."""
    enrollments = Enrollment.objects.select_related(
        "student", "class_group__level", "class_group__track"
    ).in_bulk([row.enrollment_id for row in rows])
    for row in rows:
        row.enrollment = enrollments[row.enrollment_id]
    families = {row.enrollment.student.family_id for row in rows}
    guardians = {
        guardian.family_id: guardian
        for guardian in Guardian.objects.filter(family_id__in=families, is_primary=True)
    }
    payments = {
        payment.enrollment_id: payment
        for payment in Payment.objects.filter(
            enrollment_id__in=[row.enrollment_id for row in rows], cancellation__isnull=True
        )
        .order_by("enrollment_id", "-paid_at")
        .distinct("enrollment_id")
    }
    for row in rows:
        row.guardian = guardians.get(row.enrollment.student.family_id)
        row.last_payment = payments.get(row.enrollment_id)
    return rows


def summary(filters: Filters) -> Summary:
    """Chiffres clés selon les filtres (un montant par devise de l'école, même nul), et ce que
    proposent les filtres pour l'année : classes, types de frais et tranches (libellés) des frais
    dus, dans l'ordre des échéances."""
    late = _late(filters)
    year = filters.academic_year
    charges = StudentCharge.objects.filter(
        enrollment__academic_year=year, status=StudentCharge.Status.ACTIVE
    )
    installments = charges.values("label").annotate(first=Min("due_on")).order_by("first", "label")
    owed = {
        amount.currency: amount.overdue_minor
        for amount in _amounts([charge for charges in late.values() for charge in charges])
    }
    currencies = require_current_school().enabled_currencies
    return Summary(
        students=len(late),
        enrolled=enrolled(filters),
        amounts=[
            Amount(currency, owed.get(currency, 0))
            for currency in Currency.values
            if currency in currencies or currency in owed
        ],
        long_overdue=sum(
            1 for charges in late.values() if max(c.days_late for c in charges) > LONG_DELAY
        ),
        class_groups=list(
            ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
        ),
        fee_types=list(FeeType.objects.filter(pk__in=charges.values("fee_type"))),
        installments=[item["label"] for item in installments],
    )


@dataclass
class ClassPage:
    """Une classe de l'export PDF (ou toute la liste) : élèves en retard, nombre d'inscrits,
    titulaire, total par devise."""

    class_group: ClassGroup | None
    rows: list[UnpaidStudent]
    enrolled: int
    teacher: str
    totals: list[Amount]


def by_class(rows: list[UnpaidStudent], filters: Filters) -> list[ClassPage]:
    """Les élèves en retard regroupés par classe, dans l'ordre des classes ; inscrits par
    classe en une requête."""
    groups = defaultdict(list)
    for row in rows:
        groups[row.enrollment.class_group_id].append(row)
    counts = dict(
        _enrollments(filters)
        .order_by()
        .values("class_group")
        .annotate(count=Count("pk"))
        .values_list("class_group", "count")
    )
    classes = ClassGroup.objects.filter(pk__in=groups).select_related(
        "level", "track", "homeroom_teacher"
    )
    return [
        ClassPage(
            class_group=group,
            rows=groups[group.pk],
            enrolled=counts.get(group.pk, 0),
            teacher=group.homeroom_teacher.get_full_name() if group.homeroom_teacher else "",
            totals=totals(groups[group.pk]),
        )
        for group in classes
    ]
