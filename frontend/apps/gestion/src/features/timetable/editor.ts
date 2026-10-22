// Éditeur de l'horaire (EDT.2a et EDT.2b, maquettes `emploi-du-temps-*`) : calculs de l'écran sur
// l'état d'un brouillon. Le serveur reste juge des conflits (il les renvoie après chaque geste) ;
// l'écran ne fait que ranger les séances d'une vue (classe, enseignant, salle) dans une grille et
// teinter les cases pendant le choix d'une heure (vert : possible, rouge : classe, enseignant ou
// salle déjà pris, enseignant absent, gris : ne tient pas).
import type { Schemas } from "@mwangaza/api";

import { type Absence, isBlocked } from "./availability";
import type { ClassRow, Room, TeacherProfile, TimeGrid } from "./data";
import { toClock, toMinutes } from "./week";

export type DraftState = Schemas["DraftState"];
export type Entry = Schemas["Entry"];
export type EditorCourse = Schemas["TimetableCourse"];
export type Issue = Schemas["CheckIssue"];
type Slot = Schemas["TimeSlot"];

/** Les cases de chaque jour d'une grille, dans l'ordre. */
export type Days = Map<number, Slot[]>;

export function daysOf(grid: TimeGrid | undefined): Days {
  const days: Days = new Map();
  for (const slot of grid?.slots ?? []) {
    days.set(slot.weekday, [...(days.get(slot.weekday) ?? []), slot]);
  }
  for (const slots of days.values()) slots.sort((a, b) => toMinutes(a.start) - toMinutes(b.start));
  return new Map([...days].sort(([a], [b]) => a - b));
}

/** Début et fin (minutes) d'une séance de `length` heures à partir de la `first`e heure,
 *  récréations comprises ; `null` si elle sort de la journée ou passe une récréation interdite. */
export function span(
  day: Slot[] | undefined,
  first: number,
  length: number,
  spansBreak: boolean,
): { start: number; end: number } | null {
  const at = day?.findIndex((slot) => slot.kind === "lesson" && slot.index === first) ?? -1;
  if (!day || at < 0) return null;
  let lessons = 0;
  let end = 0;
  for (const slot of day.slice(at)) {
    if (lessons === length) break;
    if (slot.kind === "break" && !spansBreak) return null;
    if (slot.kind === "lesson") lessons += 1;
    end = toMinutes(slot.end);
  }
  const start = day[at]?.start;
  return lessons === length && start ? { start: toMinutes(start), end } : null;
}

/** Ce que l'écran sait d'un brouillon : cours, classes, grilles, salles, absences. */
export type Board = {
  courses: Map<string, EditorCourse>;
  classes: Map<string, ClassRow>;
  rooms: Map<string, Room>;
  /** Absences de chaque enseignant (EDT.1b), en heures d'horloge. */
  absences: Map<string, Absence[]>;
  /** Grille d'une classe (la sienne, sinon celle par défaut). */
  gridOf: (classId: string) => string;
  daysOfGrid: (gridId: string | undefined) => Days;
  daysOfClass: (classId: string) => Days;
};

export function boardOf(
  courses: EditorCourse[],
  classes: ClassRow[],
  grids: TimeGrid[],
  rooms: Room[],
  profiles: TeacherProfile[] = [],
): Board {
  const byGrid = new Map(grids.map((grid) => [grid.id, daysOf(grid)]));
  const fallbackId = grids.find((grid) => grid.is_default)?.id ?? "";
  const fallback = byGrid.get(fallbackId) ?? new Map();
  const classMap = new Map(classes.map((row) => [row.id, row]));
  const gridOf = (classId: string) => {
    const grid = classMap.get(classId)?.time_grid;
    return grid && byGrid.has(grid) ? grid : fallbackId;
  };
  const daysOfGrid = (gridId: string | undefined) => (gridId && byGrid.get(gridId)) || fallback;
  return {
    courses: new Map(courses.map((course) => [course.id, course])),
    classes: classMap,
    rooms: new Map(rooms.map((room) => [room.id, room])),
    absences: new Map(profiles.map((profile) => [profile.teacher, profile.unavailable])),
    gridOf,
    daysOfGrid,
    daysOfClass: (classId) => daysOfGrid(gridOf(classId)),
  };
}

