import { setupI18n } from "@mwangaza/i18n";
import { describe, expect, it } from "vitest";

import { blockingReason, timeChoices, unmetReason } from "./calculation";

const t = setupI18n("fr").getFixedT("fr");
const rule = (id: string) =>
  id === "r1" ? { subject: "Atelier · 2HT", text: "Verrouillé le lundi" } : undefined;
const reason = (row: Record<string, unknown>) =>
  blockingReason({ subject: "", ...row } as never, "d1", rule, t);

describe("règles qui bloquent un calcul", () => {
  it("dit chaque règle en phrase, chiffres compris, avec l'écran qui la corrige", () => {
    const absence = reason({
      code: "absence",
      subject: "Mumbere Paluku",
      values: { due: 26, available: 24 },
    });
    expect(absence.text).toMatch(/26 h.*24 h/);
    expect(absence.fix).toEqual({ to: "/teaching-loads", label: "teacher" });
    const course = reason({ code: "course_day", class_group: "c1", values: { max: 1, hours: 5 } });
    expect(course.text).toMatch(/5 h.*1 h par jour/);
    expect(course.fix?.to).toBe("/courses?class=c1");
    expect(reason({ code: "locks", class_group: "c1" }).fix?.to).toBe(
      "/timetable?draft=d1&class=c1",
    );
    expect(reason({ code: "frozen" }).fix).toEqual({ to: null, label: "all" });

    const locked = reason({ code: "rule", rule: "r1", subject: "Heure verrouillée" });
    expect([locked.subject, locked.fix?.to]).toEqual([
      "Atelier · 2HT",
      "/timetable-checks?rule=r1",
    ]);
    expect(locked.text).toContain("Verrouillé le lundi");
    // Règle supprimée depuis : son type, sans phrase.
    expect(reason({ code: "rule", rule: "r2", subject: "Heure verrouillée" }).subject).toBe(
      "Heure verrouillée",
    );
    // Chaque code connu a sa phrase (jamais une clé brute).
    for (const code of ["teacher_day", "unit", "no_gaps", "locks", "frozen", "other"]) {
      expect(reason({ code }).text).not.toContain("timetable.");
    }
  });

  it("dit les souhaits non tenus et propose les temps permis à l'école", () => {
    expect(unmetReason({ code: "rule", rule: "r1", count: 3 }, rule, t).text).toBe(
      "Verrouillé le lundi",
    );
    expect(unmetReason({ code: "moved", count: 5 } as never, rule, t).subject).not.toContain(
      "timetable.",
    );
    expect(timeChoices(60)).toEqual([30, 60]);
    expect(timeChoices(180)).toEqual([30, 60, 120, 180]);
    expect(timeChoices(45)).toEqual([30, 45]);
  });
});
