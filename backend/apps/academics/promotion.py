"""Passage de classe et confirmation de place (8.4.5).

Après la proclamation, l'école propose à chaque ancien sa place de l'année suivante, d'après la
décision de la dernière version figée de sa classe (`DeliberationSnapshot`) : admis → niveau
suivant, doublant → même niveau, réorienté → classe à choisir ; repêchage, exclusion, abandon et
fin d'études n'ont pas de place. Le parent répond au Portail (`portal/places.py`) ; l'école
inscrit ensuite, en lot. Rien n'est inscrit sans elle, et l'année finie n'est pas modifiée.

Année finie = la dernière qui a une année suivante, sans dépasser l'année en cours : l'écran sert
avant comme après le changement d'année en cours."""

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import pairwise

from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext_lazy as _

from apps.academics.models import DeliberationDecision, DeliberationSnapshot, PlaceConfirmation
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.notifications import events
from apps.schools.models import AcademicYear, ClassGroup, Level
from apps.students import services as students
from apps.students.models import Enrollment

Decision = DeliberationDecision.Decision
Status = PlaceConfirmation.Status

# Ce que la décision prévoit pour l'année suivante.
NEXT_LEVEL, SAME_LEVEL, CHOOSE = "next_level", "same_level", "choose"
FINISHED, WAITING, NO_PLACE, UNDECIDED = "finished", "waiting", "no_place", "undecided"
PROPOSALS = [NEXT_LEVEL, SAME_LEVEL, CHOOSE, FINISHED, WAITING, NO_PLACE, UNDECIDED]
# Décisions qui donnent droit à une place.
OFFERABLE = {Decision.PASS, Decision.REPEAT, Decision.ORIENT}

NO_NEXT_YEAR = ApiError("no_next_year", _("Create next school year first, with its classes."), 400)
NOT_FINISHED_YEAR = ApiError(
    "not_finished_year", _("This class is not in the school year that is ending."), 400
)
NOT_IN_CLASS = ApiError("not_in_class", _("This student is not in this class."), 400)
NOT_NEXT_YEAR = ApiError("not_next_year", _("This class is not in next school year."), 400)
NO_PLACE_FOR_DECISION = ApiError(
    "no_place_for_decision",
    _("This student has no place next year: resit pending, excluded, dropped out or no decision."),
    400,
)
ALREADY_ENROLLED = ApiError(
    "already_enrolled_next_year", _("This student is already enrolled next year."), 400
)


def years() -> tuple[AcademicYear | None, AcademicYear | None]:
    """(année finie, année suivante) ; sans année suivante : (année en cours, None)."""
    ordered = list(AcademicYear.objects.order_by("starts_on"))
    current = next((y for y in ordered if y.is_current), None)
    pairs = [
        (year, following)
        for year, following in pairwise(ordered)
        if current is None or year.starts_on <= current.starts_on
    ]
    return pairs[-1] if pairs else (current, None)


def _latest_rows(groups) -> dict:
    """Lignes figées de la dernière proclamation de chaque classe :
    {classe: {"held_on": date, "rows": {inscription: ligne}}}."""
    snapshots = (
        DeliberationSnapshot.objects.filter(deliberation__class_group__in=groups)
        .annotate(group_id=F("deliberation__class_group_id"))
        .order_by("deliberation__class_group_id", "-version")
        .distinct("deliberation__class_group_id")
    )
    return {
        s.group_id: {"held_on": s.held_on, "rows": {row["enrollment"]: row for row in s.rows}}
        for s in snapshots
    }


def _following_level(level: Level, levels: list[Level]) -> Level | None:
    """Niveau suivant dans l'ordre de l'école ; aucun après le dernier, ni après l'Examen d'État."""
    if level.has_state_exam:
        return None
    index = next(i for i, item in enumerate(levels) if item.pk == level.pk)
    return levels[index + 1] if index + 1 < len(levels) else None


def _proposal(decision: str, group: ClassGroup, targets: list[ClassGroup], levels) -> tuple:
    """(issue, classe proposée ou None) : même option et même section si elles existent, sinon la
    seule classe du niveau ; plusieurs possibles → à choisir."""
    if not decision:
        return UNDECIDED, None
    if decision == Decision.RESIT:
        return WAITING, None
    if decision not in OFFERABLE:
        return NO_PLACE, None
    if decision == Decision.ORIENT:
        return CHOOSE, None
    level = group.level if decision == Decision.REPEAT else _following_level(group.level, levels)
    if level is None:
        return FINISHED, None
    candidates = [g for g in targets if g.level_id == level.pk]
    same_track = [g for g in candidates if g.track_id == group.track_id]
    match = next((g for g in same_track if g.section == group.section), None)
    if match is None and len(same_track) == 1:
        match = same_track[0]
    if match is None and len(candidates) == 1:
        match = candidates[0]
    return (SAME_LEVEL if decision == Decision.REPEAT else NEXT_LEVEL), match


def _targets(following: AcademicYear) -> list[ClassGroup]:
    return list(
        ClassGroup.objects.filter(academic_year=following).select_related(
            "academic_year", "level", "track"
        )
    )