/** Une séance placée, avec ses heures d'horloge (pour comparer deux grilles). */
export type Placed = {
  entry: Entry;
  course: EditorCourse;
  start: number;
  end: number;
};

export function placedOf(board: Board, entries: Entry[]): Placed[] {
  return entries.flatMap((entry) => {
    const course = board.courses.get(entry.course);
    if (!course) return [];
    const days = board.daysOfClass(course.class_group);
    const run = span(days.get(entry.weekday), entry.first, entry.length, true);
    return run ? [{ entry, course, ...run }] : [];
  });
}

/** Salle d'une séance qu'on place : celle du cours, sinon celle de la classe (un type exigé reste
 *  à choisir), comme le serveur. */
export function defaultRoom(board: Board, course: EditorCourse): string | null {
  if (course.room) return course.room;
  if (course.room_kind) return null;
  return board.classes.get(course.class_group)?.home_room ?? null;
}

export type Tint =
  | { kind: "fits" }
  | { kind: "short" }
  | { kind: "absent"; teacher: string }
  | { kind: "conflict"; reason: "class" | "teacher" | "room"; other: Placed };

/** La séance tiendrait-elle là, et qu'est-ce qui y est déjà pris ? `ignore` : les séances qui
 *  partent de là (celle qu'on déplace, celle avec qui on échange). */
export function tint(
  board: Board,
  placed: Placed[],
  move: { course: EditorCourse; length: number; room: string | null },
  weekday: number,
  first: number,
  ignore: string[] = [],
): Tint {
  const { course, length, room } = move;
  const run = span(
    board.daysOfClass(course.class_group).get(weekday),
    first,
    length,
    course.spans_break,
  );
  if (!run) return { kind: "short" };
  const { start, end } = run;
  const others = placed.filter(
    (item) =>
      !ignore.includes(item.entry.id) &&
      item.entry.weekday === weekday &&
      item.start < end &&
      start < item.end,
  );
  const sameClass = others.find((item) => item.course.class_group === course.class_group);
  if (sameClass) return { kind: "conflict", reason: "class", other: sameClass };
  const sameTeacher = course.teacher
    ? others.find((item) => item.course.teacher === course.teacher)
    : undefined;
  if (sameTeacher) return { kind: "conflict", reason: "teacher", other: sameTeacher };
  const sameRoom =
    room && board.rooms.get(room)?.kind !== "sports"
      ? others.find((item) => item.entry.room === room)
      : undefined;
  if (sameRoom) return { kind: "conflict", reason: "room", other: sameRoom };
  const absent =
    course.teacher &&
    isBlocked(board.absences.get(course.teacher) ?? [], weekday, {
      start: toClock(start),
      end: toClock(end),
    });
  if (absent) return { kind: "absent", teacher: course.teacher_name };
  return { kind: "fits" };
}

/** Ce que montre une vue (EDT.2b) : une classe, un enseignant ou une salle. */
export type View = "class" | "teacher" | "room";

/** Une séance « À placer » : une des séances restantes d'un cours. */
export type LeftItem = { course: EditorCourse; length: number; key: string };

/** Les séances, le reste à placer, les conflits et la grille d'une vue. Enseignant ou salle : la
 *  grille la plus fréquente de leurs classes ; `mixed` si leurs classes en suivent plusieurs (les
 *  séances sont alors rangées par numéro d'heure). « À placer » d'une salle : les cours dont c'est
 *  la salle par défaut. */
