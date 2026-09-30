import { describe, expect, it } from "vitest";

import { closingOnDevice, differences } from "./closing";
import type { SessionPayment } from "./offline";

type Payment = SessionPayment["payment"];

const row = (
  number: string,
  amount: number,
  currency: "USD" | "CDF",
  parts: [string, number][],
  more: Partial<Payment> = {},
  sync: SessionPayment["sync"] = "recorded",
): SessionPayment => ({
  payment: {
    receipt_number: number,
    received_amount_minor: amount,
    received_currency: currency,
    paid_at: `2026-10-19T0${number.at(-1)}:00:00Z`,
    cancelled: false,
    cancellation_pending: false,
    allocations: parts.map(([fee_type_name, received_minor]) => ({
      fee_type_name,
      received_minor,
    })),
    ...more,
  } as Payment,
  sync,
  error: null,
});

describe("clôture sur l'appareil", () => {
  it("attend les paiements gardés par devise, le trop-perçu à part, jamais les annulés ni les refusés", () => {
    const rows = [
      row("P1-3", 15000, "USD", [["Minerval", 12000]]), // 30,00 $ de trop-perçu hors ligne
      row("C1-1", 4500, "USD", [["Frais d'atelier", 4500]], { cancellation_pending: true }),
      row("C1-2", 5000, "USD", [["Minerval", 5000]], { cancelled: true }),
      row("P1-4", 9000, "USD", [["Minerval", 9000]], {}, "rejected"),
      row("P1-5", 25000, "CDF", [["Fonctionnement", 25000]], {}, "pending"),
    ];

    const data = closingOnDevice(rows, ["USD", "CDF"]);

    expect(data.currencies).toEqual([
      { currency: "USD", expected_minor: 19500, count: 2 },
      { currency: "CDF", expected_minor: 25000, count: 1 },
    ]);
    expect(data.fee_types).toEqual([
      { fee_type: "Fonctionnement", currency: "CDF", amount_minor: 25000 },
      { fee_type: "Frais d'atelier", currency: "USD", amount_minor: 4500 },
      { fee_type: "Minerval", currency: "USD", amount_minor: 12000 },
      { fee_type: null, currency: "USD", amount_minor: 3000 },
    ]);
    expect([data.payments_count, data.first_receipt, data.last_receipt]).toEqual([
      4,
      "C1-1",
      "P1-5",
    ]);
    expect(data.cancelled).toEqual([{ currency: "USD", amount_minor: 5000, count: 1 }]);
    expect(data.cancellations_pending).toBe(1);

    expect(differences(data, { USD: 19000 })).toEqual([
      { currency: "USD", expected_minor: 19500, counted_minor: 19000, difference_minor: -500 },
      { currency: "CDF", expected_minor: 25000, counted_minor: null, difference_minor: null },
    ]);
  });

  it("compte chaque devise de l'école, même sans paiement", () => {
    const data = closingOnDevice([], ["USD", "CDF"]);
    expect(data.currencies.map((c) => [c.currency, c.expected_minor])).toEqual([
      ["USD", 0],
      ["CDF", 0],
    ]);
    expect([data.payments_count, data.first_receipt]).toEqual([0, null]);
  });
});
