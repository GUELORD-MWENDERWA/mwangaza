import { describe, expect, it } from "vitest";

import {
  buildWeek,
  fromSlots,
  lessonCount,
  rowKeys,
  setMinutes,
  shapeOf,
  toMinutes,
  toSlots,
} from "./week";

// Grille proposée (Q16) : 50 min dès 07:30, 7 heures du lundi au vendredi, 4 le samedi.
const proposed = buildWeek({
  lessonMinutes: 50,
  start: toMinutes("07:30"),
  lessons: { 1: 7, 2: 7, 3: 7, 4: 7, 5: 7, 6: 4 },
  breaks: [
    { after: 3, minutes: 15 },
    { after: 5, minutes: 10 },
  ],
});

describe("semaine d'une grille horaire", () => {
  it("calcule les heures, les récréations entre deux heures et la capacité", () => {
    expect(lessonCount(proposed)).toBe(39);
    const monday = toSlots(proposed).filter((slot) => slot.weekday === 1);
    expect(monday.at(3)).toMatchObject({ kind: "break", start: "10:00", end: "10:15" });
    expect(monday.at(-1)).toMatchObject({ index: 7, start: "12:55", end: "13:45" });
    // Samedi : la récréation d'après la 5e heure n'existe pas.
    expect(
      toSlots(proposed)
        .filter((slot) => slot.weekday === 6)
        .map((s) => s.kind),
    ).toEqual(["lesson", "lesson", "lesson", "break", "lesson"]);
    expect(rowKeys(proposed)).toEqual(["L1", "L2", "L3", "B3", "L4", "L5", "B5", "L6", "L7"]);
  });

  it("une récréation plus longue décale la suite du jour seulement", () => {
    const week = setMinutes(proposed, 5, 3, 30);
    const friday = toSlots(week).filter((slot) => slot.weekday === 5);
    expect(friday.at(4)).toMatchObject({ index: 4, start: "10:30", end: "11:20" });
    expect(
      toSlots(week)
        .filter((slot) => slot.weekday === 4)
        .at(4)?.start,
    ).toBe("10:15");
  });

  it("relit la semaine enregistrée et en retrouve les réglages", () => {
    const back = fromSlots(
      toSlots(proposed).map((slot) => ({ ...slot, start: `${slot.start}:00`, end: slot.end })),
    );
    expect(toSlots(back)).toEqual(toSlots(proposed));
    const shape = shapeOf(back, 50, toMinutes("07:30"));
    expect(shape.lessons).toMatchObject({ 1: 7, 6: 4, 7: 0 });
    expect(shape.breaks).toEqual([
      { after: 3, minutes: 15 },
      { after: 5, minutes: 10 },
    ]);
  });
});