@dataclass
class ClassSummary:
    group: ClassGroup
    proclaimed_on: object
    counts: Counter = field(default_factory=Counter)


def summary(year: AcademicYear, following: AcademicYear | None) -> list[ClassSummary]:
    """Une ligne par classe de l'année finie : proclamée ou non, élèves, places proposées et
    réponses, élèves déjà inscrits l'année suivante. Cinq requêtes, quel que soit le nombre."""
    groups = list(ClassGroup.objects.filter(academic_year=year).select_related("level", "track"))
    latest = _latest_rows(groups)
    lines = {g.pk: ClassSummary(g, latest.get(g.pk, {}).get("held_on")) for g in groups}
    pupils = list(
        Enrollment.objects.filter(class_group__in=groups)
        .exclude(status=Enrollment.Status.TRANSFERRED)
        .values_list("class_group_id", "student_id")
    )
    enrolled = (
        set(Enrollment.objects.filter(academic_year=following).values_list("student_id", flat=True))
        if following
        else set()
    )
    for group_id, student_id in pupils:
        lines[group_id].counts["students"] += 1
        lines[group_id].counts["enrolled"] += student_id in enrolled
    for group_id, answer in PlaceConfirmation.objects.filter(
        enrollment__class_group__in=groups, status=Status.OFFERED
    ).values_list("enrollment__class_group_id", "answer"):
        counts = lines[group_id].counts
        counts["offered"] += 1
        counts[answer or "no_answer"] += 1
    return list(lines.values())


@dataclass
class Row:
    enrollment: Enrollment
    decision: str
    percent: Decimal | None
    proposal: str
    proposed_class: ClassGroup | None
    place: PlaceConfirmation | None
    enrolled_class: ClassGroup | None
    on_portal: bool


@dataclass
class ClassPassage:
    group: ClassGroup
    year: AcademicYear
    following: AcademicYear | None
    proclaimed_on: object
    targets: list[ClassGroup]
    rows: list[Row]
    counts: Counter


def class_passage(group: ClassGroup) -> ClassPassage:
    """Élèves de la classe : décision figée, place proposée, réponse du parent, inscription de
    l'année suivante. Six requêtes, quel que soit le nombre d'élèves."""
    year, following = years()
    if year is None or group.academic_year_id != year.pk:
        raise BusinessError(NOT_FINISHED_YEAR)
    frozen = _latest_rows([group]).get(group.pk, {})
    decided = frozen.get("rows", {})
    enrollments = list(
        Enrollment.objects.filter(class_group=group)
        .exclude(status=Enrollment.Status.TRANSFERRED)
        .select_related("student__family")
        .order_by("student__last_name", "student__middle_name", "student__first_name", "pk")
    )
    targets = _targets(following) if following else []
    places = {
        p.enrollment_id: p
        for p in PlaceConfirmation.objects.filter(enrollment__class_group=group).select_related(
            "class_group__level", "class_group__track"
        )
    }
    enrolled = (
        {
            e.student_id: e.class_group
            for e in Enrollment.objects.filter(
                academic_year=following, student__in=[e.student_id for e in enrollments]
            ).select_related("class_group__level", "class_group__track")
        }
        if following
        else {}
    )
    levels = list(Level.objects.all())
    rows = []
    for enrollment in enrollments:
        line = decided.get(str(enrollment.pk), {})
        decision = line.get("decision", "")
        percent = line.get("percent")
        proposal, proposed = _proposal(decision, group, targets, levels)
        family = enrollment.student.family
        rows.append(
            Row(
                enrollment,
                decision,
                Decimal(percent) if percent is not None else None,
                proposal,
                proposed,
                places.get(enrollment.pk),
                enrolled.get(enrollment.student_id),
                family.primary_user_id is not None and family.portal_suspended_at is None,
            )
        )
    return ClassPassage(
        group, year, following, frozen.get("held_on"), targets, rows, place_counts(rows)
    )


def _place_data(place: PlaceConfirmation) -> dict:
    return {
        "school_year": place.class_group.academic_year.name,
        "class": place.class_group.name,
        "status": place.status,
    }


def _label(place: PlaceConfirmation) -> str:
    return place.enrollment.student.full_name


def _checked(group: ClassGroup, enrollment_ids) -> tuple[AcademicYear, list[Enrollment]]:
    """Année suivante et inscriptions demandées, toutes de cette classe de l'année finie."""
    year, following = years()
    if following is None:
        raise BusinessError(NO_NEXT_YEAR)
    if group.academic_year_id != year.pk:
        raise BusinessError(NOT_FINISHED_YEAR)
    wanted = set(enrollment_ids)
    enrollments = list(
        Enrollment.objects.filter(pk__in=wanted, class_group=group).select_related(
            "student__family"
        )
    )
    if len(enrollments) != len(wanted):
        raise BusinessError(NOT_IN_CLASS)
    return following, enrollments


