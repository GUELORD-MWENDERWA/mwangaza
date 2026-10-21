// Éditeur de l'horaire (EDT.2a, maquette `emploi-du-temps-classe`) : calculs de l'écran sur l'état
// d'un brouillon. Le serveur reste juge des conflits (il les renvoie après chaque geste) ; l'écran
// ne fait que placer les séances dans la grille de la classe et teinter les cases pendant le choix
// d'une heure (vert : possible, rouge : classe, enseignant ou salle déjà pris, gris : ne tient pas).
import type { Schemas } from "@mwangaza/api";

import type { ClassRow, Room, TimeGrid } from "./data";
import { toMinutes } from "./week";

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

/** Ce que l'écran sait d'un brouillon : cours, classes, grilles, salles. */
export type Board = {
  courses: Map<string, EditorCourse>;
  classes: Map<string, ClassRow>;
  rooms: Map<string, Room>;
  daysOfClass: (classId: string) => Days;
};

export function boardOf(
  courses: EditorCourse[],
  classes: ClassRow[],
  grids: TimeGrid[],
  rooms: Room[],
): Board {
  const byGrid = new Map(grids.map((grid) => [grid.id, daysOf(grid)]));
  const fallback = daysOf(grids.find((grid) => grid.is_default));
  const classMap = new Map(classes.map((row) => [row.id, row]));
  return {
    courses: new Map(courses.map((course) => [course.id, course])),
    classes: classMap,
    rooms: new Map(rooms.map((room) => [room.id, room])),
    daysOfClass: (classId) => {
      const grid = classMap.get(classId)?.time_grid;
      return (grid && byGrid.get(grid)) || fallback;
    },
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
  return { kind: "fits" };
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
