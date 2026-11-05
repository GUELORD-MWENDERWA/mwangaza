import { describe, expect, it } from "vitest";

import type { LocalEnrollment, QueuedOperation } from "../../lib/sync/db";
import type { Config } from "../../lib/sync/engine";
import { financeOf } from "../cash/offline";
import { deviceCharges, localDuplicates, provisionalMatricule, queuedEnrollments } from "./offline";

// Inscription sans réseau (HL.1) : frais dus tirés des barèmes de l'appareil, élève provisoire
// encaissable à la caisse, doublon de l'appareil.

const installment = (id: string, amount: number, dueOn: string, order: number) => ({
  id,
  label: `Tranche ${order}`,
  amount_minor: amount,
  due_on: dueOn,
  order,
});

const config = {
  academic_year: { id: "year", name: "2026-2027", starts_on: "2026-09-01", ends_on: "2027-07-02" },
  fee_types: [
    { id: "tuition", name: "Minerval", category: "tuition", is_active: true },
    { id: "exam", name: "Frais d'État", category: "official_exam", is_active: true },
  ],
  fee_rules: [
    {
      id: "r-1A",
      fee_type: "tuition",
      currency: "USD",
      installments: [
        installment("t2", 6000, "2026-12-15", 2),
        installment("t1", 6000, "2026-09-30", 1),
      ],
      class_groups: ["1A"],
    },
    {
      id: "r-exam",
      fee_type: "exam",
      currency: "CDF",
      installments: [installment("e1", 2500000, "2027-02-28", 1)],
      class_groups: ["1A", "2B"],
    },
    {
      id: "r-2B",
      fee_type: "tuition",
      currency: "USD",
      installments: [installment("x1", 9000, "2026-09-30", 1)],
      class_groups: ["2B"],
    },
  ],
} as unknown as Config;

let next = 0;
const newId = () => `c${(next += 1)}`;

function enrolledHere(id: string, status: QueuedOperation["status"]): QueuedOperation {
  const charges = deviceCharges(config, "1A", id, newId).map(({ charge }) => charge);
  return {
    op_id: `s-${id}`,
    type: "student.enroll",
    payload: {},
    created_at: "2026-10-05T08:00:00Z",
    status,
    error: null,
    enrollment: {
      id,
      academic_year: "year",
      class_group: "1A",
      status: "active",
      enrolled_on: "2026-10-05",
      left_on: null,
      student: {
        id: `s-${id}`,
        family: "f1",
        matricule: provisionalMatricule("0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b"),
        last_name: "BISIMWA",
        middle_name: "MUGISHO",
        first_name: "Arsène",
        sex: "M",
        birth_date: "2011-03-12",
        family_code: "FAM-PRV-2M9",
      },
      charges,
      payments: [],
      credits: [],
      credit_uses: [],
    },
  };
}

describe("inscription sur l'appareil", () => {
  it("tire les frais dus des barèmes de la classe, en entiers et dans leur devise", () => {
    const made = deviceCharges(config, "1A", "e1", newId);
    // Minerval de la 1A (pas celui de la 2B) et frais d'État : une ligne par tranche, par échéance.
    expect(made.map(({ template }) => template)).toEqual(["t1", "t2", "e1"]);
    expect(
      made.map(({ charge }) => [charge.amount_minor, charge.currency, charge.remaining_minor]),
    ).toEqual([
      [6000, "USD", 6000],
      [6000, "USD", 6000],
      [2500000, "CDF", 2500000],
    ]);
    expect(new Set(made.map(({ charge }) => charge.id)).size).toBe(3);
    expect(made.every(({ charge }) => charge.enrollment === "e1")).toBe(true);
    // Sans droit sur les finances, la config n'a pas de barèmes : aucun frais.
    expect(deviceCharges({ ...config, fee_rules: null }, "1A", "e1", newId)).toEqual([]);
  });

  it("montre à la caisse l'élève inscrit ici jusqu'à la descente, encaissable", () => {
    const waiting = enrolledHere("e-new", "pending");
    const [shown] = queuedEnrollments([waiting], new Map());
    const { balance } = financeOf(shown!, [], "2026-10-05");
    expect(balance.currencies.map((line) => [line.currency, line.remaining_minor])).toEqual([
      ["USD", 12000],
      ["CDF", 2500000],
    ]);
    expect(shown!.student.matricule).toMatch(/^PRV-[2-9A-HJKMNP-Z]{4}$/);
    // Descendue (même identifiant) : celle du serveur seulement ; refusée : plus montrée.
    expect(queuedEnrollments([waiting], new Map([["e-new", shown]]))).toEqual([]);
    expect(queuedEnrollments([enrolledHere("e-no", "rejected")], new Map())).toEqual([]);
  });

  it("repère un doublon de l'appareil : mêmes nom, prénom et date de naissance", () => {
    const [known] = queuedEnrollments([enrolledHere("e-old", "sent")], new Map());
    const same = { last_name: "bisimwa ", first_name: "ARSÈNE", birth_date: "2011-03-12" };
    expect(localDuplicates([known as LocalEnrollment], same)).toHaveLength(1);
    expect(
      localDuplicates([known as LocalEnrollment], { ...same, birth_date: "2011-03-13" }),
    ).toEqual([]);
    expect(localDuplicates([known as LocalEnrollment], { ...same, birth_date: null })).toEqual([]);
  });
});
