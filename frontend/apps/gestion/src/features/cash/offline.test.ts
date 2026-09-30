import type { Schemas } from "@mwangaza/api";
import { describe, expect, it } from "vitest";

import type { LocalEnrollment, QueuedOperation } from "../../lib/sync/db";
import type { Config } from "../../lib/sync/engine";
import {
  creditLines,
  creditUse,
  duplicateReceipt,
  financeOf,
  offlinePayload,
  offlineReceipt,
  receiptNumber,
  searchEnrollments,
  sessionPayments,
  sessionTotals,
} from "./offline";
import type { Receipt } from "./Receipt";

type Charge = Schemas["StudentCharge"];

const charge = (id: string, amount: number, currency: "USD" | "CDF", dueOn: string): Charge => ({
  id,
  enrollment: "e1",
  fee_type: "f",
  fee_type_name: "Minerval",
  fee_category: "tuition",
  label: id,
  amount_minor: amount,
  currency,
  due_on: dueOn,
  source: "rule",
  status: "active",
  discount_minor: 0,
  paid_minor: 0,
  remaining_minor: amount,
  state: "upcoming",
});

const session = {
  id: "s1",
  cash_register: { id: "r1", name: "Caisse principale", code: "C1", is_active: true },
  cashier: { id: "u1", last_name: "Kavira", middle_name: "", first_name: "Esther" },
  opened_at: "2026-10-05T07:00:00Z",
  closed_at: null,
};

function enrollment(payments: Schemas["Payment"][] = []): LocalEnrollment {
  return {
    id: "e1",
    academic_year: "y",
    class_group: "g",
    status: "active",
    enrolled_on: "2026-09-01",
    left_on: null,
    student: {
      id: "st1",
      matricule: "26-0042",
      last_name: "Kambale",
      middle_name: "Muhindo",
      first_name: "Josué",
      sex: "M",
      birth_date: null,
      family_code: "F1",
    },
    // T1 échue au 1er octobre, T2 à venir, frais d'examen en francs.
    charges: [
      { ...charge("t1", 5000, "USD", "2026-10-01"), discount_minor: 1000 },
      charge("t2", 6000, "USD", "2026-12-01"),
      charge("x", 2_000_000, "CDF", "2026-10-01"),
    ],
    payments,
    credits: [],
    gen: 1,
  };
}

/** Payé deux fois hors ligne : 50 $ à traiter. */
const credit: Schemas["StudentCredit"] = {
  id: "c1",
  enrollment: "e1",
  student: { id: "st1", full_name: "KAMBALE Muhindo Josué", matricule: "26-0042" },
  class_group: "3e Électricité A",
  origin: "offline_surplus",
  amount_minor: 5000,
  currency: "USD",
  used_minor: 0,
  remaining_minor: 5000,
  state: "to_process",
  created_at: "2026-10-04T10:00:00Z",
  voided_at: null,
  source_payment: "p12",
  receipt_number: "ITIG-P2-26-000012",
  cash_register_name: "Caisse 2",
  paid_at: "2026-10-04T09:30:00Z",
  discount_reason: null,
  discount_fee_type: null,
};

/** Encaissement de l'appareil : 30 $ sur T1 (échue), numéro donné par l'appareil. */
function collect(seq: number, id: string, paidAt = "2026-10-05T09:00:00Z"): Receipt {
  const { charges } = financeOf(enrollment(), [], "2026-10-05");
  return offlineReceipt({
    id,
    number: receiptNumber("itig", "P1", "2026-09-01", seq),
    enrollment: enrollment(),
    classGroup: "3e Électricité A",
    academicYear: "2026-2027",
    session,
    cashier: session.cashier,
    received: { minor: 3000, currency: "USD" },
    rate: "2850",
    lines: [{ charge: charges[0]!, received: 3000, amount: 3000 }],
    charges,
    note: "",
    paidAt,
    day: "2026-10-05",
  });
}

const queued = (receipt: Receipt, status: QueuedOperation["status"]): QueuedOperation => ({
  op_id: receipt.id,
  type: "payment.create",
  payload: offlinePayload(receipt),
  created_at: receipt.paid_at,
  status,
  error: status === "rejected" ? { code: "no_open_session", detail: "No open session." } : null,
  receipt,
});

