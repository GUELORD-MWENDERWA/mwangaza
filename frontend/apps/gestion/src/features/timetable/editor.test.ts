// Éditeur de l'horaire (EDT.2a) : teinte des cases pendant le choix d'une heure. Le serveur reste
// juge ; l'écran ne doit pas dire « possible » là où la classe, l'enseignant ou la salle est déjà
// pris, même quand deux classes suivent des grilles différentes (deux vacations).
import { describe, expect, it } from "vitest";

import type { ClassRow, Room, TimeGrid } from "./data";
import { type EditorCourse, type Entry, boardOf, lanesOf, placedOf, rowsOf, tint } from "./editor";

const slot = (weekday: number, index: number | null, start: string, end: string) => ({
  id: `${weekday}-${start}`,
  weekday,
  index,
  kind: index ? ("lesson" as const) : ("break" as const),
  start,
  end,
});
// Grille du matin : 3 heures, récréation, 1 heure ; grille décalée de 25 minutes.
const morning = [
  slot(1, 1, "07:30", "08:20"),
  slot(1, 2, "08:20", "09:10"),
  slot(1, 3, "09:10", "10:00"),
  slot(1, null, "10:00", "10:15"),
  slot(1, 4, "10:15", "11:05"),
];
const late = [slot(1, 1, "07:55", "08:45"), slot(1, 2, "08:45", "09:35")];
const grids = [
  { id: "g1", name: "Matin", is_default: true, slots: morning },
  { id: "g2", name: "Décalée", is_default: false, slots: late },
] as unknown as TimeGrid[];
const classes = [
  { id: "a", name: "1A", time_grid: null, home_room: "r1" },
  { id: "b", name: "1B", time_grid: "g2", home_room: "r2" },
] as unknown as ClassRow[];
const rooms = [
  { id: "r1", name: "Salle 1", kind: "classroom" },
  { id: "r2", name: "Salle 2", kind: "classroom" },
  { id: "sport", name: "Terrain", kind: "sports" },
] as unknown as Room[];
const course = (id: string, group: string, teacher: string | null, spans = false) =>
  ({
    id,
    name: id,
    class_group: group,
    teacher,
    teacher_name: teacher ?? "",
    room: null,
    room_kind: "",
    spans_break: spans,
    sessions: [2],
    max_per_day: 2,
    category: "main",
  }) as EditorCourse;
const courses = [
  course("maths", "a", "t1"),
  course("french", "a", "t2"),
  course("physics", "b", "t1"),
  course("workshop", "a", "t3", true),
];
const entry = (
  id: string,
  courseId: string,
  first: number,
  length: number,
  room: string | null = null,
) => ({ id, course: courseId, weekday: 1, first, length, room, locked: false }) as Entry;

describe("teinte des cases de l'éditeur", () => {
  const board = boardOf(courses, classes, grids, rooms);

  it("classe, enseignant (autre grille) et salle déjà pris ; séance qui ne tient pas", () => {
    // 1B (grille décalée) : physique avec t1 de 07:55 à 09:35.
    const placed = placedOf(board, [entry("p", "physics", 1, 2, "r1"), entry("f", "french", 3, 1)]);
    const maths = { course: courses[0]!, length: 1, room: "r1" };
    // 1re heure de la 1A (07:30-08:20) chevauche la physique de t1 : rouge, à cause de l'enseignant.
    expect(tint(board, placed, maths, 1, 1)).toMatchObject({ kind: "conflict", reason: "teacher" });
    // 3e heure : la 1A a déjà le français.
    expect(tint(board, placed, maths, 1, 3)).toMatchObject({ kind: "conflict", reason: "class" });
    // 4e heure : libre.
    expect(tint(board, placed, maths, 1, 4)).toEqual({ kind: "fits" });
    // Sans t1, la salle 1 reste prise par la physique ; le terrain de sport en reçoit plusieurs.
    const other = { course: courses[1]!, length: 1, room: "r1" };
    expect(tint(board, placed, other, 1, 2)).toMatchObject({ kind: "conflict", reason: "room" });
    expect(tint(board, placed, { ...other, room: "sport" }, 1, 2)).toEqual({ kind: "fits" });
    // 2 h à partir de la 3e : passe la récréation, interdit pour les maths, permis à l'atelier.
    expect(tint(board, [], { ...maths, length: 2 }, 1, 3)).toEqual({ kind: "short" });
    expect(tint(board, [], { course: courses[3]!, length: 2, room: null }, 1, 3)).toEqual({
      kind: "fits",
    });
    // La séance qu'on déplace ne se gêne pas elle-même.
    expect(tint(board, placed, { ...other, room: null }, 1, 3, ["f"])).toEqual({ kind: "fits" });
  });

  it("lignes de la grille et séances en même temps côte à côte", () => {
    expect(rowsOf(board.daysOfClass("a")).map((row) => row.key)).toEqual([
      "L1",
      "L2",
      "L3",
      "B3",
      "L4",
    ]);
    const lanes = lanesOf([
      entry("x", "maths", 1, 2),
      entry("y", "french", 2, 1),
      entry("z", "maths", 4, 1),
    ]);
    expect([lanes.get("x"), lanes.get("y"), lanes.get("z")]).toEqual([
      { lane: 0, lanes: 2 },
      { lane: 1, lanes: 2 },
      { lane: 0, lanes: 1 },
    ]);
  });
});