export function focusOf(board: Board, state: DraftState, view: View, id: string) {
  const inView = (entry: Entry) => {
    const course = board.courses.get(entry.course);
    if (!course) return false;
    if (view === "class") return course.class_group === id;
    return view === "teacher" ? course.teacher === id : entry.room === id;
  };
  const owns = (course: EditorCourse) =>
    view === "class"
      ? course.class_group === id
      : view === "teacher"
        ? course.teacher === id
        : defaultRoom(board, course) === id;
  const entries = state.entries.filter(inView);
  const left: LeftItem[] = state.left.flatMap((row) => {
    const course = board.courses.get(row.course);
    return course && owns(course)
      ? row.lengths.map((length, index) => ({ course, length, key: `${row.course}-${index}` }))
      : [];
  });
  const byId = new Map(state.entries.map((entry) => [entry.id, entry]));
  const field = view === "class" ? "class_group" : view;
  const issues = state.issues.filter(
    (issue) =>
      issue[field] === id ||
      entriesOf(issue).some((entryId) => {
        const entry = byId.get(entryId);
        return entry ? inView(entry) : false;
      }),
  );
  const groups = new Set(
    view === "class"
      ? [id]
      : [
          ...entries.flatMap((entry) => board.courses.get(entry.course)?.class_group ?? []),
          ...left.map((item) => item.course.class_group),
        ],
  );
  const counts = new Map<string, number>();
  for (const group of groups) {
    const grid = board.gridOf(group);
    counts.set(grid, (counts.get(grid) ?? 0) + 1);
  }
  const grid = [...counts].sort((a, b) => b[1] - a[1])[0]?.[0];
  return { entries, left, issues, days: board.daysOfGrid(grid), mixed: counts.size > 1 };
}

/** Heures d'une grille occupées par des séances (une heure prise deux fois compte une fois). */
export function hoursOf(entries: Entry[], weekday?: number): number {
  return new Set(
    entries
      .filter((entry) => weekday === undefined || entry.weekday === weekday)
      .flatMap((entry) =>
        Array.from({ length: entry.length }, (_, k) => `${entry.weekday}-${entry.first + k}`),
      ),
  ).size;
}

/** Lignes de la grille d'une classe : chaque heure de cours, et une récréation après la `index`e
 *  heure quand un jour en a une. */
export type Row = { key: string; kind: "lesson" | "break"; index: number; start: string };

export function rowsOf(days: Days): Row[] {
  const lessons = new Map<number, string>();
  const breaks = new Map<number, string>();
  for (const slots of days.values()) {
    let last = 0;
    for (const slot of slots) {
      if (slot.kind === "lesson" && slot.index) {
        last = slot.index;
        if (!lessons.has(last)) lessons.set(last, slot.start);
      } else if (last && !breaks.has(last)) {
        breaks.set(last, slot.start);
      }
    }
  }
  return [...lessons.keys()]
    .sort((a, b) => a - b)
    .flatMap((index): Row[] => [
      { key: `L${index}`, kind: "lesson", index, start: lessons.get(index) ?? "" },
      ...(breaks.has(index)
        ? [{ key: `B${index}`, kind: "break" as const, index, start: breaks.get(index) ?? "" }]
        : []),
    ]);
}

/** Couloirs des séances d'un jour qui se chevauchent (groupes en parallèle, conflit) : chacune
 *  prend sa part de la largeur de la case. */
export function lanesOf(entries: Entry[]): Map<string, { lane: number; lanes: number }> {
  const sorted = [...entries].sort((a, b) => a.first - b.first);
  const result = new Map<string, { lane: number; lanes: number }>();
  let cluster: Entry[] = [];
  let ends: number[] = [];
  let clusterEnd = 0;
  const close = () => {
    for (const entry of cluster) {
      result.set(entry.id, { lane: result.get(entry.id)?.lane ?? 0, lanes: ends.length });
    }
    cluster = [];
    ends = [];
  };
  for (const entry of sorted) {
    if (cluster.length && entry.first > clusterEnd) close();
    const last = entry.first + entry.length - 1;
    let lane = ends.findIndex((end) => end < entry.first);
    if (lane < 0) lane = ends.push(last) - 1;
    else ends[lane] = last;
    result.set(entry.id, { lane, lanes: 1 });
    cluster.push(entry);
    clusterEnd = Math.max(clusterEnd, last);
  }
  close();
  return result;
}

