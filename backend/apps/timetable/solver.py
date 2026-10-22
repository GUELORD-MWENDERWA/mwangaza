"""Calcul automatique de l'horaire (EDT.3a, spec emploi du temps § 7) : modèle CP-SAT.

On place des **unités** : un cours, ou les cours d'un groupe en parallèle (une classe, au même
moment, chacun son enseignant et sa salle) ou d'un cours commun (plusieurs classes ensemble, un
enseignant, une salle). Les séances de même longueur d'une unité sont interchangeables : une seule
variable par départ possible, `x[unité, longueur, jour, 1re heure, salles]`, et la somme des `x`
d'une longueur vaut son nombre de séances (O4). Un départ hors de la grille ou sur une récréation
que le cours ne passe pas (O5) n'existe pas ; un départ contraire à une règle réglable (absence,
heure interdite, salle fermée, heure déjà prise par ce qui ne bouge pas) n'est pas créé : le modèle
reste petit.

Une case ne reçoit qu'une séance : classes en numéros d'heure de leur grille (O1), enseignants
(O2) et salles (O3, sauf le terrain de sport) en temps, car les grilles d'une école à deux
vacations se chevauchent. Ce qui ne bouge pas (heures verrouillées, O6 ; reste de l'horaire quand on
ne recalcule qu'une classe ou un enseignant) occupe ses cases d'avance.

Impossible : on recommence avec chaque règle réglable reliée à une hypothèse ; CP-SAT rend celles
qui suffisent à l'impossibilité (`SufficientAssumptionsForInfeasibility`). O1 à O5 ne
s'assouplissent jamais.

`prepare` est du Python pur ; OR-Tools (≈ 75 Mo, pandas compris) n'est importé que dans `solve`,
c'est-à-dire dans la tâche de la file `heavy`."""

import itertools
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from time import monotonic
from types import SimpleNamespace
from uuid import UUID

from apps.academics.models import MAIN, MORNING
from apps.timetable import placement as placing
from apps.timetable.checks import Context, Week, _forbids, _teacher_loads, is_blocked
from apps.timetable.constraints import HARD, MIDDAY, matches
from apps.timetable.models import Room, TimetableEntry, TimetableRule

Kind = TimetableRule.Kind
ALL, CLASS, TEACHER = "all", "class", "teacher"
DONE, INFEASIBLE, TIMEOUT = "done", "infeasible", "timeout"
# Souhaits de la spec (§ 5) qui ne sont pas des lignes `TimetableRule`.
MORNING_WEIGHT = 3
STABILITY_WEIGHT = 8
BLOCKING_SHOWN = 10
# Groupes de règles réglables (hypothèses) : ("rule", id), ("absence", enseignant),
# ("teacher_day", enseignant), ("course_day", cours), ("no_gaps", classe), ("locks", classe),
# ("frozen",) : le reste de l'horaire, gardé tel quel.
Group = tuple
Cell = tuple  # (classe, jour, numéro d'heure)


@dataclass(slots=True)
class Unit:
    courses: list
    joint: bool
    weeks: list[Week]
    span_break: bool
    teachers: list[UUID]
    classes: list[UUID]
    in_scope: bool
    # Salles possibles, une liste par cours (cours commun : une seule, partagée).
    rooms: list[list[UUID | None]]


@dataclass(slots=True)
class Option:
    unit: int
    length: int
    weekday: int
    first: int
    rooms: tuple
    cells: list[Cell]
    atoms: list[tuple]
    blocked: list[Group]
    costs: list[tuple[Group, int]]


@dataclass
class Problem:
    ctx: Context
    units: list[Unit] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    # (unité, longueur) → séances à placer.
    need: dict[tuple[int, int], int] = field(default_factory=dict)
    # Ce qui ne bouge pas : cases de classe, temps des enseignants, heures par jour.
    fixed_cells: set = field(default_factory=set)
    fixed_teacher: set = field(default_factory=set)
    fixed_course_day: Counter = field(default_factory=Counter)
    fixed_sessions_day: Counter = field(default_factory=Counter)
    fixed_teacher_day: Counter = field(default_factory=Counter)
    # Séances du brouillon de départ recalculées (`replaced`), à garder si possible (stabilité).
    previous: dict[int, list[tuple[int, int, int]]] = field(default_factory=dict)
    replaced: set[UUID] = field(default_factory=set)
    # Verrous de règles `fixed_lesson` absents du brouillon : (unité, longueur, jour, 1re heure,
    # rang du cours, salle, groupe).
    required: list[tuple] = field(default_factory=list)
    gapless: list[UUID] = field(default_factory=list)
    # Par jour : les tranches de temps où une grille a une heure de cours, dans l'ordre.
    atoms: dict[int, list[tuple]] = field(default_factory=dict)

    @property
    def sessions(self) -> int:
        return sum(self.need.values())


