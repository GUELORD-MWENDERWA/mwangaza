// Éditeur de l'horaire (EDT.2a, EDT.2b) : teinte des cases pendant le choix d'une heure, vues par
// enseignant et par salle, noms courts de l'horaire général. Le serveur reste juge ; l'écran ne doit
// pas dire « possible » là où la classe, l'enseignant ou la salle est déjà pris, ni où l'enseignant
// est absent, même quand deux classes suivent des grilles différentes (deux vacations).
import { describe, expect, it } from "vitest";

import type { ClassRow, Room, TeacherProfile, TimeGrid } from "./data";
import {
  type DraftState,
  type EditorCourse,
  type Entry,
  boardOf,
  focusOf,
  lanesOf,
  placedOf,
  rowsOf,
  shortNames,
  tint,
} from "./editor";

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

describe("vues par enseignant et par salle, noms courts", () => {
  // t1 est absent le lundi à partir de 09:00.
  const profiles = [
    { teacher: "t1", unavailable: [{ weekday: 1, start: "09:00", end: "12:00" }] },
  ] as unknown as TeacherProfile[];
  const board = boardOf(courses, classes, grids, rooms, profiles);

  it("une heure où l'enseignant est absent se teinte en rouge", () => {
    const maths = { course: courses[0]!, length: 1, room: null };
    expect(tint(board, [], maths, 1, 1)).toEqual({ kind: "fits" });
    expect(tint(board, [], maths, 1, 3)).toEqual({ kind: "absent", teacher: "t1" });
  });

  it("séances, reste à placer et conflits d'un enseignant ; grilles mélangées signalées", () => {
    const state = {
      entries: [entry("m", "maths", 1, 1, "r1"), entry("f", "french", 2, 1, "r1")],
      left: [{ course: "physics", lengths: [2] }],
      issues: [
        { code: "same_room", entry: "f", values: { entries: ["m"] }, teacher: null, room: "r1" },
        { code: "class_gap", entry: null, values: {}, class_group: "a", teacher: null },
      ],
    } as unknown as DraftState;
    const mine = focusOf(board, state, "teacher", "t1");
    expect(mine.entries.map((item) => item.id)).toEqual(["m"]);
    expect(mine.left.map((item) => item.course.id)).toEqual(["physics"]);
    expect(mine.issues.map((issue) => issue.code)).toEqual(["same_room"]);
    // Maths en 1A (grille du matin), physique en 1B (grille décalée).
    expect(mine.mixed).toBe(true);
    // La salle 1 : les deux séances ; « À placer » : la physique n'y va pas (salle de la 1B : r2).
    const room = focusOf(board, state, "room", "r1");
    expect(room.entries.map((item) => item.id)).toEqual(["m", "f"]);
    expect(room.left).toEqual([]);
    expect(focusOf(board, state, "class", "a").issues).toHaveLength(2);
  });

  it("noms courts distincts dans une classe, les mêmes partout ailleurs", () => {
    const named = (id: string, name: string, group: string) =>
      ({ ...course(id, group, null), name }) as EditorCourse;
    const codes = shortNames([
      named("1", "Mathématiques", "a"),
      named("2", "Éducation civique et morale", "a"),
      named("3", "Électricité", "a"),
      named("4", "Électronique", "a"),
      named("5", "Électronique", "b"),
      named("6", "Technologie électrique", "b"),
      named("7", "Technologie électronique", "b"),
      named("8", "H.G.A.", "b"),
    ]);
    expect([...codes.values()]).toEqual([
      "Math",
      "ÉduCM",
      "Électri",
      "Électro",
      "Électro",
      "TecÉlectri",
      "TecÉlectro",
      "HGA",
    ]);
  });
});