/** Les séances nommées par un conflit (la séance, ou les deux d'un chevauchement). */
export function entriesOf(issue: Issue): string[] {
  const values = issue.values as { entries?: string[] };
  return [...(issue.entry ? [issue.entry] : []), ...(values.entries ?? [])];
}

const SMALL_WORDS = new Set(
  [
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "l",
    "d",
    "et",
    "à",
    "au",
    "aux",
    "en",
    "pour",
    "sur",
  ].concat(["of", "the", "and", "for", "to"]),
);

const wordsOf = (name: string) =>
  name
    .split(/[\s'’/,-]+/)
    .map((word) => word.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter((word) => word && !SMALL_WORDS.has(word.toLowerCase()));

/** Noms courts de l'horaire général (« Math », « Phys », « DesÉ » pour Dessin électrique) : un
 *  mot → ses 4 premières lettres ; plusieurs → 3 lettres du premier et l'initiale des suivants
 *  (2 au plus). Deux cours d'une même classe ne gardent pas le même nom court : le mot qui les
 *  distingue s'allonge (« Électri », « Électro »). Un nom de cours a le même nom court partout. */
export function shortNames(courses: EditorCourse[]): Map<string, string> {
  const words = new Map(courses.map((course) => [course.name, wordsOf(course.name).slice(0, 3)]));
  const sizes = new Map(
    [...words].map(([name, list]) => [
      name,
      list.map((_, i): number => (i ? 1 : list.length > 1 ? 3 : 4)),
    ]),
  );
  const code = (name: string) => {
    const list = words.get(name) ?? [];
    if (!list.length) return name.slice(0, 4);
    return list
      .map((word, i) => {
        const part = word.slice(0, sizes.get(name)?.[i]);
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join("");
  };
  const together = new Map<string, Set<string>>();
  for (const course of courses) {
    together.set(
      course.class_group,
      (together.get(course.class_group) ?? new Set()).add(course.name),
    );
  }
  for (let round = 0; round < 8; round += 1) {
    let longer = false;
    for (const names of together.values()) {
      const byCode = new Map<string, string[]>();
      for (const name of names) byCode.set(code(name), [...(byCode.get(code(name)) ?? []), name]);
      for (const same of byCode.values()) {
        for (const name of same.length > 1 ? same : []) {
          const mine = words.get(name) ?? [];
          const other = words.get(same.find((item) => item !== name) ?? "") ?? [];
          const at = Math.max(
            0,
            mine.findIndex((word, i) => word.toLowerCase() !== other[i]?.toLowerCase()),
          );
          const size = sizes.get(name) ?? [];
          if ((size[at] ?? 0) < (mine[at]?.length ?? 0)) {
            size[at] = (size[at] ?? 0) + 1;
            longer = true;
          }
        }
      }
    }
    if (!longer) break;
  }
  return new Map(courses.map((course) => [course.id, code(course.name)]));
}

/** Couleur d'un cours : la même dans toutes les vues (jetons `--color-course-1` à `-10`). */
export const COURSE_COLORS = 10;

export function colorOf(courseName: string): string {
  let hash = 0;
  for (const char of courseName.toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return `var(--color-course-${(hash % COURSE_COLORS) + 1})`;
}

/** Un geste de l'éditeur : une requête, qui renvoie l'état du brouillon. */
export type Gesture =
  | { kind: "place"; course: string; weekday: number; first: number; length: number }
  | { kind: "move"; entry: string; weekday: number; first: number }
  | { kind: "swap"; entry: string; other: string }
  | { kind: "room"; entry: string; room: string | null }
  | { kind: "lock"; entry: string; locked: boolean }
  | { kind: "remove"; entry: string }
  | { kind: "undo" };
