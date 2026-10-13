import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCOUNT, currency, ITIG } from "../../test/fixtures";
import { mockApi, renderApp } from "../../test/render";

const fee = (
  id: string,
  name: string,
  due: string,
  code: string,
  amount: number,
  left: number,
  state: string,
) => ({
  id,
  fee: name,
  due_on: due,
  currency: code,
  amount_minor: amount,
  remaining_minor: left,
  state,
});

const CHILD = {
  id: "s1",
  full_name: "KASEREKA Muhindo Jean",
  class_name: "3e Électricité A",
  academic_year: "2026-2027",
  school_name: "ITIG Don Bosco Goma",
  school_timezone: "Africa/Lubumbashi",
  school_environment: "live",
  school_modules: ["students", "finance", "communication", "portal"],
  photo: null,
  balance: {
    situation: "partial",
    next_due_on: "2027-04-15",
    currencies: [currency("USD", 36000, 29000, 0), currency("CDF", 25000, 0, 25000)],
  },
  fees: [
    fee("c1", "Fonctionnement", "2026-09-30", "CDF", 25000, 25000, "overdue"),
    fee("c2", "Minerval · 1re tranche", "2026-10-15", "USD", 12000, 0, "paid"),
    fee("c3", "Minerval · 2e tranche", "2027-01-15", "USD", 12000, 0, "paid_early"),
    fee("c4", "Minerval · 3e tranche", "2027-04-15", "USD", 12000, 7000, "partial"),
  ],
  payments: [
    {
      id: "p3",
      receipt_number: "ITIG-C1-26-000190",
      paid_at: "2026-10-20T09:00:00Z",
      received_amount_minor: 10000,
      received_currency: "CDF",
      cancelled: true,
    },
    {
      id: "p2",
      receipt_number: "ITIG-C1-26-000184",
      paid_at: "2026-10-19T09:00:00Z",
      received_amount_minor: 5000,
      received_currency: "USD",
      cancelled: false,
    },
  ],
};

describe("paiements d'un enfant", () => {
  it("depuis l'accueil : état de chaque frais, retard, reçus en PDF sauf paiement annulé", async () => {
    mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG],
      "GET /api/portal/children/s1/": CHILD,
    });
    const { user } = renderApp("/");

    await user.click(await screen.findByText("KASEREKA Muhindo Jean"));

    await screen.findByText("Détail des frais");
    expect(screen.getByText("ITIG Don Bosco Goma · 3e Électricité A · 2026-2027")).toBeTruthy();
    // Par devise, jamais additionnés ; le retard depuis l'échéance la plus ancienne.
    expect(screen.getByText("290,00 $")).toBeTruthy();
    expect(screen.getByText("+ 0 FC")).toBeTruthy();
    expect(screen.getByText(/en retard depuis le 30\/09\/2026/)).toBeTruthy();
    expect(screen.getByText("Payé d'avance")).toBeTruthy();
    expect(screen.getByText("Partiel")).toBeTruthy();
    expect(screen.getAllByText("reste 70,00 $")).toHaveLength(1);

    const receipts = screen.getByRole("heading", { name: "Reçus" }).closest("section")!;
    const pdf = within(receipts).getByRole("link", { name: "Reçu ITIG-C1-26-000184 en PDF" });
    expect(pdf.getAttribute("href")).toBe("/api/portal/payments/p2/receipt/");
    expect(within(receipts).getAllByRole("link")).toHaveLength(1);
    expect(within(receipts).getByText("Annulé")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Paiements" }).getAttribute("aria-current")).toBe(
      "page",
    );
  });
});