def offer(group: ClassGroup, choices: dict, *, actor: User) -> int:
    """Propose (ou change) la place de chaque élève de `choices` ({inscription: classe de l'année
    suivante}) : visible tout de suite au Portail, le parent est prévenu ; une place retirée
    redevient proposée. Admis, doublant ou réorienté seulement, pas déjà inscrit l'année suivante.
    Rend le nombre de places nouvelles ou changées."""
    following, enrollments = _checked(group, choices)
    targets = {g.pk: g for g in _targets(following) if g.pk in set(choices.values())}
    if len(targets) != len(set(choices.values())):
        raise BusinessError(NOT_NEXT_YEAR)
    decided = _latest_rows([group]).get(group.pk, {}).get("rows", {})
    if any(decided.get(str(e.pk), {}).get("decision") not in OFFERABLE for e in enrollments):
        raise BusinessError(NO_PLACE_FOR_DECISION)
    if Enrollment.objects.filter(
        academic_year=following, student__in=[e.student_id for e in enrollments]
    ).exists():
        raise BusinessError(ALREADY_ENROLLED)
    existing = {
        p.enrollment_id: p
        for p in PlaceConfirmation.objects.filter(enrollment__in=enrollments).select_related(
            "class_group__academic_year", "class_group__level", "class_group__track"
        )
    }
    created, changed, notify = [], [], set()
    with transaction.atomic():
        for enrollment in enrollments:
            target = targets[choices[enrollment.pk]]
            place = existing.get(enrollment.pk)
            if place is None:
                created.append(
                    PlaceConfirmation(enrollment=enrollment, class_group=target, created_by=actor)
                )
                notify.add(enrollment.student.family_id)
                continue
            if place.class_group_id == target.pk and place.status == Status.OFFERED:
                continue
            before = _place_data(place)
            if place.status != Status.OFFERED:
                notify.add(enrollment.student.family_id)
            place.class_group, place.status = target, Status.OFFERED
            place.save(update_fields=["class_group", "status", "updated_at"])
            old, new = audit.changes(before, _place_data(place))
            audit.record(
                Action.STUDENTS_PLACE_OFFERED,
                place,
                actor=actor,
                before=old,
                after=new,
                label=enrollment.student.full_name,
            )
            changed.append(place)
        PlaceConfirmation.objects.bulk_create(created)
        audit.record_many(
            Action.STUDENTS_PLACE_OFFERED,
            [(place, _place_data(place)) for place in created],
            actor=actor,
            label=_label,
        )
        if notify:
            events.places_offered(notify, following.name)
    return len(created) + len(changed)


def withdraw(group: ClassGroup, enrollment_ids, *, actor: User) -> int:
    """Retire les places encore proposées (le parent ne les voit plus) ; les autres restent."""
    _following, enrollments = _checked(group, enrollment_ids)
    with transaction.atomic():
        places = list(
            PlaceConfirmation.objects.select_for_update(of=("self",))
            .filter(enrollment__in=enrollments, status=Status.OFFERED)
            .select_related(
                "enrollment__student",
                "class_group__academic_year",
                "class_group__level",
                "class_group__track",
            )
        )
        PlaceConfirmation.objects.filter(pk__in=[p.pk for p in places]).update(
            status=Status.WITHDRAWN
        )
        audit.record_many(
            Action.STUDENTS_PLACE_WITHDRAWN,
            [(place, {**_place_data(place), "status": Status.WITHDRAWN}) for place in places],
            actor=actor,
            label=_label,
        )
    return len(places)


def enroll(group: ClassGroup, enrollment_ids, *, actor: User) -> int:
    """Inscrit l'année suivante, dans la classe proposée, les élèves dont la place est proposée
    (réponse du parent ou non : c'est l'école qui décide) : frais dus d'après les barèmes de
    l'année suivante, matricule gardé. Un élève déjà inscrit entre-temps n'est pas inscrit deux
    fois. Rend le nombre d'inscriptions créées."""
    following, enrollments = _checked(group, enrollment_ids)
    with transaction.atomic():
        places = list(
            PlaceConfirmation.objects.select_for_update(of=("self",))
            .filter(enrollment__in=enrollments, status=Status.OFFERED)
            .select_related(
                "enrollment__student",
                "class_group__academic_year",
                "class_group__level",
                "class_group__track",
            )
        )
        already = set(
            Enrollment.objects.filter(
                academic_year=following,
                student__in=[p.enrollment.student_id for p in places],
            ).values_list("student_id", flat=True)
        )
        created = students.enroll_many(
            [
                (place.enrollment.student, place.class_group)
                for place in places
                if place.enrollment.student_id not in already
            ],
            actor=actor,
        )
        PlaceConfirmation.objects.filter(pk__in=[p.pk for p in places]).update(
            status=Status.ENROLLED
        )
    return len(created)


def place_counts(rows: list[Row]) -> Counter:
    """Compteurs de la classe affichés au-dessus du tableau."""
    counts: Counter = Counter(students=len(rows))
    for row in rows:
        if row.enrolled_class is not None:
            counts["enrolled"] += 1
        elif row.place is not None and row.place.status == Status.OFFERED:
            counts["offered"] += 1
            counts[row.place.answer or "no_answer"] += 1
    return counts