@dataclass
class Outcome:
    status: str
    placements: list[dict] = field(default_factory=list)
    score: int | None = None
    unmet: list[dict] = field(default_factory=list)
    blocking: list[dict] = field(default_factory=list)
    duration_ms: int = 0


def _atoms(weeks: list[Week]) -> dict[int, list[tuple]]:
    bounds: dict[int, set] = defaultdict(set)
    lessons: dict[int, set] = defaultdict(set)
    for week in weeks:
        for weekday, start, end in week.lessons:
            bounds[weekday] |= {start, end}
            lessons[weekday].add((start, end))
    atoms = {}
    for weekday, points in bounds.items():
        ordered = sorted(points)
        atoms[weekday] = [
            (start, end)
            for start, end in itertools.pairwise(ordered)
            if any(a <= start and end <= b for a, b in lessons[weekday])
        ]
    return atoms


def _rooms_of(course, ctx: Context, by_kind: dict) -> list[UUID | None]:
    """Salle du cours, sinon une salle du type qu'il exige, sinon la salle de sa classe (comme les
    contrôles)."""
    room = ctx.rooms.get(course.room_id) if course.room_id else None
    if room is not None and room.is_active:
        return [room.pk]
    if course.room_kind:
        return by_kind.get(course.room_kind) or [None]
    home = ctx.rooms.get(ctx.by_group[course.class_group_id].home_room_id)
    return [home.pk] if home is not None and home.is_active else [None]


def _units(ctx: Context, scope: str, target: UUID | None) -> tuple[list[Unit], dict]:
    by_kind: dict[str, list[UUID]] = defaultdict(list)
    for room in sorted(ctx.rooms.values(), key=lambda room: room.name):
        if room.is_active:
            by_kind[room.kind].append(room.pk)
    grouped = [(members, False) for _rule, members in ctx.parallel if len(members) > 1]
    grouped += [(members, True) for _rule, members in ctx.joint if len(members) > 1]
    taken = {course.pk for members, _joint in grouped for course in members}
    grouped += [([course], False) for course in ctx.courses if course.pk not in taken]
    units, unit_of = [], {}
    for members, joint in grouped:
        weeks = []
        for course in members:
            week = ctx.week_of.get(course.class_group_id)
            if week is not None and week not in weeks:
                weeks.append(week)
        if scope == CLASS:
            in_scope = all(course.class_group_id == target for course in members)
        elif scope == TEACHER:
            in_scope = all(course.teacher_id == target for course in members)
        else:
            in_scope = True
        rooms = [_rooms_of(course, ctx, by_kind) for course in members[: 1 if joint else None]]
        unit_of.update({course.pk: len(units) for course in members})
        units.append(
            Unit(
                members,
                joint,
                weeks,
                all(placing.spans_break(course) for course in members),
                list(dict.fromkeys(course.teacher_id for course in members if course.teacher_id)),
                list(dict.fromkeys(course.class_group_id for course in members)),
                in_scope and all(ctx.week_of.get(course.class_group_id) for course in members),
                rooms,
            )
        )
    return units, unit_of


