"""Reprise des résultats (8.4.7) : une école qui arrive avec Mwangaza n'a pas les notes de l'an
dernier. Pour chaque élève sans aucune note cette année-là, un fichier Excel donne la décision
finale et le pourcentage ; chaque ligne devient la décision de l'élève dans la délibération de sa
classe, encore en cours, avec son pourcentage repris (`DeliberationDecision.prior_percent`). La
date est posée aux classes qui n'en ont pas ; chaque classe se proclame ensuite comme les autres.

Comme la reprise des paiements (4.19) : ni table ni tâche de fond. `check` lit le fichier et rend
l'aperçu ; à la validation, le même fichier est renvoyé et `record` le vérifie de nouveau sous
verrou. Une décision déjà enregistrée telle quelle n'est ni réécrite ni journalisée : un fichier
envoyé deux fois ne change rien.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.academics import deliberation
from apps.academics.models import Deliberation, DeliberationDecision, Grade
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import workbook
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import AcademicYear
from apps.students import imports
from apps.students.models import Enrollment

Decision = DeliberationDecision.Decision
# Aperçu : les erreurs d'abord (toutes celles qu'un écran peut montrer), quelques lignes prêtes.
MAX_ERRORS = 300
MAX_READY = 20

TITLES = {
    "matricule": {"matricule", "numeromatricule", "nmatricule", "studentnumber", "number"},
    "decision": {"decision", "decisionfinale", "resultat", "result", "finaldecision"},
    "percent": {"pourcentage", "pourcent", "percentage", "percent", "pct"},
}
# Ce que les écoles écrivent (sans accents ni espaces), en français et en anglais.
WORDS = {
    Decision.PASS: {"admis", "admise", "passe", "reussi", "reussie", "admitted", "passed", "pass"},
    Decision.REPEAT: {
        "double",
        "doublant",
        "doublante",
        "doublelannee",
        "redouble",
        "redoublant",
        "redoublante",
        "echec",
        "echoue",
        "repeat",
        "repeats",
        "repeatstheyear",
        "failed",
    },
    Decision.RESIT: {"repechage", "examenderepechage", "ajourne", "resit", "resitexam"},
    Decision.ORIENT: {"reoriente", "reorientee", "oriente", "orientee", "reoriented", "oriented"},
    Decision.EXCLUDE: {"exclu", "exclue", "renvoye", "renvoyee", "excluded"},
    Decision.DROPPED: {"abandon", "abandonne", "abandonnee", "dropped", "droppedout", "dropout"},
}
DECISIONS = {word: decision for decision, words in WORDS.items() for word in words}
PERCENT = re.compile(r"\d{1,3}(\.\d)?")

MISSING_COLUMN = ApiError(
    "missing_column",
    _("The file needs a student number column and a decision column: use the template."),
    400,
)
NOTHING_TO_RECORD = ApiError("nothing_to_record", _("No row can be recorded."), 409)
PREVIEW_OUTDATED = ApiError(
    "preview_outdated",
    _("The file or the classes changed since the preview: check it again."),
    409,
)


@dataclass
class Line:
    """Une ligne du fichier qui porte une décision ou un pourcentage : prête, ou en erreur
    (`issues`, codes traduits par l'écran)."""

    number: int
    matricule: str
    decision_text: str
    percent_text: str
    enrollment: Enrollment | None = None
    decision: str = ""
    percent: Decimal | None = None
    issues: list[dict] = field(default_factory=list)

    def refuse(self, code: str) -> None:
        self.issues.append({"code": code})


@dataclass
class Preview:
    lines: list[Line]
    empty: int
    changed: int = 0

    @property
    def ready(self) -> list[Line]:
        return [line for line in self.lines if not line.issues]

    @property
    def errors(self) -> list[Line]:
        return [line for line in self.lines if line.issues]

    @property
    def class_count(self) -> int:
        return len({line.enrollment.class_group_id for line in self.ready})


def _percent(text: str) -> Decimal | None:
    """« 62,5 % » → 62.5 ; `None` si illisible, au-delà de 100 ou plus précis qu'au dixième."""
    cleaned = "".join(text.split()).removesuffix("%").replace(",", ".")
    if not PERCENT.fullmatch(cleaned):
        return None
    percent = Decimal(cleaned)
    return percent if percent <= 100 else None


def _read(file) -> tuple[list[Line], int]:
    """Lignes qui portent une décision ou un pourcentage, et nombre de lignes vides (le modèle
    liste tous les élèves sans note)."""
    _sheet, headers, rows = imports.read_file(file, set().union(*TITLES.values()))
    keys = [imports._key(header) for header in headers]
    columns = {
        name: next((i for i, key in enumerate(keys) if key in titles), None)
        for name, titles in TITLES.items()
    }
    if columns["matricule"] is None or columns["decision"] is None:
        raise BusinessError(MISSING_COLUMN)

    def cell(cells: list[str], name: str) -> str:
        index = columns[name]
        return cells[index].strip() if index is not None and index < len(cells) else ""

    lines, empty = [], 0
    for number, cells in rows:
        decision, percent = cell(cells, "decision"), cell(cells, "percent")
        if not decision and not percent:
            empty += 1
            continue
        lines.append(Line(number, cell(cells, "matricule"), decision, percent))
    return lines, empty


def _enrolled(year: AcademicYear):
    return Enrollment.objects.filter(
        academic_year=year, status=Enrollment.Status.ACTIVE
    ).select_related("student", "class_group__level", "class_group__track")


def _noted(ids) -> set:
    """Inscriptions qui ont au moins une note : leur pourcentage se calcule."""
    return set(
        Grade.objects.filter(enrollment_id__in=ids)
        .values_list("enrollment_id", flat=True)
        .distinct()
    )


def _check(lines: list[Line], year: AcademicYear, *, lock: bool = False) -> dict:
    """Remplit chaque ligne : élève, décision, pourcentage ou erreurs. Rend les délibérations
    des classes du fichier, verrouillées à l'enregistrement (`lock`)."""
    by_matricule = {e.student.matricule.upper(): e for e in _enrolled(year) if e.student.matricule}
    seen = set()
    for line in lines:
        line.enrollment = by_matricule.get(line.matricule.upper())
        if line.enrollment is None:
            line.refuse("unknown_student" if line.matricule else "missing_matricule")
        elif line.enrollment.pk in seen:
            line.refuse("duplicate")
        else:
            seen.add(line.enrollment.pk)
        line.decision = DECISIONS.get(imports._key(line.decision_text), "")
        if not line.decision:
            line.refuse("unknown_decision" if line.decision_text else "missing_decision")
        if line.percent_text:
            line.percent = _percent(line.percent_text)
            if line.percent is None:
                line.refuse("invalid_percent")

    groups = {line.enrollment.class_group_id for line in lines if line.enrollment}
    deliberations = Deliberation.objects.filter(class_group_id__in=groups).order_by("pk")
    if lock:
        deliberations = deliberations.select_for_update()
    by_group = {d.class_group_id: d for d in deliberations}
    noted = _noted(seen)
    for line in lines:
        if line.enrollment is None:
            continue
        if line.enrollment.pk in noted:
            line.refuse("has_grades")
        found = by_group.get(line.enrollment.class_group_id)
        if found and found.status == Deliberation.Status.PROCLAIMED:
            line.refuse("class_proclaimed")
    return by_group


def check(file, year: AcademicYear) -> Preview:
    """Aperçu d'un fichier : rien n'est écrit."""
    lines, empty = _read(file)
    _check(lines, year)
    return Preview(lines, empty)


def record(file, *, actor: User, year: AcademicYear, held_on: date, expected: int) -> Preview:
    """Écrit les lignes prêtes dans la délibération de leur classe, en une transaction ; les
    lignes en erreur sont laissées. `expected` : nombre de lignes prêtes de l'aperçu validé ;
    409 `preview_outdated` s'il a changé. `held_on` : date posée aux classes qui n'en ont pas."""
    lines, empty = _read(file)
    with transaction.atomic():
        by_group = _check(lines, year, lock=True)
        preview = Preview(lines, empty)
        ready = preview.ready
        if not ready:
            raise BusinessError(NOTHING_TO_RECORD)
        if len(ready) != expected:
            raise BusinessError(PREVIEW_OUTDATED)
        names = {line.enrollment.class_group_id: line.enrollment.class_group.name for line in ready}
        for group_id in sorted(names):
            if group_id not in by_group:
                by_group[group_id], _created = Deliberation.objects.get_or_create(
                    class_group_id=group_id
                )
        now = timezone.now()
        dated = [by_group[g] for g in sorted(names) if by_group[g].held_on is None]
        for found in dated:
            found.held_on, found.updated_at = held_on, now
        Deliberation.objects.bulk_update(dated, ["held_on", "updated_at"])

        existing = {
            (d.deliberation_id, d.enrollment_id): d
            for d in DeliberationDecision.objects.filter(
                enrollment_id__in=[line.enrollment.pk for line in ready]
            )
        }
        created, updated, entries = [], [], []
        source = file.name[:120]
        for line in ready:
            enrollment = line.enrollment
            target = by_group[enrollment.class_group_id]
            found = existing.get((target.pk, enrollment.pk))
            after = {
                "decision": line.decision,
                "prior_percent": str(line.percent) if line.percent is not None else None,
                "file": source,
            }
            if found is None:
                found = DeliberationDecision(
                    deliberation=target,
                    enrollment=enrollment,
                    decision=line.decision,
                    prior_percent=line.percent,
                    created_by=actor,
                )
                created.append(found)
            elif (found.decision, found.prior_percent) == (line.decision, line.percent):
                continue
            else:
                after["previous"] = deliberation._logged(found)
                # Élève déjà chargé avec la ligne : le journal ne relit rien.
                found.enrollment = enrollment
                found.decision, found.prior_percent, found.updated_at = (
                    line.decision,
                    line.percent,
                    now,
                )
                updated.append(found)
            entries.append((found, after))
        DeliberationDecision.objects.bulk_create(created, batch_size=500)
        DeliberationDecision.objects.bulk_update(
            updated, ["decision", "prior_percent", "updated_at"], batch_size=500
        )
        audit.record_many(
            Action.DELIBERATION_DECIDED,
            [*entries, *((d, {"held_on": str(held_on), "file": source}) for d in dated)],
            actor=actor,
            label=lambda obj: (
                f"{obj.enrollment.student.full_name} · {names[obj.enrollment.class_group_id]}"
                if isinstance(obj, DeliberationDecision)
                else names[obj.class_group_id]
            ),
        )
        preview.changed = len(entries)
    return preview


def template_workbook(year: AcademicYear) -> bytes:
    """Modèle à remplir, déjà garni : chaque élève de l'année sans aucune note, dans une classe
    pas encore proclamée, avec la décision et le pourcentage déjà repris. Quatre requêtes."""
    enrollments = sorted(
        _enrolled(year),
        key=lambda e: (e.class_group.name, e.student.last_name, e.student.first_name),
    )
    noted = _noted([e.pk for e in enrollments])
    proclaimed = set(
        Deliberation.objects.filter(
            class_group__academic_year=year, status=Deliberation.Status.PROCLAIMED
        ).values_list("class_group_id", flat=True)
    )
    decided = {
        (d.deliberation.class_group_id, d.enrollment_id): d
        for d in DeliberationDecision.objects.filter(
            deliberation__class_group__academic_year=year
        ).select_related("deliberation")
    }
    labels = dict(Decision.choices)
    rows = []
    for enrollment in enrollments:
        if enrollment.pk in noted or enrollment.class_group_id in proclaimed:
            continue
        found = decided.get((enrollment.class_group_id, enrollment.pk))
        rows.append(
            [
                enrollment.student.matricule,
                str(enrollment.student),
                enrollment.class_group.name,
                str(labels[found.decision]) if found else None,
                found.prior_percent if found else None,
            ]
        )
    headers = [
        gettext("STUDENT NUMBER"),
        gettext("NAME"),
        gettext("CLASS"),
        gettext("DECISION"),
        gettext("PERCENTAGE"),
    ]
    return workbook(headers, rows, title=year.name, widths=[18, 34, 16, 18, 14])
