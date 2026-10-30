"""Frais de démonstration (I5 en attendant la grille de l'ITIG) : grille fictive réaliste, à
partir de celle des maquettes | minerval en tranches USD, fonctionnement et frais connexes en une
fois, atelier par option, motivation des enseignants mensuelle en FC, Exetat en 4e —, le taux
de l'année, ce que doit chaque élève inscrit, quelques réductions, les caisses, des paiements
depuis la rentrée et deux crédits d'élèves par école. Écrits directement dans les modèles :
`make demo` n'écrit rien dans le journal."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.core.money import Money
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import (
    CancellationRequest,
    CashClosing,
    CashRegister,
    CashSession,
    Discount,
    ExchangeRate,
    FeeRule,
    FeeType,
    Payment,
    PaymentAllocation,
    StudentCredit,
)
from apps.finance.services import (
    Installment,
    _excess,
    _write_installments,
    allocate,
    charges_by_enrollment,
    charges_of,
    close_cash_session,
    closing_summary,
    current_rate,
    sync_charges,
)
from apps.schools.demo import DemoSpace
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
        *[DemoRule(MINERVAL, level=level, total=30000) for level in ("7EB", "8EB")],
        *[DemoRule(MINERVAL, level=level, total=36000) for level in ("1HT", "2HT", "3HT")],
        DemoRule(MINERVAL, level="4HT", total=39000),
        DemoRule("Frais de fonctionnement", total=5000, kind=FeeRule.ScheduleKind.SINGLE),
        DemoRule("Frais connexes", total=2500, kind=FeeRule.ScheduleKind.SINGLE),
        *[DemoRule(ATELIER, track=code, total=6000) for code in ("ELEC", "ELO")],
        *[DemoRule(ATELIER, track=code, total=7500) for code in ("MG", "MA")],
        DemoRule(MOTIVATION, currency="CDF", total=150000, kind=FeeRule.ScheduleKind.MONTHLY),
        DemoRule(
            "Frais d'État (Exetat)", level="4HT", total=4000, kind=FeeRule.ScheduleKind.SINGLE
        ),
    ],
    "volcans": [
        DemoRule(MINERVAL, total=24000),
        DemoRule(MOTIVATION, currency="CDF", total=100000, kind=FeeRule.ScheduleKind.MONTHLY),
    ],
}

RATES = {"itig": Decimal("2850"), "volcans": Decimal("2830")}


def create_demo_fees(spaces: list[DemoSpace]) -> None:
    """Crée ou remet à jour les types de frais et les barèmes de démonstration de l'année en
    cours, et son taux s'il n'en a pas encore (un taux ne se modifie pas). Ce que l'utilisateur
    a ajouté en essayant l'application n'est pas effacé."""
    for space in spaces:
        code, school = space.profile, space.school
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


def create_demo_charges(spaces: list[DemoSpace]) -> None:
    """Frais dus des élèves inscrits cette année, d'après les barèmes de démonstration : ceux qui
    manquent sont ajoutés, ceux d'un barème remis à zéro reprennent son montant."""
    for space in spaces:
        school = space.school
        with use_school(school):
            year = AcademicYear.objects.get(is_current=True)
            sync_charges(Enrollment.objects.filter(academic_year=year), actor=None)


# Un élève sur `every` (dans l'ordre des matricules) : (motif, pourcentage, sur le minerval seul).
DEMO_DISCOUNTS = [
    (20, Discount.Reason.STAFF_CHILD, 50, True, "Enfant d'un enseignant de l'école"),
    (33, Discount.Reason.SIBLING, 10, False, "Troisième enfant de la famille inscrit"),
    (45, Discount.Reason.SCHOLARSHIP, 25, True, "Bourse de la paroisse, lettre du 12/10/2026"),
]


def create_demo_discounts(spaces: list[DemoSpace]) -> None:
    """Quelques réductions (E3), une seule fois par école : enfants du personnel, fratries,
    bourses."""
    for space in spaces:
        school = space.school
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


