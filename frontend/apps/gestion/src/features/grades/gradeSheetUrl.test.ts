import { describe, expect, it } from "vitest";

import { DEFAULT_LAYOUT } from "../printing/printOptions";
import { gradeSheetUrl } from "./data";

const base = { output: "html" as const, layout: DEFAULT_LAYOUT, columns: ["matricule"] };

describe("gradeSheetUrl", () => {
  it("garde le cours, les colonnes et le papier pour la fiche d'un cours", () => {
    const url = gradeSheetUrl("g1", { ...base, kind: "course", course: "c1", blankColumns: 8 });
    expect(url).toBe(
      "/api/class-groups/g1/grade-sheet/?kind=course&output=html&course=c1&columns=matricule&paper=a4",
    );
  });

  it("n'envoie la colonne que pour le tableau de la classe et le nombre de colonnes vides que pour la fiche vierge", () => {
    const table = gradeSheetUrl("g1", { ...base, kind: "class", column: "", blankColumns: 8 });
    expect(table).toContain("column=year");
    expect(table).not.toContain("course=");
    expect(table).not.toContain("blank_columns");
    const blank = gradeSheetUrl("g1", { ...base, kind: "blank", course: "c1", blankColumns: 12 });
    expect(blank).toContain("blank_columns=12");
  });
});