class _Builder:
    def __init__(self, ctx: Context, entries: list[TimetableEntry], scope: str, target) -> None:
        self.ctx = ctx
        self.problem = Problem(ctx)
        self.problem.units, self.unit_of = _units(ctx, scope, target)
        weeks = [week for week in ctx.week_of.values() if week is not None]
        self.problem.atoms = _atoms(list({id(week): week for week in weeks}.values()))
        # Clé occupée par ce qui ne bouge pas → groupes qui l'occupent.
        self.obstacles: dict[tuple, set[Group]] = defaultdict(set)
        self.sports = {pk for pk, room in ctx.rooms.items() if room.kind == Room.Kind.SPORTS}
        self.closed: dict[UUID, list[TimetableRule]] = defaultdict(list)
        for rule in ctx.rules:
            if rule.kind == Kind.ROOM_UNAVAILABLE:
                self.closed[UUID(rule.params["room"])].append(rule)
        self._keep(entries)

    def atoms_of(self, weekday: int, start, end) -> list[tuple]:
        return [
            (weekday, number)
            for number, (a, b) in enumerate(self.problem.atoms.get(weekday, []))
            if start <= a and b <= end
        ]

    def _keep(self, entries: list[TimetableEntry]) -> None:
        """Séances qui restent (verrouillées, ou hors de ce qu'on recalcule) : elles occupent leurs
        cases ; les autres séances des unités recalculées servent de référence (stabilité)."""
        problem, ctx = self.problem, self.ctx
        kept_lengths: dict[UUID, Counter] = defaultdict(Counter)
        self.kept_at: set[tuple] = set()
        for entry in entries:
            course = ctx.by_course.get(entry.course_id)
            if course is None:
                continue
            number = self.unit_of[course.pk]
            unit = problem.units[number]
            if unit.in_scope and not entry.locked:
                problem.replaced.add(entry.pk)
                if course.pk == unit.courses[0].pk:
                    problem.previous.setdefault(number, []).append(
                        (entry.weekday, entry.first, entry.length)
                    )
                continue
            group = ("locks", course.class_group_id) if entry.locked else ("frozen",)
            kept_lengths[course.pk][entry.length] += 1
            last = entry.first + entry.length - 1
            self.kept_at.add((course.pk, entry.weekday, entry.first, last))
            for index in range(entry.first, last + 1):
                cell = (course.class_group_id, entry.weekday, index)
                problem.fixed_cells.add(cell)
                self.obstacles[cell].add(group)
            problem.fixed_course_day[(course.pk, entry.weekday)] += entry.length
            problem.fixed_sessions_day[(course.pk, entry.weekday)] += 1
            week = ctx.week_of.get(course.class_group_id)
            run = week.span(entry.weekday, entry.first, last, True) if week else "outside_grid"
            if isinstance(run, str):
                continue
            atoms = self.atoms_of(entry.weekday, run[0].start, run[-1].end)
            if course.teacher_id:
                problem.fixed_teacher_day[(course.teacher_id, entry.weekday)] += entry.length
                for atom in atoms:
                    problem.fixed_teacher.add((course.teacher_id, *atom))
                    self.obstacles[("teacher", course.teacher_id, *atom)].add(group)
            if entry.room_id and entry.room_id not in self.sports:
                for atom in atoms:
                    self.obstacles[("room", entry.room_id, *atom)].add(group)
        for number, unit in enumerate(problem.units):
            if not unit.in_scope or not unit.weeks:
                continue
            reference = unit.courses[0]
            needed = Counter(placing.sessions(reference)) - kept_lengths[reference.pk]
            for length, count in needed.items():
                problem.need[(number, length)] = count
        self._complete_classes(kept_lengths)

    def _complete_classes(self, kept_lengths: dict[UUID, Counter]) -> None:
        """« Pas de trou » ne vaut que pour une classe dont toutes les séances seront placées."""
        if not self.ctx.school_rules["no_gaps"]:
            return
        incomplete = set()
        for course in self.ctx.courses:
            unit = self.problem.units[self.unit_of[course.pk]]
            if not unit.in_scope and Counter(placing.sessions(course)) - kept_lengths[course.pk]:
                incomplete.add(course.class_group_id)
        self.problem.gapless = [
            group.pk
            for group in self.ctx.groups
            if group.pk not in incomplete and self.ctx.week_of.get(group.pk)
        ]

    def options(self) -> None:
        ctx, problem = self.ctx, self.problem
        course_rules = [
            rule
            for rule in ctx.rules
            if rule.kind in (Kind.COURSE_NOT_SLOT, Kind.COURSE_PART_OF_DAY)
        ]
        free_days = [
            rule
            for rule in ctx.rules
            if rule.kind == Kind.TEACHER_FREE_DAY
            and rule.strength == HARD
            and rule.params["weekday"] is not None
        ]
        early = ctx.school_rules["main_courses_early"]
        lengths: dict[int, set[int]] = defaultdict(set)
        for number, length in problem.need:
            lengths[number].add(length)
        for number, unit_lengths in lengths.items():
            unit = problem.units[number]
            mine = [
                rule
                for rule in course_rules
                if any(matches(rule.params["target"], course) for course in unit.courses)
            ]
            morning = any(
                course.preferred_part == MORNING or (early and course.category == MAIN)
                for course in unit.courses
            )
            free = [rule for rule in free_days if rule.params["teacher"] in map(str, unit.teachers)]
            for length in sorted(unit_lengths):
                self._starts(number, unit, length, mine, morning, free)
        self._required()

    def _starts(self, number, unit: Unit, length, mine, morning, free) -> None:
        reference = unit.weeks[0]
        for weekday, day in sorted(reference.days.items()):
            for slot in day:
                if slot.index is None:
                    continue
                first, last = slot.index, slot.index + length - 1
                runs = [week.span(weekday, first, last, unit.span_break) for week in unit.weeks]
                if any(isinstance(run, str) for run in runs):
                    continue
                run = runs[0]
                slots = [(weekday, s.start, s.end) for s in run if s.index is not None]
                cells = [
                    (group, weekday, index)
                    for group in unit.classes
                    for index in range(first, last + 1)
                ]
                atoms = self.atoms_of(weekday, run[0].start, run[-1].end)
                blocked, costs = self._judge(unit, weekday, first, last, slots, cells, atoms, mine)
                blocked += [("rule", rule.pk) for rule in free if rule.params["weekday"] == weekday]
                late = sum(start >= MIDDAY for _day, start, _end in slots)
                if morning and late:
                    costs.append((("morning",), MORNING_WEIGHT * late))
                self._with_rooms(
                    number, unit, length, weekday, first, slots, cells, atoms, blocked, costs
                )

    def _judge(self, unit, weekday, first, last, slots, cells, atoms, mine):
        """Règles réglables qui interdisent ce départ (groupes), et souhaits qu'il ne tient pas."""
        ctx = self.ctx
        blocked: set[Group] = set()
        costs: list[tuple[Group, int]] = []
        for cell in cells:
            blocked |= self.obstacles.get(cell, set())
        for teacher in unit.teachers:
            profile = ctx.profiles.get(teacher)
            if profile and any(is_blocked(profile.unavailable, slot) for slot in slots):
                blocked.add(("absence", teacher))
            for atom in atoms:
                blocked |= self.obstacles.get(("teacher", teacher, *atom), set())
        week = unit.weeks[0]
        lock = SimpleNamespace(
            weekday=weekday,
            first=first,
            last=last,
            is_last=last == week.lessons_on(weekday),
            slots=slots,
        )
        for rule in mine:
            if _forbids(rule, lock):
                if rule.strength == HARD:
                    blocked.add(("rule", rule.pk))
                else:
                    costs.append((("rule", rule.pk), rule.weight))
        return list(blocked), costs

    def _with_rooms(
        self, number, unit, length, weekday, first, slots, cells, atoms, blocked, costs
    ):
        combos: list[tuple] = [()]
        for choices in unit.rooms:
            combos = [(*combo, room) for combo in combos for room in choices]
        for rooms in combos:
            extra_blocked: set[Group] = set()
            extra_costs = []
            for room in rooms:
                if room is None or room in self.sports:
                    continue
                for atom in atoms:
                    extra_blocked |= self.obstacles.get(("room", room, *atom), set())
                for rule in self.closed.get(room, []):
                    params = {k: v for k, v in rule.params.items() if k != "room"}
                    if any(is_blocked([params], slot) for slot in slots):
                        if rule.strength == HARD:
                            extra_blocked.add(("rule", rule.pk))
                        else:
                            extra_costs.append((("rule", rule.pk), rule.weight))
            self.problem.options.append(
                Option(
                    number,
                    length,
                    weekday,
                    first,
                    rooms,
                    cells,
                    atoms,
                    blocked + list(extra_blocked - set(blocked)),
                    costs + extra_costs,
                )
            )

    def _required(self) -> None:
        """Verrous de règles `fixed_lesson` qui ne sont pas déjà dans ce qui reste."""
        for rule in self.ctx.rules:
            if rule.kind != Kind.FIXED_LESSON:
                continue
            params = rule.params
            course = self.ctx.by_course.get(UUID(params["course"]))
            if course is None:
                continue
            number = self.unit_of[course.pk]
            unit = self.problem.units[number]
            key = (course.pk, params["weekday"], params["first"], params["last"])
            if not unit.in_scope or key in self.kept_at:
                continue
            member = next(i for i, c in enumerate(unit.courses) if c.pk == course.pk)
            room = UUID(params["room"]) if params.get("room") else None
            self.problem.required.append(
                (
                    number,
                    params["last"] - params["first"] + 1,
                    params["weekday"],
                    params["first"],
                    0 if unit.joint else member,
                    room,
                    ("rule", rule.pk),
                )
            )


