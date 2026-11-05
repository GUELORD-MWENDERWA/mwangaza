import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const base = {
  category: id(1),
  category_name: "Atelier mécanique",
  reason: "Pièces pour le banc d'essai",
  currency: "USD",
  spent_on: "2026-10-19",
  account: "bank",
  has_voucher: true,
  requested_by_name: "Ir. Paluku",
  decided_by_name: null,
  decided_at: null,
  decision_note: "",
  paid_at: null,
  cancelled: false,
  cancellation_reason: null,
  created_at: "2026-10-19T08:00:00Z",
};
const waiting = {
  ...base,
  id: id(11),
  number: "DEP-26-0047",
  beneficiary: "Quincaillerie Mapendo",
  amount_minor: 42000,
  status: "pending",
};
const cancelled = {
  ...base,
  id: id(12),
  number: "DEP-26-0046",
  beneficiary: "Ets Kahindo",
  amount_minor: 7500,
  status: "paid",
  cancelled: true,
  cancellation_reason: "Doublon",
};

function routes(): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/expenses/": { count: 2, next: null, previous: null, results: [waiting, cancelled] },
    "GET /api/expenses/summary/": {
      by_currency: [{ currency: "USD", spent: 0, pending: 42000, pending_count: 1, cash: null }],
      cancelled: [{ currency: "USD", total: 7500, count: 1 }],
    },
    "GET /api/expense-categories/": [{ id: id(1), name: "Atelier mécanique", is_active: true }],
    "GET /api/expense-settings/": { usd_threshold_minor: 20000, cdf_threshold_minor: 50000000 },
    "POST /api/expenses/00000000-0000-7000-8000-000000000011/approve/": {
      ...waiting,
      status: "approved",
    },
  };
}

describe("Dépenses (FIN.1)", () => {
  it("annonce ce qui attend une validation, garde la dépense annulée sans action et valide", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/expenses");

    const pending = (await screen.findByText("Quincaillerie Mapendo")).closest("tr")!;
    within(pending).getByText("420,00 $");
    within(pending).getByText("À valider");
    const old = screen.getByText("Ets Kahindo").closest("tr")!;
    within(old).getByText("Annulée");
    within(old).getByText("Doublon");
    expect(within(old).queryByRole("button")).toBeNull();
    screen.getByText(/1 dépense attend une validation/);

    await user.click(within(pending).getByRole("button", { name: "Valider" }));
    await user.click(screen.getAllByRole("button", { name: "Valider" }).at(-1)!);
    await screen.findByText("Quincaillerie Mapendo");
    expect(requests.some((r) => r.method === "POST" && r.path.endsWith("/approve/"))).toBe(true);
  });
});
