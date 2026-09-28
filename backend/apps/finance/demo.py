"""Frais de démonstration (I5 en attendant la grille de l'ITIG) : grille fictive réaliste, à
partir de celle des maquettes — minerval en tranches USD, fonctionnement et frais connexes en une
fois, atelier par option, motivation des enseignants mensuelle en FC, Exetat en 4e —, le taux
de l'année, ce que doit chaque élève inscrit, quelques réductions, les caisses et des paiements
depuis la rentrée. Écrits directement dans les modèles : `make demo` n'écrit rien dans le
journal."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.accounts.models import User
from apps.core.money import Money
from apps.core.tenancy import use_school
from apps.finance.models import (
    CashRegister,
    CashSession,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    Payment,
    PaymentAllocation,
)
from apps.finance.services import (
    Installment,
    _write_installments,
    allocate,
    charges_by_enrollment,
    current_rate,
    sync_charges,
)
from apps.schools.models import AcademicYear, Level, School, Track
from apps.students.models import Enrollment

TRANCHES = (date(2026, 10, 15), date(2027, 1, 15), date(2027, 4, 15))
START = date(2026, 9, 30)
# Septembre à juin : dix mois, payés avant le 10.
MONTHS = [date(2026 + (month < 9), month, 10) for month in (9, 10, 11, 12, 1, 2, 3, 4, 5, 6)]
MONTH_NAMES = [
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
]


@dataclass(frozen=True)
class DemoFeeType:
    name: str
    category: str
    funds_teacher_bonus: bool = False
    accounting_code: str = ""


@dataclass(frozen=True)
class DemoRule:
    fee_type: str
    # "" : toute l'école ; sinon le nom d'un niveau ou le code d'une option.
    level: str = ""
    track: str = ""
    currency: str = "USD"
    total: int = 0
    kind: str = FeeRule.ScheduleKind.INSTALLMENTS


def _installments(rule: DemoRule) -> list[Installment]:
    if rule.kind == FeeRule.ScheduleKind.SINGLE:
        return [Installment(rule.fee_type, rule.total, START)]
    if rule.kind == FeeRule.ScheduleKind.MONTHLY:
        return [
            Installment(name, rule.total // len(MONTHS), due)
            for name, due in zip(MONTH_NAMES, MONTHS, strict=True)
        ]
    labels = ("1re tranche", "2e tranche", "3e tranche")
    return [
        Installment(label, rule.total // len(TRANCHES), due)
        for label, due in zip(labels, TRANCHES, strict=True)
    ]


MINERVAL = "Minerval"
MOTIVATION = "Motivation des enseignants"
ATELIER = "Frais d'atelier"

TYPES = {
    "itig": [
        DemoFeeType(MINERVAL, FeeType.Category.TUITION, accounting_code="706"),
        DemoFeeType("Frais de fonctionnement", FeeType.Category.OPERATING),
        DemoFeeType("Frais connexes", FeeType.Category.ANCILLARY),
        DemoFeeType(ATELIER, FeeType.Category.CUSTOM),
        DemoFeeType(MOTIVATION, FeeType.Category.CUSTOM, funds_teacher_bonus=True),
        DemoFeeType("Frais d'État (Exetat)", FeeType.Category.OFFICIAL_EXAM),
        DemoFeeType("Uniforme", FeeType.Category.UNIFORM),
    ],
    "volcans": [
        DemoFeeType(MINERVAL, FeeType.Category.TUITION),
        DemoFeeType(MOTIVATION, FeeType.Category.CUSTOM, funds_teacher_bonus=True),
    ],
}

RULES = {
    "itig": [
        *[DemoRule(MINERVAL, level=level, total=30000) for level in ("7e EB", "8e EB")],
        *[DemoRule(MINERVAL, level=level, total=36000) for level in ("1re", "2e", "3e")],
        DemoRule(MINERVAL, level="4e", total=39000),
        DemoRule("Frais de fonctionnement", total=5000, kind=FeeRule.ScheduleKind.SINGLE),
        DemoRule("Frais connexes", total=2500, kind=FeeRule.ScheduleKind.SINGLE),
        *[DemoRule(ATELIER, track=code, total=6000) for code in ("ELEC", "ELO")],
        *[DemoRule(ATELIER, track=code, total=7500) for code in ("MG", "MA")],
        DemoRule(MOTIVATION, currency="CDF", total=150000, kind=FeeRule.ScheduleKind.MONTHLY),
        DemoRule("Frais d'État (Exetat)", level="4e", total=4000, kind=FeeRule.ScheduleKind.SINGLE),
    ],
    "volcans": [
        DemoRule(MINERVAL, total=24000),
        DemoRule(MOTIVATION, currency="CDF", total=100000, kind=FeeRule.ScheduleKind.MONTHLY),
    ],
}

RATES = {"itig": Decimal("2850"), "volcans": Decimal("2830")}


def create_demo_fees(schools: dict[str, School]) -> None:
    """Crée ou remet à jour les types de frais et les barèmes de démonstration de l'année en
    cours, et son taux s'il n'en a pas encore (un taux ne se modifie pas). Ce que l'utilisateur
    a ajouté en essayant l'application n'est pas effacé."""
    for code, school in schools.items():
        with use_school(school):
            year = AcademicYear.objects.get(is_current=True)
            types = {}
            for demo in TYPES[code]:
                types[demo.name], _created = FeeType.objects.update_or_create(
                    name=demo.name,
                    defaults={
                        "category": demo.category,
                        "funds_teacher_bonus": demo.funds_teacher_bonus,
                        "accounting_code": demo.accounting_code,
                        "is_active": True,
                    },
                )
            levels = {level.name: level for level in Level.objects.all()}
            tracks = {track.code: track for track in Track.objects.all()}
            for demo in RULES[code]:
                rule, _created = FeeRule.objects.update_or_create(
                    academic_year=year,
                    fee_type=types[demo.fee_type],
                    level=levels.get(demo.level),
                    track=tracks.get(demo.track),
                    class_group=None,
                    defaults={
                        "currency": demo.currency,
                        "total_amount_minor": demo.total,
                        "schedule_kind": demo.kind,
                    },
                )
                _write_installments(rule, _installments(demo), actor=None)
            if not ExchangeRate.objects.filter(academic_year=year).exists():
                ExchangeRate.objects.create(academic_year=year, rate=RATES[code])


def create_demo_charges(schools: dict[str, School]) -> None:
    """Frais dus des élèves inscrits cette année, d'après les barèmes de démonstration : ceux qui
    manquent sont ajoutés, ceux d'un barème remis à zéro reprennent son montant."""
    for school in schools.values():
        with use_school(school):
            year = AcademicYear.objects.get(is_current=True)
            sync_charges(Enrollment.objects.filter(academic_year=year), actor=None)


