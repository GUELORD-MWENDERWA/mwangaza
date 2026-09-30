import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const C1 = { id: id(11), name: "Caisse 1", code: "C1", is_active: true };
const C2 = { id: id(12), name: "Caisse 2", code: "C2", is_active: true };
const kavira = { id: id(21), last_name: "Kavira", middle_name: "", first_name: "Jeanne" };
const zawadi = { id: id(22), last_name: "Zawadi", middle_name: "", first_name: "Alice" };
const closedSession = {
  id: id(1),
  cash_register: C1,
  cashier: kavira,
  opened_at: "2026-10-19T05:42:00Z",
  closed_at: "2026-10-19T14:51:00Z",
};
const forgotten = {
  id: id(2),
  cash_register: C2,
  cashier: zawadi,
  opened_at: "2026-10-18T05:31:00Z",
  closed_at: null,
};
const closedRow = {
  ...closedSession,
  payments_count: 41,
  state: "difference",
  lines: [
    { currency: "USD", expected_minor: 265000, counted_minor: 264500, difference_minor: -500 },
    { currency: "CDF", expected_minor: 480000, counted_minor: 480000, difference_minor: 0 },
  ],
  late: [{ currency: "USD", amount_minor: 6000, count: 1 }],
};
const openRow = {
  ...forgotten,
  payments_count: 29,
  state: "unclosed",
  lines: [
    { currency: "USD", expected_minor: 141000, counted_minor: null, difference_minor: null },
    { currency: "CDF", expected_minor: 540000, counted_minor: null, difference_minor: null },
  ],
  late: [],
};
const detail = {
  session: closedSession,
  currencies: [
    { currency: "USD", expected_minor: 265000, count: 30 },
    { currency: "CDF", expected_minor: 480000, count: 11 },
  ],
  fee_types: [],
  payments_count: 41,
  first_receipt: "ITIG-C1-26-000144",
  last_receipt: "ITIG-C1-26-000184",
  cancelled: [{ currency: "USD", amount_minor: 5000, count: 1 }],
  cancellations_pending: 0,
  closing: {
    lines: closedRow.lines,
    note: "Billet de 5 $ déchiré rendu au parent",
    closed_at: "2026-10-19T14:51:00Z",
    closed_by: kavira,
    offline: true,
    received_at: "2026-10-19T15:20:00Z",
  },
  state: "difference",
  late_payments: [
    {
      id: id(301),
      receipt_number: "ITIG-P2-26-000012",
      student: { id: id(70), full_name: "SAFARI BIRINGANINE Patrick", matricule: "ITIG-2026-0179" },
      amount_minor: 6000,
      currency: "USD",
      paid_at: "2026-10-19T13:10:00Z",
      received_at: "2026-10-19T16:02:00Z",
      cancelled: false,
    },
  ],
};

function routes(): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/cash-closings/": {
      count: 2,
      next: null,
      previous: null,
      results: [closedRow, openRow],
    },
    "GET /api/cash-closings/summary/": {
      sessions: 31,
      cash_registers: 2,
      differences: [
        { currency: "USD", difference_minor: -500, sessions: 1 },
        { currency: "CDF", difference_minor: 0, sessions: 0 },
      ],
      registers: [C1, C2],
      unclosed: [forgotten],
    },
    [`GET /api/cash-closings/${id(1)}/`]: detail,
  };
}

describe("Clôtures de caisse (M16)", () => {
  it("le comptable voit l'écart, la caisse restée ouverte et le paiement arrivé après la clôture, sans rien pouvoir modifier", async () => {
    const requests = mockApi(routes());
    renderApp("/cash-closings");

    // Bandeau : la session d'hier pas clôturée ; écart par devise, jamais additionné.
    await screen.findByText(/Alice Zawadi doit la clôturer avant d'encaisser à nouveau/);
    expect(screen.getAllByText("− 5,00 $").length).toBeGreaterThan(0);
    await screen.findByText("Billet de 5 $ déchiré rendu au parent");
    const card = screen.getByText("Caisse 1 · 19/10/2026").closest("div")!.parentElement!;
    within(card).getByText("ITIG-C1-26-000144 → 000184");
    within(card).getByText("16:51, hors-ligne · reçue au serveur à 17:20");
    within(card).getByText(/1 paiement encaissé hors ligne est arrivé après la clôture/);
    within(card).getByText("ITIG-P2-26-000012 · SAFARI BIRINGANINE Patrick");
    screen.getByRole("button", { name: "Bordereau" });
    screen.getByText("1 arrivé après la clôture");
    // Lecture seule : aucune écriture vers le serveur.
    expect(requests.filter((request) => request.method !== "GET")).toEqual([]);
  });

  it("le mois et la caisse choisis filtrent la liste, les chiffres et l'export Excel", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/cash-closings");

    const register = await screen.findByRole("combobox", { name: "Caisse" });
    await screen.findByRole("option", { name: "Caisse : Caisse 2" });
    await user.selectOptions(register, C2.id);

    const excel = screen.getByRole("link", { name: "Excel" });
    expect(excel.getAttribute("href")).toContain(`cash_register=${C2.id}`);
    const filtered = requests.filter(
      (request) =>
        request.path.startsWith("/api/cash-closings/") && request.query.cash_register === C2.id,
    );
    expect(new Set(filtered.map((request) => request.path))).toEqual(
      new Set(["/api/cash-closings/", "/api/cash-closings/summary/"]),
    );
    expect(filtered.every((request) => /^\d{4}-\d{2}$/.test(request.query.month!))).toBe(true);
  });
});
