import { describe, expect, it } from "vitest";

import { everyMonth } from "./schedule";

describe("everyMonth", () => {
  it("garde le total exact et le jour choisi, ramené à la fin des mois courts", () => {
    const lines = everyMonth(100000, 3, "2026-12-31", (n) => `Versement ${n}`);
    expect(lines).toEqual([
      { label: "Versement 1", amount_minor: 33334, due_on: "2026-12-31" },
      { label: "Versement 2", amount_minor: 33333, due_on: "2027-01-31" },
      { label: "Versement 3", amount_minor: 33333, due_on: "2027-02-28" },
    ]);
  });
});