def create_demo_payments(spaces: list[DemoSpace]) -> None:
    """Caisses de démonstration, toutes fermées (une session laissée ouverte en essayant est
    close), puis, une seule fois par école, des paiements depuis deux semaines avant la rentrée
    jusqu'à hier : sur dix élèves (ordre des matricules), quatre ont payé ce qui est dû avant la
    1re tranche dans chaque devise, deux ont donné 60,00 $, un le dû du 30/09, trois rien encore.
    Répartis comme à la caisse (`allocate`), une session par caisse et par jour."""
    for space in spaces:
        code, school = space.profile, space.school
        with use_school(school):
            registers = []
            for register_code, name, phone in REGISTERS[code]:
                register, _created = CashRegister.objects.update_or_create(
                    code=register_code, defaults={"name": name, "is_active": True}
                )
                cashier = User.objects.get(phone=space.numbers.of(phone))
                registers.append((register, cashier))
            # Caisses laissées ouvertes : clôturées, l'argent compté juste.
            for session in CashSession.objects.filter(closed_at__isnull=True).select_related(
                "cashier"
            ):
                summary = closing_summary(session)
                expected = {c["currency"]: c["expected_minor"] for c in summary["currencies"]}
                close_cash_session(session, actor=session.cashier, counted=expected)
            if not Payment.objects.exists():
                _demo_payments(school, registers)
            _demo_closings(school)


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


def _demo_closings(school: School) -> None:
    """Sessions fermées sans clôture (paiements de la démo, bases d'avant 3.8.2) : clôturées le
    soir, l'argent compté juste, sauf la plus récente où il manque 5,00 $ (billet refusé),
    expliqué : l'écart se voit dans le mois en cours (Clôtures de caisse, 3.8.3)."""
    sessions = list(
        CashSession.objects.filter(closed_at__isnull=False, closings__isnull=True).order_by(
            "opened_at"
        )
    )
    expected = {
        (row["cash_session"], row["received_currency"]): row["amount_minor"]
        for row in Payment.objects.filter(cash_session__in=sessions, cancellation__isnull=True)
        .values("cash_session", "received_currency")
        .annotate(amount_minor=Sum("received_amount_minor"))
        .order_by()
    }
    first = not CashClosing.objects.exclude(difference_minor=0).exists()
    closings = []
    for index, session in enumerate(sessions):
        last = index == len(sessions) - 1
        short = first and last and expected.get((session.pk, "USD"), 0) >= 500
        for currency in school.enabled_currencies:
            want = expected.get((session.pk, currency), 0)
            missing = 500 if short and currency == "USD" else 0
            closings.append(
                CashClosing(
                    cash_session=session,
                    currency=currency,
                    expected_minor=want,
                    counted_minor=want - missing,
                    difference_minor=-missing,
                    note="Billet de 5 $ déchiré refusé, rendu au parent" if short else "",
                    closed_by_id=session.cashier_id,
                    closed_at=session.closed_at,
                )
            )
    CashClosing.objects.bulk_create(closings, batch_size=500)


def create_demo_credits(spaces: list[DemoSpace]) -> None:
    """Une seule fois par école, deux crédits à traiter (M14) : une bourse de 25 % accordée
    après le paiement de la 1re tranche (crédit du trop-payé), et le minerval de l'année
    encaissé deux fois hors ligne, à la première et à la dernière caisse (crédit du second)."""
    for space in spaces:
        school = space.school
        with use_school(school):
            if StudentCredit.objects.exists():
                continue
            current = Enrollment.objects.filter(
                academic_year__is_current=True,
                status=Enrollment.Status.ACTIVE,
                discounts__isnull=True,
            ).order_by("student__matricule")
            paid = current.filter(
                payments__received_currency="USD", payments__received_amount_minor__gt=6000
            ).first()
            unpaid = current.filter(payments__isnull=True).first()
            if paid is None or unpaid is None:
                continue
            _demo_scholarship(paid)
            _demo_paid_twice(school, unpaid)


