import { cleanup, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const subscription = {
  contract: {
    number: "CTR-2026-0001",
    end_date: "2027-08-31",
    currency: "USD",
    modules: ["students", "finance"],
  },
  plan_name: "Complet",
  balance: [{ currency: "USD", amount: 110000 }],
  next_due: { number: "FAC-2026-0003", due_on: "2026-11-15", currency: "USD", amount: 110000 },
  late: true,
  read_only: true,
  payment_details: "Virement : compte 123",
  open_requests: [],
};

const routes = (account: ReturnType<typeof me>, readOnly: boolean): Routes => ({
  "GET /api/school/": { ...school, read_only: readOnly },
  "GET /api/me/": account,
  "GET /api/subscription/": subscription,
  "GET /api/subscription/invoices/": { count: 0, next: null, previous: null, results: [] },
});

describe("Mon abonnement (ABO.4)", () => {
  it("affiche l'offre, le solde et comment payer, même en lecture seule", async () => {
    mockApi(routes(me("head"), true));
    renderApp("/subscription");
    expect(await screen.findByText("Complet")).toBeTruthy();
    expect(screen.getByText("Virement : compte 123")).toBeTruthy();
    expect(screen.getAllByText(/Lecture seule/).length).toBeGreaterThan(0);
  });

  it("le bandeau de lecture seule est vu par tous les rôles, sans lien pour qui n'a pas le droit", async () => {
    mockApi(routes(me("cashier"), true));
    renderApp("/");
    expect(await screen.findByText(/Lecture seule\./)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Mon abonnement" })).toBeNull();
    cleanup();
  });
});