def prepare(
    ctx: Context, entries: list[TimetableEntry], scope: str = ALL, target: UUID | None = None
) -> Problem:
    """Le problème d'un brouillon, en Python pur : unités, départs permis, ce qui ne bouge pas."""
    builder = _Builder(ctx, entries, scope, target)
    builder.options()
    return builder.problem


class _Model:
    """Le modèle CP-SAT d'un problème : strict (départs contraires aux règles non créés, souhaits
    dans l'objectif) ou `explain` (tous les départs de la grille, chaque groupe de règles relié à
    une hypothèse, sans objectif)."""

    def __init__(self, problem: Problem, explain: bool) -> None:
        from ortools.sat.python import cp_model

        self.cp = cp_model
        self.problem, self.explain = problem, explain
        self.model = cp_model.CpModel()
        self.assume: dict[Group, object] = {}
        self.chosen: list[tuple[Option, object]] = []
        self.terms: list[tuple[Group, int, object]] = []
        # Journées d'un enseignant (règle « peu de trous ») : blocs d'heures qui commencent.
        self.days: list[tuple[Group, int, list]] = []
        self.by_key: dict[tuple, list] = defaultdict(list)
        self.by_unit_day: dict[tuple, list] = defaultdict(list)
        self.by_teacher_day: dict[tuple, list] = defaultdict(list)
        self.by_start: dict[tuple, list] = defaultdict(list)
        rooms = problem.ctx.rooms
        self.sports = {pk for pk, room in rooms.items() if room.kind == Room.Kind.SPORTS}
        self._variables()
        self._exactly()
        self._at_most_one()
        self._day_limits()
        self._no_gaps()
        self._rules()
        self._required()
        if not explain:
            self._stability()
            self.model.minimize(self.objective())

    def penalize(self, group: Group, weight: int, expr) -> None:
        if not isinstance(expr, int):
            self.terms.append((group, weight, expr))

    def objective(self):
        compact = sum(weight * var for _group, weight, day in self.days for var in day)
        return sum(weight * expr for _key, weight, expr in self.terms) + compact

    def lit(self, group: Group):
        if group not in self.assume:
            self.assume[group] = self.model.new_bool_var(str(group))
        return self.assume[group]

    def enforce(self, constraint, group: Group) -> None:
        if self.explain:
            constraint.only_enforce_if(self.lit(group))

    def never(self, group: Group) -> None:
        """Ce groupe, s'il tient, rend le problème impossible."""
        if self.explain:
            self.model.add_bool_or([~self.lit(group)])
        else:
            flag = self.model.new_bool_var("")
            self.model.add(flag == 1)
            self.model.add(flag == 0)

    def _variables(self) -> None:
        problem = self.problem
        for option in problem.options:
            if option.blocked and not self.explain:
                continue
            var = self.model.new_bool_var("")
            for group in option.blocked:
                self.model.add_implication(var, ~self.lit(group))
            self.chosen.append((option, var))
            unit = problem.units[option.unit]
            self.by_start[(option.unit, option.length, option.weekday, option.first)].append(
                (option, var)
            )
            self.by_unit_day[(option.unit, option.weekday)].append((option.length, var))
            for cell in option.cells:
                self.by_key[cell].append(var)
            for teacher in unit.teachers:
                self.by_teacher_day[(teacher, option.weekday)].append((option.length, var))
                for atom in option.atoms:
                    self.by_key[("teacher", teacher, *atom)].append(var)
            for room in set(option.rooms):
                if room is not None and room not in self.sports:
                    for atom in option.atoms:
                        self.by_key[("room", room, *atom)].append(var)
            if not self.explain:
                for group, weight in option.costs:
                    self.terms.append((group, weight, var))

    def _exactly(self) -> None:
        """O4 : chaque unité reçoit exactement ses séances."""
        by_length: dict[tuple, list] = defaultdict(list)
        for option, var in self.chosen:
            by_length[(option.unit, option.length)].append(var)
        for key, count in self.problem.need.items():
            variables = by_length.get(key, [])
            if len(variables) < count:
                self.never(("unit", key[0]))
            else:
                self.model.add(sum(variables) == count)

    def _at_most_one(self) -> None:
        """O1 à O3 : une séance au plus par case de classe, temps d'enseignant, temps de salle."""
        for variables in self.by_key.values():
            if len(variables) > 1:
                self.model.add_at_most_one(variables)

    def _day_limits(self) -> None:
        """Heures d'un cours au plus par jour (cours, sinon règle de l'école) ; heures d'un
        enseignant au plus par jour (profil, sinon règle de l'école)."""
        problem, ctx = self.problem, self.problem.ctx
        school_max = ctx.school_rules["max_same_course_per_day"]
        for (number, weekday), items in self.by_unit_day.items():
            unit = problem.units[number]
            limits = [
                (
                    placing.max_per_day(course, school_max)
                    - problem.fixed_course_day[(course.pk, weekday)],
                    course,
                )
                for course in unit.courses
            ]
            most, course = min(limits, key=lambda item: item[0])
            if sum(length for length, _var in items) > most:
                self.enforce(
                    self.model.add(sum(length * var for length, var in items) <= max(most, 0)),
                    ("course_day", course.pk),
                )
        default = ctx.school_rules["teacher_max_day_hours"]
        for (teacher, weekday), items in self.by_teacher_day.items():
            profile = ctx.profiles.get(teacher)
            most = ((profile.max_day_hours if profile else None) or default) - (
                problem.fixed_teacher_day[(teacher, weekday)]
            )
            if sum(length for length, _var in items) > most:
                self.enforce(
                    self.model.add(sum(length * var for length, var in items) <= max(most, 0)),
                    ("teacher_day", teacher),
                )

    def _no_gaps(self) -> None:
        """Pas de trou : les heures occupées d'une classe, chaque jour, partent de la 1re. Une case
        occupée = un booléen (la somme des séances qui la couvrent) ; « heure suivante occupée ⇒
        heure d'avant occupée » se propage bien mieux qu'une inégalité entre deux sommes."""
        problem, group_of = self.problem, ("no_gaps",)
        for group in problem.gapless:
            week = problem.ctx.week_of[group]
            for weekday in week.days:
                previous = None
                for index in range(1, week.lessons_on(weekday) + 1):
                    cell = (group, weekday, index)
                    variables = self.by_key.get(cell, [])
                    if cell in problem.fixed_cells:
                        here = 1
                    elif variables:
                        here = self.model.new_bool_var("")
                        self.model.add(sum(variables) == here)
                    else:
                        here = 0
                    if previous is not None and not (isinstance(here, int) and not here):
                        if isinstance(previous, int) and isinstance(here, int):
                            if not previous:
                                self.never((*group_of, group))
                        elif isinstance(previous, int):
                            if not previous:
                                self.enforce(self.model.add(here == 0), (*group_of, group))
                        elif isinstance(here, int):
                            self.enforce(self.model.add(previous == 1), (*group_of, group))
                        else:
                            implication = self.model.add_implication(here, previous)
                            self.enforce(implication, (*group_of, group))
                    previous = here

    def _days_of(self, number: int) -> dict[int, list]:
        days: dict[int, list] = defaultdict(list)
        for weekday in self.problem.units[number].weeks[0].days:
            days[weekday] = [var for _length, var in self.by_unit_day.get((number, weekday), [])]
        return days

    def _used(self, variables: list, fixed: int):
        """1 si le cours (ou l'enseignant) a une séance ce jour-là, sinon 0."""
        if fixed:
            return 1
        if not variables:
            return 0
        used = self.model.new_bool_var("")
        for var in variables:
            self.model.add_implication(var, used)
        self.model.add(used <= sum(variables))
        return used

    def _rules(self) -> None:
        for rule in self.problem.ctx.rules:
            if rule.kind == Kind.SPREAD_OVER_WEEK:
                self._spread(rule)
            elif rule.kind == Kind.TEACHER_FREE_DAY:
                self._free_day(rule)
            elif rule.kind == Kind.TEACHER_COMPACT and not self.explain:
                self._compact(rule)

    def _spread(self, rule: TimetableRule) -> None:
        """Étaler sur la semaine : une séance par jour au plus, et (au choix) pas deux jours de
        suite. Obligatoire : contrainte ; souhait : pénalité par séance de trop dans un jour et par
        paire de jours qui se suivent."""
        if self.explain and rule.strength != HARD:
            return
        problem, group = self.problem, ("rule", rule.pk)
        for number, unit in enumerate(problem.units):
            if not unit.in_scope or not any(
                matches(rule.params["target"], course) for course in unit.courses
            ):
                continue
            reference = unit.courses[0]
            if len(placing.sessions(reference)) < 2:
                continue
            days = self._days_of(number)
            used = {}
            for weekday, variables in days.items():
                fixed = problem.fixed_sessions_day[(reference.pk, weekday)]
                if rule.strength == HARD and variables:
                    self.enforce(self.model.add(sum(variables) <= max(0, 1 - fixed)), group)
                used[weekday] = self._used(variables, fixed)
            if rule.strength != HARD:
                total = len(placing.sessions(reference))
                self.penalize(group, rule.weight, total - sum(used.values()))
            if rule.params.get("no_consecutive_days", True):
                for weekday in used:
                    after = used.get(weekday + 1)
                    if after is None or (isinstance(after, int) and isinstance(used[weekday], int)):
                        continue
                    if rule.strength == HARD:
                        self.enforce(self.model.add(used[weekday] + after <= 1), group)
                    else:
                        both = self.model.new_bool_var("")
                        self.model.add(both >= used[weekday] + after - 1)
                        self.penalize(group, rule.weight, both)

    def _free_day(self, rule: TimetableRule) -> None:
        """Jour libre d'un enseignant ; un jour précis obligatoire est déjà dans les départs."""
        params, group = rule.params, ("rule", rule.pk)
        teacher = UUID(params["teacher"])
        weekdays = sorted({weekday for (pk, weekday) in self.by_teacher_day if pk == teacher})
        if not weekdays:
            return
        if params["weekday"] is not None:
            if rule.strength != HARD and not self.explain:
                variables = [
                    v for _l, v in self.by_teacher_day.get((teacher, params["weekday"]), [])
                ]
                fixed = self.problem.fixed_teacher_day[(teacher, params["weekday"])]
                self.penalize(group, rule.weight, self._used(variables, fixed))
            return
        if self.explain and rule.strength != HARD:
            return
        free = []
        for weekday in weekdays:
            if self.problem.fixed_teacher_day[(teacher, weekday)]:
                continue
            day_free = self.model.new_bool_var("")
            for _length, var in self.by_teacher_day[(teacher, weekday)]:
                self.model.add(var + day_free <= 1)
            free.append(day_free)
        if rule.strength == HARD:
            if free:
                self.enforce(self.model.add(sum(free) >= 1), group)
            else:
                self.never(group)
        elif free:
            has = self.model.new_bool_var("")
            self.model.add(has <= sum(free))
            self.penalize(group, rule.weight, 1 - has)

    def _compact(self, rule: TimetableRule) -> None:
        """Peu de trous dans la journée d'un enseignant : chaque bloc d'heures qui commence coûte
        le poids ; le nombre de trous du jour est ce nombre moins un."""
        problem = self.problem
        wanted = rule.params.get("teacher")
        for (teacher, weekday), _items in list(self.by_teacher_day.items()):
            if wanted and str(teacher) != wanted:
                continue
            previous, day = 0, []
            for number in range(len(problem.atoms.get(weekday, []))):
                key = ("teacher", teacher, weekday, number)
                fixed = 1 if (teacher, weekday, number) in problem.fixed_teacher else 0
                here = fixed + sum(self.by_key.get(key, []))
                if not isinstance(here, int):
                    begins = self.model.new_bool_var("")
                    self.model.add(begins >= here - previous)
                    day.append(begins)
                previous = here
            if day:
                self.days.append((("rule", rule.pk), rule.weight, day))

    def _required(self) -> None:
        for number, length, weekday, first, member, room, group in self.problem.required:
            variables = [
                var
                for option, var in self.by_start.get((number, length, weekday, first), [])
                if room is None or option.rooms[member] == room
            ]
            if variables:
                self.enforce(self.model.add(sum(variables) >= 1), group)
            else:
                self.never(group)

    def _stability(self) -> None:
        """Garder les séances du brouillon de départ là où elles étaient."""
        for number, positions in self.problem.previous.items():
            for weekday, first, length in positions:
                variables = [
                    var for _o, var in self.by_start.get((number, length, weekday, first), [])
                ]
                if variables:
                    self.penalize(("moved",), STABILITY_WEIGHT, 1 - sum(variables))


