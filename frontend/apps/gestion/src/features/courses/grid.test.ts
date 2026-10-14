import { describe, expect, it } from "vitest";

import { gridSummary, termCounts } from "./grid";

const secondary = [1, 2].map(() => ({
  kind: "semester",
  children: [{ kind: "period" }, { kind: "period" }, { kind: "exam" }],
}));
const row = (period_max: number, has_exam = true) => ({
  period_max,
  has_exam,
  weekly_hours: 2,
  teacher_id: null,
});

describe("grille de cours (8.1)", () => {
  it("formulaire IGE/P.S/100 : 710 par période, 1 020 aux examens, 4 880 sur l'année", () => {
    const rows = [
      ...[10, 10, 10].map((max) => row(max)),
      ...Array.from({ length: 9 }, () => row(20)),
      ...Array.from({ length: 5 }, () => row(40)),
      row(50),
      row(50),
      row(100, false),
      row(100, false),
    ];
    const summary = gridSummary(rows, termCounts(secondary));
    expect([summary.period, summary.exam, summary.year]).toEqual([710, 1020, 4880]);
    expect(summary.groups.map(({ max, hasExam, count }) => [max, hasExam, count])).toEqual([
      [10, true, 3],
      [20, true, 9],
      [40, true, 5],
      [50, true, 2],
      [100, false, 2],
    ]);
  });

  it("le T.G. suit le découpage : 3 trimestres (6 périodes, 3 examens) → 12 × le maximum", () => {
    const trimesters = [1, 2, 3].map(() => ({
      kind: "trimester",
      children: [{ kind: "period" }, { kind: "period" }, { kind: "exam" }],
    }));
    expect(gridSummary([row(20), row(100, false)], termCounts(trimesters)).year).toBe(240 + 600);
  });
});
