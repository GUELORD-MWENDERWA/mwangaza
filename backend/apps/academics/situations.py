"""Situations de fin d'année (8.4.4, maquette `gestion/situations`) : situation d'une classe
(résultats, par cours, palmarès) et de toute l'école (lauréat, taux par classe, par niveau et
global, écarts de délibération), au critère choisi à chaque édition.

Une classe proclamée se lit dans sa dernière version figée (`DeliberationSnapshot`) ; sinon dans la
délibération en cours (décision prise, à défaut la proposition), marquée « provisoire ». La
situation de l'école ne compte que les classes proclamées : elle ne lit que les instantanés, sans
recalculer les notes. Rien n'est stocké.

Critères : `rules` (règles de la classe : la décision de la délibération, repêchage compris ;
taux = admis ÷ délibérés, inscrits moins abandons) ou `average` (moyenne seule : 50 % de l'année
et plus ; taux = réussites ÷ classés, élèves qui ont un pourcentage). Abandons et exclus comptent
aussi les inscriptions arrêtées en cours d'année (`Enrollment.status`), absentes de la
délibération.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import F

from apps.academics import deliberation, report_cards, resits
from apps.academics.models import DeliberationDecision, DeliberationSnapshot
from apps.academics.report_cards import YEAR_KEY
from apps.schools.models import AcademicYear, ClassGroup
from apps.students.models import Enrollment

RULES, AVERAGE = "rules", "average"
CRITERIA = (RULES, AVERAGE)
AVERAGE_PASS = Decimal(50)
STEP = Decimal("0.1")
Decision = DeliberationDecision.Decision
# Inscription arrêtée en cours d'année → décision qu'elle vaut dans les comptes.
LEFT = {Enrollment.Status.DROPPED: Decision.DROPPED, Enrollment.Status.EXCLUDED: Decision.EXCLUDE}


def rate(part: int, whole: int) -> Decimal | None:
    return (Decimal(part * 100) / whole).quantize(STEP, ROUND_HALF_UP) if whole else None


@dataclass
class Line:
    """Un élève de la délibération. `decision` : figée, ou en cours (prise, sinon proposée)."""

    enrollment: str
    name: str
    percent: Decimal | None
    decision: str
    proposed: str
    reason: str
    deviates: bool
    place: int | None = None

    @property
    def decision_label(self) -> str:
        return Decision(self.decision).label if self.decision else ""

    @property
    def proposed_label(self) -> str:
        return Decision(self.proposed).label if self.proposed else ""

    def passed(self, criterion: str) -> bool | None:
        """Réussite selon le critère ; `None` : sans résultat (ni pourcentage ni décision)."""
        if criterion == AVERAGE:
            return None if self.percent is None else self.percent >= AVERAGE_PASS
        return None if not self.decision else self.decision == Decision.PASS


@dataclass
class Counts:
    enrolled: int = 0
    dropped: int = 0
    deliberated: int = 0
    passed: int = 0
    resit: int = 0
    repeat: int = 0
    orient: int = 0
    excluded: int = 0
    failed: int = 0
    unranked: int = 0
    deviations: int = 0

    @property
    def rate(self) -> Decimal | None:
        return rate(self.passed, self.deliberated)

    def add(self, other: "Counts") -> None:
        for item in fields(self):
            setattr(self, item.name, getattr(self, item.name) + getattr(other, item.name))


def count(lines: list[Line], left: Counter, criterion: str) -> Counts:
    """Comptes d'une classe : `left`, inscriptions arrêtées en cours d'année par décision."""
    result = Counts(
        enrolled=len(lines) + sum(left.values()),
        dropped=left[Decision.DROPPED],
        excluded=left[Decision.EXCLUDE] if criterion == RULES else 0,
        unranked=left[Decision.EXCLUDE] if criterion == AVERAGE else 0,
    )
    tally = {
        Decision.PASS: "passed",
        Decision.RESIT: "resit",
        Decision.REPEAT: "repeat",
        Decision.ORIENT: "orient",
        Decision.EXCLUDE: "excluded",
    }
    for line in lines:
        result.deviations += line.deviates
        if line.decision == Decision.DROPPED:
            result.dropped += 1
        elif (passed := line.passed(criterion)) is None:
            result.unranked += 1
        elif criterion == AVERAGE:
            result.passed += passed
            result.failed += not passed
        else:
            name = tally[line.decision]
            setattr(result, name, getattr(result, name) + 1)
    if criterion == RULES:
        result.failed = result.repeat + result.orient + result.excluded
        result.deliberated = result.enrolled - result.dropped
    else:
        result.deliberated = result.passed + result.failed
    return result


def rank(lines: list[Line]) -> list[Line]:
    """Palmarès : du plus haut pourcentage au plus bas, ex æquo à la même place ; sans pourcentage
    ou en abandon, à la fin sans place."""
    placed = sorted(
        (x for x in lines if x.percent is not None and x.decision != Decision.DROPPED),
        key=lambda x: (-x.percent, x.name),
    )
    for index, line in enumerate(placed):
        same = index and placed[index - 1].percent == line.percent
        line.place = placed[index - 1].place if same else index + 1
    return placed + sorted((x for x in lines if x.place is None), key=lambda x: x.name)


def best(lines: list[Line]) -> list[Line]:
    """Meilleur(s) élève(s) : le plus haut pourcentage, ex æquo compris."""
    ranked = [x for x in lines if x.percent is not None and x.decision != Decision.DROPPED]
    top = max((x.percent for x in ranked), default=None)
    return [x for x in ranked if x.percent == top] if top is not None else []


def _frozen(rows: list[dict]) -> list[Line]:
    return [
        Line(
            row["enrollment"],
            row["student"],
            Decimal(row["percent"]) if row["percent"] is not None else None,
            row["decision"],
            row["proposed"],
            row["reason"],
            row["deviates"],
        )
        for row in rows
    ]


def _left(enrollments, kept: set[str]) -> Counter:
    """Inscriptions arrêtées en cours d'année (abandon, exclusion) absentes de la délibération."""
    return Counter(
        LEFT[status] for pk, status in enrollments if status in LEFT and str(pk) not in kept
    )