def _solver(cp, seconds: float):
    solver = cp.CpSolver()
    solver.parameters.max_time_in_seconds = max(1.0, seconds)
    # Serveur partagé : un seul fil de recherche (spec § 7).
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 1
    return solver


def _placements(problem: Problem, built: _Model, solver) -> list[dict]:
    """Les séances placées ; celles qu'une règle `fixed_lesson` impose sont verrouillées."""
    required = {item[:4] for item in problem.required}
    rows = []
    for option, var in built.chosen:
        if not solver.boolean_value(var):
            continue
        unit = problem.units[option.unit]
        locked = (option.unit, option.length, option.weekday, option.first) in required
        for rank, course in enumerate(unit.courses):
            rows.append(
                {
                    "course": course.pk,
                    "weekday": option.weekday,
                    "first": option.first,
                    "length": option.length,
                    "room": option.rooms[0 if unit.joint else rank],
                    "locked": locked,
                }
            )
    return rows


def _unmet(built: _Model, solver) -> list[dict]:
    """Souhaits non tenus, par règle (ou réglage de l'école) : combien de fois."""
    counts: Counter = Counter()
    for key, _weight, expr in built.terms:
        if solver.value(expr) > 0:
            counts[key] += 1
    for key, _weight, day in built.days:
        # Trous de la journée : blocs d'heures moins un.
        gaps = sum(solver.boolean_value(var) for var in day) - 1
        if gaps > 0:
            counts[key] += gaps
    rows = []
    for key, count in counts.items():
        row = {"code": key[0], "count": count}
        if key[0] == "rule":
            row["rule"] = str(key[1])
        rows.append(row)
    return sorted(rows, key=lambda row: -row["count"])


