import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RIGHTS } from "../../lib/rights";
import { OWNER, mockApi, renderApp } from "../../test/render";

const ME = {
  id: "a1",
  phone: "+243970000001",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
  ...OWNER,
};

const invoice = {
  id: "i1",
  number: "FAC-2026-0003",
  kind: "invoice",
  school: "itig-demo",
  contract: "CTR-2026-0001",
  credit_for: null,
  issued_on: "2026-11-01",
  due_on: "2099-11-15",
  period_start: "2026-09-01",
  period_end: "2026-12-31",
  currency: "USD",
  total: 160000,
  cancelled: false,
  paid: 0,
  balance: 160000,
  lines: [{ description: "Plan Complet", quantity: 800, unit_amount: 200, amount: 160000 }],
  payments: [],
};
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

afterEach(() => vi.unstubAllGlobals());

describe("Facturation de la plateforme", () => {
  it("un membre qui ne voit que les écoles lit les offres, sans les factures (argent)", async () => {
    mockApi({
      "GET /api/me/": {
        ...ME,
        platform_roles: ["support"],
        platform_permissions: [RIGHTS.schoolsView],
      },
      "GET /api/console/billing/plans/": page([]),
      "GET /api/console/billing/invoices/": page([invoice]),
    });
    const { user } = renderApp("/billing");

    expect(await screen.findByRole("button", { name: "Offres" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Factures" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Conditions" }));
    expect(screen.queryByText("FAC-2026-0003")).toBeNull();
  });

  it("enregistre un paiement en plus petite unité et refuse un montant mal écrit", async () => {
    const requests = mockApi({
      "GET /api/me/": ME,
      "GET /api/console/billing/invoices/": page([invoice]),
      "POST /api/console/billing/invoices/i1/pay/": invoice,
    });
    const { user } = renderApp("/billing");

    await user.click(await screen.findByRole("button", { name: "Ouvrir" }));
    await user.click(await screen.findByRole("button", { name: "Enregistrer un paiement" }));
    const dialog = (await screen.findAllByRole("dialog")).at(-1)!;
    await user.type(within(dialog).getByLabelText(/Montant/), "12,345");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(await within(dialog).findByText("Montant invalide.")).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);

    await user.clear(within(dialog).getByLabelText(/Montant/));
    await user.type(within(dialog).getByLabelText(/Montant/), "500,50");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await vi.waitFor(() =>
      expect(requests.find((r) => r.method === "POST")?.body).toMatchObject({
        amount: 50050,
        method: "bank",
      }),
    );
  });
});
