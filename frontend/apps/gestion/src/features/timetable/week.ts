// Semaine d'une grille horaire (EDT.1a, maquette `grille-horaire`) : chaque jour est une suite de
// cases (heures de cours et récréations) qui se suivent sans trou, à partir de l'heure de début du
// jour. Changer la durée d'une case décale les suivantes. Calculs en minutes depuis minuit ; le
// serveur vérifie de nouveau tout (`timetable/services.py:check_slots`).
import type { Schemas } from "@mwangaza/api";

export type SlotKind = Schemas["TimeSlotKindEnum"];
export type Slot = Pick<Schemas["TimeSlot"], "weekday" | "kind" | "start" | "end">;
export type SlotInput = Schemas["TimeSlotInputRequest"];
export type Item = { kind: SlotKind; minutes: number };
export type Day = { start: number; items: Item[] };
/** Jours de cours seulement (1 = lundi … 7 = dimanche). */
export type Week = Partial<Record<number, Day>>;
export type Break = { after: number; minutes: number };
export type Shape = {
  lessonMinutes: number;
  start: number;
  lessons: Record<number, number>;
  breaks: Break[];
};

export const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7] as const;
export const MAX_LESSONS_PER_DAY = 12;

export function toMinutes(clock: string): number {
  const [hours = "0", minutes = "0"] = clock.split(":");
  return Number(hours) * 60 + Number(minutes);
}

export function toClock(total: number): string {
  const hours = Math.floor(total / 60);
  return `${String(hours).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function fromSlots(slots: Slot[]): Week {
  const week: Week = {};
  const sorted = [...slots].sort(
    (a, b) => a.weekday - b.weekday || toMinutes(a.start) - toMinutes(b.start),
  );
  for (const slot of sorted) {
    const day = (week[slot.weekday] ??= { start: toMinutes(slot.start), items: [] });
    day.items.push({ kind: slot.kind, minutes: toMinutes(slot.end) - toMinutes(slot.start) });
  }
  return week;
}

/** Réglages qui redonnent cette semaine : heures par jour, et récréations du premier jour. */
export function shapeOf(week: Week, lessonMinutes: number, start: number): Shape {
  const lessons: Record<number, number> = {};
  for (const weekday of WEEKDAYS) {
    lessons[weekday] = week[weekday]?.items.filter((item) => item.kind === "lesson").length ?? 0;
  }
  const first = WEEKDAYS.map((weekday) => week[weekday]).find(Boolean);
  const breaks: Break[] = [];
  let count = 0;
  for (const item of first?.items ?? []) {
    if (item.kind === "lesson") count += 1;
    else breaks.push({ after: count, minutes: item.minutes });
  }
  return { lessonMinutes, start, lessons, breaks };
}

/** Semaine recalculée : chaque jour commence au début, une récréation suit la Ne heure s'il y a
 *  une heure après elle. */
export function buildWeek(shape: Shape): Week {
  const week: Week = {};
  for (const weekday of WEEKDAYS) {
    const count = Math.min(shape.lessons[weekday] ?? 0, MAX_LESSONS_PER_DAY);
    if (count === 0) continue;
    const items: Item[] = [];
    for (let index = 1; index <= count; index += 1) {
      items.push({ kind: "lesson", minutes: shape.lessonMinutes });
      const pause = shape.breaks.find((item) => item.after === index);
      if (pause && index < count) items.push({ kind: "break", minutes: pause.minutes });
    }
    week[weekday] = { start: shape.start, items };
  }
  return week;
}

export function setMinutes(week: Week, weekday: number, position: number, minutes: number): Week {
  const day = week[weekday];
  if (!day) return week;
  const items = day.items.map((item, at) => (at === position ? { ...item, minutes } : item));
  return { ...week, [weekday]: { ...day, items } };
}

export function setDayStart(week: Week, weekday: number, start: number): Week {
  const day = week[weekday];
  return day ? { ...week, [weekday]: { ...day, start } } : week;
}

/** Une case du jour, avec son numéro d'heure (vide pour une récréation) et ses horaires. */
export type Cell = {
  position: number;
  kind: SlotKind;
  index: number | null;
  start: number;
  end: number;
};

export function cellsOf(day: Day): Cell[] {
  const cells: Cell[] = [];
  let moment = day.start;
  let lessons = 0;
  day.items.forEach((item, position) => {
    if (item.kind === "lesson") lessons += 1;
    const index = item.kind === "lesson" ? lessons : null;
    cells.push({ position, kind: item.kind, index, start: moment, end: moment + item.minutes });
    moment += item.minutes;
  });
  return cells;
}

export function toSlots(week: Week): SlotInput[] {
  return WEEKDAYS.flatMap((weekday) => {
    const day = week[weekday];
    if (!day) return [];
    return cellsOf(day).map((cell) => ({
      weekday,
      kind: cell.kind,
      index: cell.index,
      start: toClock(cell.start),
      end: toClock(cell.end),
    }));
  });
}

export function lessonCount(week: Week): number {
  return WEEKDAYS.reduce(
    (total, weekday) =>
      total + (week[weekday]?.items.filter((item) => item.kind === "lesson").length ?? 0),
    0,
  );
}

/** Lignes du tableau de la semaine : « 1re heure », puis « récréation après la 1re heure »
 *  seulement si un jour en a une, etc. Clé : `L<n>` ou `B<n>`. */
export function rowKeys(week: Week): string[] {
  const present = new Set<string>();
  let most = 0;
  for (const weekday of WEEKDAYS) {
    const day = week[weekday];
    if (!day) continue;
    for (const cell of cellsOf(day)) {
      if (cell.index !== null) most = Math.max(most, cell.index);
      present.add(cellKey(day, cell));
    }
  }
  const keys: string[] = [];
  for (let index = 1; index <= most; index += 1) {
    keys.push(`L${index}`);
    if (present.has(`B${index}`)) keys.push(`B${index}`);
  }
  return keys;
}

/** Clé de la ligne d'une case : `L3` pour la 3e heure, `B3` pour la récréation qui la suit. */
export function cellKey(day: Day, cell: Cell): string {
  if (cell.index !== null) return `L${cell.index}`;
  const before = cellsOf(day)
    .slice(0, cell.position)
    .filter((item) => item.index !== null).length;
  return `B${before}`;
}