def describe(problem: Problem, group: Group) -> dict:
    """Une règle qui bloque, en données que l'écran met en phrase (EDT.3b)."""
    ctx = problem.ctx
    code, key = group[0], (group[1] if len(group) > 1 else None)
    row: dict = {"code": code}
    if code == "rule":
        rule = next(rule for rule in ctx.rules if rule.pk == key)
        row |= {"rule": str(key), "kind": rule.kind, "subject": str(rule.get_kind_display())}
    elif code in ("absence", "teacher_day"):
        loads, names = _teacher_loads(ctx.courses, ctx.staff, ctx.joint)
        profile = ctx.profiles.get(key)
        row |= {"teacher": str(key), "subject": names.get(key, "")}
        if code == "absence":
            slots = {
                slot
                for course in ctx.courses
                if course.teacher_id == key and ctx.week_of.get(course.class_group_id)
                for slot in ctx.week_of[course.class_group_id].lessons
            }
            free = [slot for slot in slots if not is_blocked(profile.unavailable, slot)]
            row["values"] = {"due": loads.get(key, 0), "available": len(free)}
        else:
            most = (profile.max_day_hours if profile else None) or ctx.school_rules[
                "teacher_max_day_hours"
            ]
            row["values"] = {"max": most, "due": loads.get(key, 0)}
    elif code == "course_day":
        course = ctx.by_course[key]
        most = placing.max_per_day(course, ctx.school_rules["max_same_course_per_day"])
        row |= {
            "course": str(key),
            "class_group": str(course.class_group_id),
            "subject": f"{course.name} · {ctx.by_group[course.class_group_id].name}",
            "values": {"max": most, "hours": course.weekly_hours or 0},
        }
    elif code in ("no_gaps", "locks"):
        row |= {"class_group": str(key), "subject": ctx.by_group[key].name}
    elif code == "unit":
        course = problem.units[key].courses[0]
        row |= {
            "course": str(course.pk),
            "class_group": str(course.class_group_id),
            "subject": f"{course.name} · {ctx.by_group[course.class_group_id].name}",
        }
    return row


