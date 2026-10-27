import { describe, expect, it } from "vitest";

import { patternProblem, proposedPattern } from "../courses/placement";
import { describe as summary, isBlocked, toggleDay, toggleLesson } from "./availability";

const first = { start: "07:30:00", end: "08:20:00" };
const second = { start: "08:20:00", end: "09:10:00" };
const third = { start: "09:10:00", end: "10:00:00" };
const monday = [first, second, third];

describe("absences d'un enseignant", () => {
  it("une plage bloque les heures qu'elle chevauche, un jour entier toutes", () => {
    const list = [{ weekday: 2, start: "07:30", end: "09:00" }, { weekday: 5 }];
    expect(isBlocked(list, 2, second)).toBe(true);
    expect(isBlocked(list, 2, third)).toBe(false);
    expect(isBlocked(list, 5, third)).toBe(true);
  });

  it("une heure se marque et se libère ; dans un jour entier, elle seule redevient libre", () => {
    const one = toggleLesson([], 1, first, monday);
    expect(one).toEqual([{ weekday: 1, start: "07:30", end: "08:20" }]);
    expect(toggleLesson(one, 1, first, monday)).toEqual([]);
    const day = toggleDay([], 1);
    expect(toggleLesson(day, 1, second, monday)).toEqual([
      { weekday: 1, start: "07:30", end: "08:20" },
      { weekday: 1, start: "09:10", end: "10:00" },
    ]);
    expect(toggleDay(day, 1)).toEqual([]);
  });

  it("le résumé réunit les plages qui se suivent", () => {
    const list = [
      { weekday: 2, start: "08:20", end: "09:10" },
      { weekday: 2, start: "07:30", end: "08:20" },
      { weekday: 5 },
    ];
    expect(summary(list, (day) => `j${day}`)).toEqual(["j2 07:30–09:10", "j5"]);
  });
});

describe("séances d'un cours", () => {
  it("proposées : des blocs de 2 h à partir de 4 h", () => {
    expect([1, 3, 4, 5, 6].map((hours) => proposedPattern(hours))).toEqual([
      "1",
      "1+1+1",
      "2+2",
      "2+2+1",
      "2+2+2",
    ]);
    // Un atelier : des blocs de 4 h au plus, à parts égales.
    expect([3, 4, 7, 8, 9].map((hours) => proposedPattern(hours, true))).toEqual([
      "3",
      "4",
      "4+3",
      "4+4",
      "3+3+3",
    ]);
  });

  it("refusées avant l'envoi si elles ne font pas les heures", () => {
    expect(patternProblem("2+2", 5)).toEqual({ key: "hours", sum: 4 });
    expect(patternProblem("2,3", 5)).toEqual({ key: "bad" });
    expect(patternProblem(" 2 + 3 ", 5)).toBeNull();
    expect(patternProblem("", 5)).toBeNull();
  });
});
