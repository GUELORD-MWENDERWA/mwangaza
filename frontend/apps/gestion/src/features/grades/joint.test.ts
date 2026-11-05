import { describe, expect, it } from "vitest";

import type { Sheet } from "./data";
import {
  buildBodies,
  cellKey,
  type Column,
  InvalidCell,
  mergeColumns,
  minter,
  type Part,
  withMax,
} from "./joint";

const sheet = (
  maximum: number,
  evaluations: [string, string, number][],
  students: [string, [string, string][]][],
) =>
  ({
    maximum,
    status: "draft",
    evaluations: evaluations.map(([id, name, max_score]) => ({ id, name, max_score })),
    students: students.map(([enrollment_id, scores]) => ({
      enrollment_id,
      scores: scores.map(([evaluation_id, score]) => ({ evaluation_id, score })),
    })),
  }) as unknown as Sheet;

// Mathématiques commun à trois classes : A (/40) et B (/30) modifiables, C déjà validée.
const parts: Part[] = [
  {
    course: "math-a",
    className: "4HT A",
    locked: false,
    sheet: sheet(40, [["a1", "Interrogation 1", 10]], [["eleve-a", [["a1", "8.0"]]]]),
  },
  {
    course: "math-b",
    className: "4HT B",
    locked: false,
    sheet: sheet(
      30,
      [
        ["b1", "interrogation 1 ", 10],
        ["b2", "Devoir", 20],
      ],
      [["eleve-b", [["b1", "9.0"]]]],
    ),
  },
  {
    course: "math-c",
    className: "4HT C",
    locked: true,
    sheet: sheet(40, [["c1", "Interrogation 1", 10]], [["eleve-c", [["c1", "5.0"]]]]),
  },
];

const ids = (() => {
  let n = 0;
  return () => `neuve-${++n}`;
})();

describe("fiche de cotes commune (8.1.2a)", () => {
  it("réunit les évaluations du même nom et envoie chaque note au cours de sa classe", () => {
    const columns = mergeColumns(parts);
    expect(columns.map((column) => [column.key, column.ids])).toEqual([
      ["a1", { "math-a": "a1", "math-b": "b1", "math-c": "c1" }],
      ["b2", { "math-b": "b2" }],
    ]);
    const bodies = buildBodies({
      parts,
      columns,
      removed: [],
      reason: "",
      mint: minter(ids),
      cells: {
        [cellKey("math-a", "eleve-a", "a1")]: "8", // inchangée : pas envoyée
        [cellKey("math-a", "eleve-a", "b2")]: "15",
        [cellKey("math-b", "eleve-b", "b2")]: "17,5",
        [cellKey("math-c", "eleve-c", "a1")]: "9", // classe validée : rien n'est envoyé
      },
    });
    expect([...bodies.keys()]).toEqual(["math-a", "math-b"]);
    // A n'avait pas le devoir : il y est créé, avec un identifiant à lui.
    const a = bodies.get("math-a")!;
    expect(a.evaluations.map((e) => [e.name, e.max_score])).toEqual([
      ["Interrogation 1", 10],
      ["Devoir", 20],
    ]);
    const devoirA = a.evaluations[1]!.id;
    expect(devoirA).not.toBe("b2");
    expect(a.grades).toEqual([{ enrollment_id: "eleve-a", evaluation_id: devoirA, score: "15.0" }]);
    expect(bodies.get("math-b")!.grades).toEqual([
      { enrollment_id: "eleve-b", evaluation_id: "b2", score: "17.5" },
    ]);
  });

  it("ajoute ou retire une évaluation dans chaque classe modifiable", () => {
    const [interro] = mergeColumns(parts) as [Column];
    const mint = minter(ids);
    const added = withMax(
      { key: "nouvelle", name: "TP", ids: {}, maxima: {} },
      ["math-a", "math-b"],
      20,
      "TP",
    );
    const bodies = buildBodies({
      parts,
      columns: [added],
      removed: [interro],
      cells: {},
      reason: "",
      mint,
    });
    const tp = (course: string) => bodies.get(course)!.evaluations[0]!.id;
    expect(tp("math-a")).toBe("nouvelle");
    expect(tp("math-b")).not.toBe("nouvelle");
    // Le même identifiant revient si l'envoi est repris : pas de deuxième évaluation.
    expect(mint(added, "math-b")).toBe(tp("math-b"));
    expect(bodies.get("math-a")!.removed_evaluations).toEqual(["a1"]);
    expect(bodies.get("math-b")!.removed_evaluations).toEqual(["b1"]);
    expect(bodies.has("math-c")).toBe(false);
  });

  it("refuse une note au-dessus du maximum de l'évaluation", () => {
    expect(() =>
      buildBodies({
        parts,
        columns: mergeColumns(parts),
        removed: [],
        reason: "",
        mint: minter(ids),
        cells: { [cellKey("math-b", "eleve-b", "a1")]: "11" },
      }),
    ).toThrow(InvalidCell);
  });
});