# Un élève sur `every` (dans l'ordre des matricules) : (motif, pourcentage, sur le minerval seul).
DEMO_DISCOUNTS = [
    (20, Discount.Reason.STAFF_CHILD, 50, True, "Enfant d'un enseignant de l'école"),
    (33, Discount.Reason.SIBLING, 10, False, "Troisième enfant de la famille inscrit"),
    (45, Discount.Reason.SCHOLARSHIP, 25, True, "Bourse de la paroisse, lettre du 12/10/2026"),
]


def create_demo_discounts(schools: dict[str, School]) -> None:
    """Quelques réductions (E3), une seule fois par école : enfants du personnel, fratries,
    bourses."""
    for school in schools.values():
        with use_school(school):
            if Discount.objects.exists():
                continue
            minerval = FeeType.objects.filter(name=MINERVAL).first()
            enrollments = list(
                Enrollment.objects.filter(
                    academic_year__is_current=True, status=Enrollment.Status.ACTIVE
                ).order_by("student__matricule")
            )
            Discount.objects.bulk_create(
                Discount(
                    enrollment=enrollment,
                    fee_type=minerval if tuition_only else None,
                    kind=Discount.Kind.PERCENT,
                    percent=percent,
                    reason_code=code,
                    reason=reason,
                )
                for every, code, percent, tuition_only, reason in DEMO_DISCOUNTS
                for enrollment in enrollments[every // 2 :: every]
            )


# Caisses : code, nom, téléphone du compte qui la tient (comptes de `apps/accounts/demo.py`).
REGISTERS = {
    "itig": [("C1", "Caisse 1", "+243000001005"), ("C2", "Caisse 2", "+243000001004")],
    "volcans": [("C1", "Caisse principale", "+243000002005")],
}


def create_demo_payments(schools: dict[str, School]) -> None:
    """Caisses de démonstration, toutes fermées (une session laissée ouverte en essayant est
    close), puis, une seule fois par école, des paiements depuis deux semaines avant la rentrée
    jusqu'à hier : sur dix élèves (ordre des matricules), quatre ont payé ce qui est dû avant la
    1re tranche dans chaque devise, deux ont donné 60,00 $, un le dû du 30/09, trois rien encore.
    Répartis comme à la caisse (`allocate`), une session par caisse et par jour."""
    for code, school in schools.items():
        with use_school(school):
            registers = []
            for register_code, name, phone in REGISTERS[code]:
                register, _created = CashRegister.objects.update_or_create(
                    code=register_code, defaults={"name": name, "is_active": True}
                )
                registers.append((register, User.objects.get(phone=phone)))
            CashSession.objects.filter(closed_at__isnull=True).update(closed_at=timezone.now())
            if not Payment.objects.exists():
                _demo_payments(school, registers)


def _demo_amounts(charges: list, kind: int) -> list[Money]:
    def owed(currency: str, until: date) -> int:
        return sum(
            charge.remaining_minor
            for charge in charges
            if charge.state and charge.currency == currency and charge.due_on <= until
        )

    if kind < 4:
        amounts = [Money(owed("USD", TRANCHES[0]), "USD"), Money(owed("CDF", MONTHS[1]), "CDF")]
    elif kind < 6:
        amounts = [Money(min(6000, owed("USD", TRANCHES[0])), "USD")]
    else:
        amounts = [Money(owed("USD", START), "USD"), Money(owed("CDF", START), "CDF")]
    return [amount for amount in amounts if amount.amount_minor > 0]


def _demo_payments(school: School, registers: list[tuple[CashRegister, User]]) -> None:
    year = AcademicYear.objects.get(is_current=True)
    rate = current_rate(year).rate
    zone = ZoneInfo(school.timezone)
    enrollments = list(
        Enrollment.objects.filter(academic_year=year, status=Enrollment.Status.ACTIVE).order_by(
            "student__matricule"
        )
    )
    charges = charges_by_enrollment([enrollment.pk for enrollment in enrollments])
    first_day = year.starts_on - timedelta(days=14)
    days = max((timezone.localdate() - first_day).days, 1)
    sessions, payments, allocations, sequences = {}, [], [], {}
    for index, enrollment in enumerate(enrollments):
        if index % 10 >= 7:
            continue
        register, cashier = registers[index % len(registers)]
        day = first_day + timedelta(days=(index * 7) % days)
        if (register.pk, day) not in sessions:
            sessions[register.pk, day] = CashSession(
                cash_register=register,
                cashier=cashier,
                opened_at=datetime.combine(day, time(7, 30), zone),
                closed_at=datetime.combine(day, time(16, 30), zone),
            )
        for number, received in enumerate(_demo_amounts(charges[enrollment.pk], index % 10)):
            payment = Payment(
                enrollment=enrollment,
                cash_session=sessions[register.pk, day],
                cashier=cashier,
                received_amount_minor=received.amount_minor,
                received_currency=received.currency,
                rate_used=rate,
                paid_at=datetime.combine(day, time(8 + index % 8, (index * 13) % 60, number), zone),
            )
            payments.append(payment)
            allocations += [
                PaymentAllocation(
                    payment=payment, student_charge=charge, received_minor=part, amount_minor=amount
                )
                for charge, part, amount in allocate(charges[enrollment.pk], received, rate)
            ]
    for payment in sorted(payments, key=lambda payment: payment.paid_at):
        register = payment.cash_session.cash_register
        sequences[register.pk] = sequences.get(register.pk, 0) + 1
        prefix = f"{school.code.upper()}-{register.code}-{year.starts_on:%y}"
        payment.receipt_number = f"{prefix}-{sequences[register.pk]:06d}"
    CashSession.objects.bulk_create(sessions.values())
    Payment.objects.bulk_create(payments, batch_size=500)
    PaymentAllocation.objects.bulk_create(allocations, batch_size=1000)