def _course_rows(group: ClassGroup, criterion: str) -> list[dict]:
    """Par cours : élèves notés sur l'année, réussis (au seuil de l'école, note de repêchage
    comprise ; ou à 50 %), échoués, taux et moyenne. D'après les notes de la classe."""
    report = report_cards.class_report(group)
    threshold = AVERAGE_PASS
    second = {}
    if criterion == RULES:
        threshold = resits.rules_of(group)["course_pass_percent"]
        second = resits.grades_of_class([s.enrollment.pk for s in report.students])
    result = []
    for course in report.courses:
        if not course.is_taught:
            continue
        percents = []
        passed = 0
        for student in report.students:
            cell = student.cells[course.pk][YEAR_KEY]
            if cell.score is None or not cell.maximum:
                continue
            percent = report_cards._percent(cell.score, cell.maximum)
            percents.append(percent)
            again = second.get((student.enrollment.pk, course.pk))
            passed += percent >= threshold or (again is not None and again.percent >= threshold)
        average = sum(percents, Decimal(0)) / len(percents) if percents else None
        result.append(
            {
                "name": course.name,
                "graded": len(percents),
                "passed": passed,
                "failed": len(percents) - passed,
                "rate": rate(passed, len(percents)),
                "average": average.quantize(STEP, ROUND_HALF_UP) if average is not None else None,
            }
        )
    return result


def class_situation(group: ClassGroup, criterion: str, *, courses: bool, ranking: bool) -> dict:
    """Situation d'une classe : comptes, par cours (si demandé), palmarès (si demandé)."""
    snapshot, _rows = deliberation.proclaimed_rows(group)
    if snapshot:
        lines = _frozen(snapshot.rows)
    else:
        lines = [
            Line(
                str(r.enrollment.pk),
                r.enrollment.student.full_name,
                r.percent,
                r.decision or r.proposed,
                r.proposed,
                r.reason,
                r.deviates,
            )
            for r in deliberation.overview(group).rows
        ]
    enrollments = {
        str(e.pk): e
        for e in Enrollment.objects.filter(class_group=group)
        .exclude(status=Enrollment.Status.TRANSFERRED)
        .select_related("student")
    }
    left = _left(((pk, e.status) for pk, e in enrollments.items()), {x.enrollment for x in lines})
    ranked = rank(lines) if ranking else []
    return {
        "criterion": criterion,
        "snapshot": snapshot,
        "provisional": snapshot is None,
        "counts": count(lines, left, criterion),
        "courses": _course_rows(group, criterion) if courses else [],
        "ranking": [
            {
                "line": line,
                "enrollment": enrollments.get(line.enrollment),
                "passed": line.passed(criterion),
            }
            for line in ranked
        ],
    }


def school_situation(year: AcademicYear, criterion: str) -> dict:
    """Situation de l'école pour l'année : les classes proclamées seulement (dernière version
    figée), par niveau, avec sous-totaux, total, lauréat(s) et écarts. Quatre lectures."""
    groups = list(ClassGroup.objects.filter(academic_year=year).select_related("level", "track"))
    latest = {
        s.group_id: s
        for s in DeliberationSnapshot.objects.filter(deliberation__class_group__in=groups)
        .annotate(group_id=F("deliberation__class_group_id"))
        .order_by("deliberation__class_group_id", "-version")
        .distinct("deliberation__class_group_id")
    }
    by_class = defaultdict(list)
    for group_id, pk, status in (
        Enrollment.objects.filter(class_group__in=groups)
        .exclude(status=Enrollment.Status.TRANSFERRED)
        .values_list("class_group_id", "pk", "status")
    ):
        by_class[group_id].append((pk, status))

    levels: list[dict] = []
    total = Counts()
    candidates: list[dict] = []
    deviations: list[dict] = []
    for group in groups:
        if not levels or levels[-1]["level"] != group.level:
            levels.append(
                {"level": group.level, "classes": [], "counts": Counts(), "proclaimed": 0}
            )
        snapshot = latest.get(group.pk)
        if snapshot is None:
            active = sum(1 for _pk, status in by_class[group.pk] if status not in LEFT)
            levels[-1]["classes"].append({"group": group, "proclaimed": False, "enrolled": active})
            continue
        lines = _frozen(snapshot.rows)
        counts = count(lines, _left(by_class[group.pk], {x.enrollment for x in lines}), criterion)
        top = best(lines)
        levels[-1]["classes"].append(
            {"group": group, "proclaimed": True, "counts": counts, "best": top}
        )
        levels[-1]["counts"].add(counts)
        levels[-1]["proclaimed"] += 1
        total.add(counts)
        candidates += [{"line": line, "group": group} for line in top]
        deviations += [{"line": line, "group": group} for line in lines if line.deviates]
    winner = max((item["line"].percent for item in candidates), default=None)
    return {
        "criterion": criterion,
        "levels": levels,
        "total": total,
        "laureates": [item for item in candidates if item["line"].percent == winner],
        "deviations": deviations,
        "pending": sum(not c["proclaimed"] for level in levels for c in level["classes"]),
    }