def _demo_scholarship(enrollment: Enrollment) -> None:
    before = _excess(charges_of(enrollment.pk))
    discount = Discount.objects.create(
        enrollment=enrollment,
        fee_type=FeeType.objects.get(name=MINERVAL),
        kind=Discount.Kind.PERCENT,
        percent=25,
        reason_code=Discount.Reason.SCHOLARSHIP,
        reason="Bourse de la paroisse Saint-Esprit, lettre du 12/10/2026",
    )
    for currency, excess in _excess(charges_of(enrollment.pk)).items():
        if excess > before.get(currency, 0):
            StudentCredit.objects.create(
                enrollment=enrollment,
                origin=StudentCredit.Origin.DISCOUNT,
                amount_minor=excess - before.get(currency, 0),
                currency=currency,
                source_discount=discount,
            )


def _demo_paid_twice(school: School, enrollment: Enrollment) -> None:
    charges = charges_of(enrollment.pk)
    owed = Money(sum(c.remaining_minor for c in charges if c.state and c.currency == "USD"), "USD")
    rate = current_rate(enrollment.academic_year).rate
    registers = CashRegister.objects.order_by("code")
    for hours, register in enumerate([registers.first(), registers.last()], start=1):
        session = CashSession.objects.filter(cash_register=register).order_by("opened_at").last()
        sequence = Payment.objects.filter(cash_session__cash_register=register).count() + 1
        prefix = f"{school.code.upper()}-{register.code}-{enrollment.academic_year.starts_on:%y}"
        payment = Payment.objects.create(
            enrollment=enrollment,
            cash_session=session,
            cashier=session.cashier,
            received_amount_minor=owed.amount_minor,
            received_currency=owed.currency,
            rate_used=rate,
            paid_at=session.opened_at + timedelta(hours=hours),
            receipt_number=f"{prefix}-{sequence:06d}",
            synced_at=session.closed_at,
        )
        if hours == 1:
            PaymentAllocation.objects.bulk_create(
                PaymentAllocation(
                    payment=payment, student_charge=charge, received_minor=part, amount_minor=amount
                )
                for charge, part, amount in allocate(charges, owed, rate)
            )
    StudentCredit.objects.create(
        enrollment=enrollment,
        origin=StudentCredit.Origin.OFFLINE_SURPLUS,
        amount_minor=owed.amount_minor,
        currency=owed.currency,
        source_payment=payment,
    )


# Comptable qui décide des annulations de démonstration.
APPROVERS = {"itig": "+243000001004", "volcans": "+243000002004"}
CANCELLATION_REASONS = [
    ("Montant saisi en FC au lieu de USD", "approve"),
    ("Parent revenu : le même paiement encaissé deux fois", "reject"),
    ("Mauvais élève sélectionné (homonyme)", None),
]


def create_demo_cancellations(spaces: list[DemoSpace]) -> None:
    """Une seule fois par école, des demandes d'annulation (F7) sur les derniers paiements du
    caissier de la première caisse : une validée par le comptable (reçu d'annulation), une
    refusée, une en attente ; et une du comptable, s'il encaisse aussi, en attente (le directeur
    la valide)."""
    for space in spaces:
        code, school = space.profile, space.school
        with use_school(school):
            if CancellationRequest.objects.exists():
                continue
            approver = User.objects.get(phone=space.numbers.of(APPROVERS[code]))
            plain = Payment.objects.filter(
                credits__isnull=True, enrollment__discounts__isnull=True
            ).order_by("-paid_at")
            cashier = User.objects.get(phone=space.numbers.of(REGISTERS[code][0][2]))
            for payment, (reason, decision) in zip(
                plain.filter(cashier=cashier), CANCELLATION_REASONS, strict=False
            ):
                request, _created = services.request_cancellation(
                    payment, actor=cashier, reason=reason
                )
                if decision == "approve":
                    services.approve_cancellation(request, actor=approver, note="Argent rendu")
                elif decision == "reject":
                    note = "Un seul paiement trouvé dans la caisse"
                    services.reject_cancellation(request, actor=approver, note=note)
            if payment := plain.filter(cashier=approver).first():
                services.request_cancellation(
                    payment, actor=approver, reason="Mauvais élève (même nom, autre classe)"
                )
