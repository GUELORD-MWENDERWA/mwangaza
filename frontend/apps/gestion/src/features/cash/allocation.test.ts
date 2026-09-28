import { describe, expect, it } from "vitest";

import { charge } from "../../test/fixtures";
import { allocate, payableTotal } from "./allocation";

const RATE = "2850.000000";
// Dans l'ordre du serveur (date limite) : atelier et motivation en retard, puis minerval.
const workshop = charge(1, "1re tranche", "2026-10-15", {
  fee_type_name: "Frais d'atelier",
  amount_minor: 2000,
  state: "overdue",
});
const motivation = charge(2, "octobre", "2026-10-10", {
  fee_type_name: "Motivation",
  amount_minor: 30000,
  currency: "CDF",
  state: "overdue",
});
const tuition = charge(3, "2e tranche", "2027-01-15", { paid_minor: 5000 });
const paid = charge(4, "1re tranche", "2026-10-01", { paid_minor: 12000, state: "paid" });
const charges = [paid, motivation, workshop, tuition];

const summary = (lines: ReturnType<typeof allocate>) =>
  lines.map((line) => [line.charge.label, line.received, line.amount]);

describe("répartition d'un paiement", () => {
  it("paie d'abord les frais de la devise reçue, les plus anciens, le dernier en partie", () => {
    const lines = allocate(charges, { minor: 5000, currency: "USD" }, RATE);
    // Les francs ne sont pas touchés sans « Convertir » ; le frais soldé est ignoré.
    expect(summary(lines)).toEqual([
      ["1re tranche", 2000, 2000],
      ["2e tranche", 3000, 3000],
    ]);
  });

  it("convertit au taux pour les frais de l'autre devise, sans dépasser leur reste", () => {
    const lines = allocate(charges, { minor: 10000, currency: "USD" }, RATE, {
      convertOthers: true,
    });
    // 30 000 FC ≈ 10,53 $ ; 10,53 $ feraient 30 011 FC : la part s'arrête à 10,52 $.
    expect(summary(lines)).toEqual([
      ["1re tranche", 2000, 2000],
      ["2e tranche", 7000, 7000],
      ["octobre", 1000, 28500],
    ]);
    expect(payableTotal(charges, "USD", RATE, true)).toBe(2000 + 7000 + 1052);
    expect(payableTotal(charges, "CDF", RATE, false)).toBe(30000);
  });

  it("ne paie que les frais cochés et laisse le surplus sans affectation", () => {
    const only = new Set([tuition.id, motivation.id]);
    const lines = allocate(charges, { minor: 60000, currency: "CDF" }, RATE, { only });
    // 7 000 cents = 199 500 FC : tout le reçu va aux deux frais cochés, rien à l'atelier.
    expect(summary(lines)).toEqual([
      ["octobre", 30000, 30000],
      ["2e tranche", 30000, 1053],
    ]);
    const surplus = allocate(charges, { minor: 5000, currency: "USD" }, RATE, {
      only: new Set([workshop.id]),
    });
    expect(5000 - surplus.reduce((total, line) => total + line.received, 0)).toBe(3000);
  });
});
