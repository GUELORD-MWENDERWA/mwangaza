import { setupI18n } from "@mwangaza/i18n";
import { describe, expect, it } from "vitest";

import { snapshotTree, termLabels, type TermShape } from "./terms";

const i18n = setupI18n("fr");
const t = i18n.getFixedT("fr");
const tEn = i18n.getFixedT("en");

const group = (kind: "semester" | "trimester", name = ""): TermShape => ({
  kind,
  name,
  children: [
    { kind: "period", name: "" },
    { kind: "period", name: "" },
    { kind: "exam", name: "" },
  ],
});

function names(nodes: TermShape[], translate = t) {
  const labels = termLabels(nodes, translate);
  return nodes.flatMap((node) => [
    labels.get(node),
    ...(node.children ?? []).map((child) => labels.get(child)),
  ]);
}

describe("noms du découpage", () => {
  it("secondaire : comme la maquette", () => {
    expect(names([group("semester"), group("semester")])).toEqual([
      "Semestre 1",
      "1re période",
      "2e période",
      "Examens du 1er semestre",
      "Semestre 2",
      "3e période",
      "4e période",
      "Examens du 2e semestre",
    ]);
  });

  it("trimestres, en anglais", () => {
    expect(names([group("trimester"), group("trimester")], tEn)).toEqual([
      "Term 1",
      "Period 1",
      "Period 2",
      "Term 1 exams",
      "Term 2",
      "Period 3",
      "Period 4",
      "Term 2 exams",
    ]);
  });

  it("un nom donné par l'école garde la place des autres", () => {
    const nodes = [group("semester", "Premier semestre"), { kind: "exam" as const, name: "" }];
    nodes[0]!.children![0]!.name = "P1";

    expect(names(nodes)).toEqual([
      "Premier semestre",
      "P1",
      "2e période",
      "Examens du 1er semestre",
      "Examens",
    ]);
  });

  it("journal : liste à plat → arbre", () => {
    const tree = snapshotTree([
      { kind: "semester", name: "", parent: null },
      { kind: "period", name: "", parent: 0 },
      { kind: "exam", name: "", parent: 0 },
      { kind: "period", name: "Rattrapage", parent: null },
    ]);

    expect(tree.map((node) => node.index)).toEqual([0, 3]);
    expect(names(tree)).toEqual([
      "Semestre 1",
      "1re période",
      "Examens du 1er semestre",
      "Rattrapage",
    ]);
  });
});
