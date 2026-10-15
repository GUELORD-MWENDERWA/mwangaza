import { describe, expect, it } from "vitest";

import type { Sheet } from "./data";
import { applySave, parseTenths, percent, periodTenths, serverTenths, toScore } from "./sheet";

describe("feuille de notes", () => {
  it("lit une note à une décimale, jamais au-dessus du maximum", () => {
    expect(parseTenths("7,5", 10)).toBe(75);
    expect(parseTenths(" 8 ", 10)).toBe(80);
    expect(parseTenths("", 10)).toBeNull();
    expect(parseTenths("10.5", 10)).toBeUndefined();
    expect(parseTenths("7,25", 10)).toBeUndefined();
    expect(parseTenths("-1", 10)).toBeUndefined();
    expect(toScore(75)).toBe("7.5");
    expect(serverTenths("18.0")).toBe(180);
  });

  it("ramène la somme au maximum de la période, au dixième, comme le serveur", () => {
    expect(periodTenths([80, 90, 140], [10, 10, 20], 20)).toBe(155);
    expect(periodTenths([100], [30], 20)).toBe(67);
    // La moitié vers le haut : 1 / 80 × 20 = 0,25.
    expect(periodTenths([10], [80], 20)).toBe(3);
    expect(periodTenths([80, null], [10, 10], 20)).toBeNull();
    expect(periodTenths([], [], 20)).toBeNull();
    expect(percent(155, 20)).toBe(78);
    expect(percent(90, 20)).toBe(45);
  });

  it("montre sur l'appareil la feuille telle que le serveur la rendra (8.2.3)", () => {
    const sheet = {
      maximum: 20,
      evaluations: [{ id: "e1", name: "Interro", max_score: 20 }],
      students: [
        { enrollment_id: "a", scores: [{ evaluation_id: "e1", score: "12.0" }], total: "12.0" },
        { enrollment_id: "b", scores: [], total: null },
      ],
    } as unknown as Sheet;
    const saved = applySave(sheet, {
      evaluations: [
        { id: "e1", name: "Interro", max_score: 20 },
        { id: "e2", name: "Devoir", max_score: 10 },
      ],
      removed_evaluations: [],
      grades: [
        { enrollment_id: "a", evaluation_id: "e2", score: "7.5" },
        { enrollment_id: "b", evaluation_id: "e1", score: "9.0" },
        { enrollment_id: "b", evaluation_id: "e2", score: "10.0" },
      ],
      reason: "",
    });
    // 12 + 7,5 sur 30 → 13 sur 20 (13,0 : 19,5 × 20 / 30) ; l'élève b : 19 sur 30 → 12,7.
    expect(saved.students.map((row) => row.total)).toEqual(["13.0", "12.7"]);
    const cleared = applySave(saved, {
      evaluations: saved.evaluations,
      removed_evaluations: ["e2"],
      grades: [{ enrollment_id: "a", evaluation_id: "e1", score: null }],
      reason: "",
    });
    expect(cleared.evaluations.map((item) => item.id)).toEqual(["e1"]);
    expect(cleared.students.map((row) => [row.scores.length, row.total])).toEqual([
      [0, null],
      [1, "9.0"],
    ]);
  });
});