# Part du temps (spec § 7) : recherche ordinaire courte (petits cas, impossibilité prouvée vite),
# puis recherche locale jusqu'au premier horaire (au moins 8 s, ≈ 4 s pour l'ITIG de démonstration
# préparation comprise) ; le reste améliore les souhaits.
FIRST_SHARE, LOCAL_SHARE, LOCAL_SECONDS = 0.15, 0.35, 8


def _attempt(cp, built: _Model, seconds: float, *, local: bool = False, hint=None):
    solver = _solver(cp, seconds)
    if local:
        # Avec un seul fil, CP-SAT n'essaie pas la recherche locale de lui-même ; c'est elle qui
        # trouve vite un premier horaire quand « pas de trou » rend la recherche ordinaire lente.
        solver.parameters.use_ls_only = True
        solver.parameters.stop_after_first_solution = True
    built.model.clear_hints()
    for var, value in hint or []:
        built.model.add_hint(var, value)
    return solver, solver.solve(built.model)


def _explain(problem: Problem, cp, seconds: float) -> list[dict]:
    explained = _Model(problem, explain=True)
    explained.model.add_assumptions(list(explained.assume.values()))
    solver = _solver(cp, seconds)
    if solver.solve(explained.model) != cp.INFEASIBLE:
        return []
    index = {lit.index: group for group, lit in explained.assume.items()}
    found = [index[i] for i in solver.sufficient_assumptions_for_infeasibility()]
    return [describe(problem, group) for group in found[:BLOCKING_SHOWN]]


