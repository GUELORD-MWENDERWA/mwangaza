import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const cashier = { id: fakeId(1), last_name: "Kavira", middle_name: "", first_name: "Jeanne" };
const session = {
  id: fakeId(20),
  cash_register: { id: fakeId(12), name: "Caisse 1", code: "C1", is_active: true },
  cashier,
  opened_at: "2026-10-19T05:42:00Z",
  closed_at: null,
};
const expense = (n: number, amount_minor: number) => ({
  id: fakeId(70 + n),
  number: `DEP-26-004${n}`,
  category_name: "Atelier mécanique",
  beneficiary: "Quincaillerie Mapendo",
  reason: "Pièces atelier",
  amount_minor,
  currency: "USD",
  spent_on: "2026-10-19",
});
const current = {
  session,
  totals: [{ currency: "USD", amount_minor: 100000, count: 4 }],
  paid_out: [{ currency: "USD", amount_minor: 20000, count: 1 }],
  rate: "2850.000000",
  rate_is_fallback: false,
};
const payable = (...results: ReturnType<typeof expense>[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

describe("Sortie de caisse (FIN.2)", () => {
  it("montre l'attendu avant et après, refuse plus que la caisse n'a reçu, et envoie la sortie", async () => {
    window.print = vi.fn();
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("cashier"),
      "GET /api/cash-sessions/current/": current,
      "GET /api/cash-outs/payable/": payable(expense(1, 18500), expense(2, 90000)),
      "POST /api/cash-outs/": (request) =>
        request
          .clone()
          .json()
          .then((body) => ({
            id: body.id,
            number: "ITIG-C1-26-S0001",
            expense: body.expense,
            expense_number: "DEP-26-0041",
            category_name: "Atelier mécanique",
            beneficiary: "Quincaillerie Mapendo",
            reason: "Pièces atelier",
            amount_minor: 18500,
            currency: "USD",
            received_by: body.received_by,
            paid_at: "2026-10-19T12:32:00Z",
            cash_session: session.id,
            cash_register_code: "C1",
            cash_register_name: "Caisse 1",
            cashier_name: "Jeanne Kavira",
            offline: false,
            cancelled: false,
            cancellation_reason: null,
          })),
    });
    const { user } = renderApp("/cash/out");

    const select = await screen.findByLabelText(/Dépense à payer/);
    // Trop gros : 900 $ pour 800 $ en caisse (1 000 reçus − 200 sortis).
    await user.selectOptions(select, fakeId(72));
    await screen.findByText(/n'a pas assez reçu/);
    expect(
      (screen.getByRole("button", { name: /Sortir et imprimer/ }) as HTMLButtonElement).disabled,
    ).toBe(true);

    await user.selectOptions(select, fakeId(71));
    screen.getByText("800,00 $");
    screen.getByText("615,00 $");
    await user.click(screen.getByRole("button", { name: /Sortir et imprimer/ }));

    await screen.findByText(/Sortie ITIG-C1-26-S0001 enregistrée/);
    const post = requests.find((r) => r.method === "POST" && r.path === "/api/cash-outs/")!;
    expect(post.body).toMatchObject({ expense: fakeId(71), received_by: "Quincaillerie Mapendo" });
    await waitFor(() => expect(window.print).toHaveBeenCalled());
  });
});
