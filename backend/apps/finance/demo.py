"""Frais de démonstration (I5 en attendant la grille de l'ITIG) : grille fictive réaliste, à
partir de celle des maquettes — minerval en tranches USD, fonctionnement et frais connexes en une
fois, atelier par option, motivation des enseignants mensuelle en FC, Exetat en 4e —, le taux
de l'année, ce que doit chaque élève inscrit et quelques réductions. Écrits directement dans les
modèles : `make demo` n'écrit rien dans le journal."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.core.tenancy import use_school
from apps.finance.models import Discount, ExchangeRate, FeeRule, FeeType
from apps.finance.services import Installment, _write_installments, sync_charges
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