def solve(problem: Problem, time_limit: int, explain_limit: int) -> Outcome:
    """Résout dans le temps donné ; impossible → seconde résolution qui nomme les règles qui
    bloquent. Temps écoulé : la meilleure solution trouvée (toutes les règles obligatoires
    tiennent), sinon « pas trouvé dans le temps »."""
    from ortools.sat.python import cp_model as cp

    began = monotonic()

    def elapsed() -> int:
        return int((monotonic() - began) * 1000)

    def left() -> float:
        return time_limit - (monotonic() - began)

    if not problem.need:
        return Outcome(DONE, [], 0, [], [], 0)
    built = _Model(problem, explain=False)
    solved = (cp.OPTIMAL, cp.FEASIBLE)
    best = None
    solver, status = _attempt(cp, built, time_limit * FIRST_SHARE)
    if status == cp.MODEL_INVALID:
        raise RuntimeError(built.model.validate())
    if status in solved:
        best = solver
    if status == cp.INFEASIBLE:
        return Outcome(
            INFEASIBLE, blocking=_explain(problem, cp, explain_limit), duration_ms=elapsed()
        )
    if best is None and left() >= 1:
        budget = max(time_limit * LOCAL_SHARE, LOCAL_SECONDS)
        solver, status = _attempt(cp, built, min(left(), budget), local=True)
        if status in solved:
            best = solver
    if status != cp.OPTIMAL and left() >= 1:
        hint = [(var, best.boolean_value(var)) for _o, var in built.chosen] if best else None
        solver, status = _attempt(cp, built, left(), hint=hint)
        if status in solved and (best is None or solver.objective_value <= best.objective_value):
            best = solver
        if status == cp.INFEASIBLE and best is None:
            blocking = _explain(problem, cp, explain_limit)
            return Outcome(INFEASIBLE, blocking=blocking, duration_ms=elapsed())
    if best is None:
        return Outcome(TIMEOUT, duration_ms=elapsed())
    return Outcome(
        DONE,
        _placements(problem, built, best),
        int(best.objective_value),
        _unmet(built, best),
        [],
        elapsed(),
    )