describe("caisse sur l'appareil", () => {
  it("reçu : numéro de l'appareil, solde juste après le paiement, seulement ce que le serveur attend", () => {
    const receipt = collect(184, "p1");

    expect(receipt.receipt_number).toBe("ITIG-P1-26-000184");
    expect(receiptNumber("itig", "P1", "2026-09-01", 185)).toBe("ITIG-P1-26-000185");
    // T1 : 50 $ − 10 $ de réduction − 30 $ = 10 $ encore en retard ; les francs à part.
    expect(receipt.balance).toEqual({
      situation: "partial",
      next_due_on: "2026-12-01",
      currencies: [
        {
          currency: "USD",
          total_minor: 10000,
          paid_minor: 3000,
          remaining_minor: 7000,
          overdue_minor: 1000,
          next_due_minor: 6000,
        },
        {
          currency: "CDF",
          total_minor: 2_000_000,
          paid_minor: 0,
          remaining_minor: 2_000_000,
          overdue_minor: 2_000_000,
          next_due_minor: 0,
        },
      ],
    });
    expect(Object.keys(offlinePayload(receipt)).sort()).toEqual(
      [
        "allocations",
        "cash_session",
        "convert",
        "enrollment",
        "id",
        "note",
        "paid_at",
        "receipt_number",
        "received_amount_minor",
        "received_currency",
      ].sort(),
    );
    expect(offlinePayload(receipt).allocations).toEqual([
      { student_charge: "t1", received_minor: 3000 },
    ]);
  });

  it("solde : paiement en attente compté, déjà descendu du serveur compté une fois, refusé jamais", () => {
    const pending = collect(184, "p1");
    const rejected = collect(185, "p2");
    const day = "2026-10-05";

    const t1 = (state: LocalEnrollment, items: QueuedOperation[]) =>
      financeOf(state, items, day).charges[0]!;
    expect(t1(enrollment(), [queued(pending, "pending")])).toMatchObject({
      remaining_minor: 1000,
      state: "overdue",
    });
    // Envoyé, puis descendu avec l'état du serveur, qui l'a déjà compté : pas deux fois.
    const synced = enrollment([pending]);
    synced.charges![0] = { ...synced.charges![0]!, paid_minor: 3000, remaining_minor: 1000 };
    expect(t1(synced, [queued(pending, "sent")]).remaining_minor).toBe(1000);
    expect(t1(enrollment(), [queued(rejected, "rejected")]).remaining_minor).toBe(4000);
    // Échéance à venir hier devenue échue aujourd'hui.
    expect(financeOf(enrollment(), [], "2026-12-02").charges[1]!.state).toBe("overdue");
  });

  it("crédit utilisé : compté comme payé jusqu'à ce que le serveur le montre, jamais s'il est refusé", () => {
    const day = "2026-10-05";
    const state = { ...enrollment(), credits: [credit] };
    const lines = creditLines(financeOf(state, [], day).charges, credit);
    // T1 (40 $ après la réduction), puis 10 $ sur T2 ; jamais les francs.
    expect(lines.map((line) => [line.charge.id, line.amount])).toEqual([
      ["t1", 4000],
      ["t2", 1000],
    ]);
    const use = (status: QueuedOperation["status"]): QueuedOperation => ({
      op_id: "o1",
      type: "credit.use",
      payload: { credit: "c1" },
      created_at: "2026-10-05T09:00:00Z",
      status,
      error: status === "rejected" ? { code: "credit_used", detail: "Used." } : null,
      creditUse: creditUse(credit, lines),
    });
    const remaining = (result: ReturnType<typeof financeOf>) =>
      result.charges.map((item) => item.remaining_minor);

    const pending = financeOf(state, [use("pending")], day);
    expect(remaining(pending)).toEqual([0, 5000, 2_000_000]);
    expect(pending.credits).toEqual([]);
    // Descendu : le serveur l'a utilisé, il n'est plus à traiter ; pas compté deux fois.
    const synced = enrollment();
    synced.charges![0] = { ...synced.charges![0]!, paid_minor: 4000, remaining_minor: 0 };
    synced.charges![1] = { ...synced.charges![1]!, paid_minor: 1000, remaining_minor: 5000 };
    expect(remaining(financeOf(synced, [use("sent")], day))).toEqual([0, 5000, 2_000_000]);
    const refused = financeOf(state, [use("rejected")], day);
    expect(remaining(refused)).toEqual([4000, 6000, 2_000_000]);
    expect(refused.credits.map((item) => item.remaining_minor)).toEqual([5000]);
  });

  it("duplicata : solde juste après ce paiement, ni les suivants ni les annulés avant lui, file comprise", () => {
    const cancelled = {
      ...collect(183, "p0", "2026-10-05T08:00:00Z"),
      cancelled: true,
      cancelled_at: "2026-10-05T08:30:00Z",
    };
    const first = collect(184, "p1");
    const later = collect(185, "p2", "2026-10-05T10:00:00Z");
    const synced = enrollment([cancelled, first, later]);
    // Le serveur a compté p1 et p2 (T1 soldée) ; le duplicata de p1 revient à juste après lui.
    synced.charges![0] = { ...synced.charges![0]!, paid_minor: 6000, remaining_minor: 0 };
    const config = {
      academic_year: { name: "2026-2027" },
      cash_registers: [session.cash_register],
    } as Config;

    const duplicate = duplicateReceipt(synced, "p1", [], config, "UTC")!;
    expect(duplicate.balance).toEqual(first.balance);
    expect([duplicate.cash_register_name, duplicate.academic_year]).toEqual([
      "Caisse principale",
      "2026-2027",
    ]);
    // Encaissé plus tôt sur cet appareil, pas encore envoyé : compté avant p1, comme le fera le
    // serveur ; son propre duplicata est son reçu.
    const earlier = collect(186, "p3", "2026-10-05T08:30:00Z");
    const withQueue = duplicateReceipt(synced, "p1", [queued(earlier, "pending")], config, "UTC");
    expect(withQueue!.balance.currencies[0]).toMatchObject({ paid_minor: 6000, overdue_minor: 0 });
    expect(duplicateReceipt(synced, "p3", [queued(earlier, "pending")], config, "UTC")).toBe(
      earlier,
    );
    // Annulé après p1 (3.8.1) : il comptait encore quand p1 a été encaissé.
    const cancelledLater = {
      ...collect(187, "p4", "2026-10-05T08:10:00Z"),
      cancelled: true,
      cancelled_at: "2026-10-05T11:00:00Z",
    };
    const exact = duplicateReceipt(
      enrollment([cancelled, cancelledLater, first, later]),
      "p1",
      [],
      config,
      "UTC",
    );
    expect(exact!.balance.currencies[0]).toMatchObject({ paid_minor: 6000 });
  });

  it("paiements de la session : les plus récents d'abord, refusés montrés mais hors des totaux", () => {
    const early = collect(184, "p1", "2026-10-05T08:00:00Z");
    const late = collect(185, "p2", "2026-10-05T10:00:00Z");
    const refused = collect(186, "p3", "2026-10-05T11:00:00Z");
    const other = { ...collect(187, "p4"), cash_session: "s0" };

    const rows = sessionPayments(
      [enrollment([early, other])],
      [queued(early, "sent"), queued(late, "pending"), queued(refused, "rejected")],
      "s1",
    );

    expect(rows.map((row) => [row.payment.receipt_number, row.sync])).toEqual([
      ["ITIG-P1-26-000186", "rejected"],
      ["ITIG-P1-26-000185", "pending"],
      ["ITIG-P1-26-000184", "recorded"],
    ]);
    expect(sessionTotals(rows)).toEqual([{ currency: "USD", amount_minor: 6000, count: 2 }]);

    // Annulation demandée sur l'appareil (3.8.1) : montrée aussitôt, toujours comptée.
    const asked: QueuedOperation = {
      op_id: "o9",
      type: "cancellation.request",
      payload: { id: "r1", payment: "p1", reason: "Mauvais élève", requested_at: "x" },
      created_at: "2026-10-05T12:00:00Z",
      status: "pending",
      error: null,
    };
    const withAsk = sessionPayments([enrollment([early])], [asked], "s1");
    expect(withAsk[0]!.payment.cancellation_pending).toBe(true);
    expect(sessionTotals(withAsk)).toEqual([{ currency: "USD", amount_minor: 3000, count: 1 }]);
  });

  it("recherche : chaque mot, sans accents ni majuscules, ou le matricule", () => {
    const items = [enrollment()];
    expect(searchEnrollments(items, "josue KAMB", 8)).toHaveLength(1);
    expect(searchEnrollments(items, "26-0042", 8)).toHaveLength(1);
    expect(searchEnrollments(items, "josué kavira", 8)).toHaveLength(0);
  });
});
