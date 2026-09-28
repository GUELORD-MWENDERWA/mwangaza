import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { json, mockApi, type Routes } from "../../test/api";
import { charge, fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const cashier = { id: fakeId(1), last_name: "Kavira", middle_name: "", first_name: "Jeanne" };
const register = (n: number, open_session: unknown = null) => ({
  id: fakeId(10 + n),
  name: `Caisse ${n}`,
  code: `C${n}`,
  is_active: true,
  open_session,
});
const session = {
  id: fakeId(20),
  cash_register: register(2),
  cashier,
  opened_at: "2026-10-19T05:42:00Z",
  closed_at: null,
};
const current = (open: unknown) => ({
  session: open,
  totals: [],
  rate: "2850.000000",
  rate_is_fallback: false,
});
const noPayments = { count: 0, next: null, previous: null, results: [] };

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("cashier"),
    "GET /api/payments/": noPayments,
    ...extra,
  };
}

describe("Caisse (F1-F2)", () => {
  it("ouvre une caisse libre ; une caisse occupée ne se choisit pas", async () => {
    const all = routes({
      "GET /api/cash-sessions/current/": current(null),
      "GET /api/cash-registers/": [
        register(1, {
          id: fakeId(21),
          cashier: { ...cashier, id: fakeId(2), first_name: "Alice" },
          opened_at: "2026-10-19T05:35:00Z",
        }),
        register(2),
      ],
    });
    all["POST /api/cash-sessions/"] = () => {
      all["GET /api/cash-sessions/current/"] = current(session);
      return json(session, 201);
    };
    const requests = mockApi(all);
    const { user } = renderApp("/cash");

    const [busy, free] = await screen.findAllByRole("radio");
    expect((busy as HTMLInputElement).disabled).toBe(true);
    expect((free as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText("Ouverte à 07:35 par Alice Kavira")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Ouvrir la caisse C2" }));

    expect(await screen.findByRole("heading", { name: "Caisse 2" })).toBeTruthy();
    const opened = requests.find((request) => request.method === "POST");
    expect(opened?.body).toEqual({ id: expect.any(String), cash_register: register(2).id });
  });

  it("encaisse la répartition affichée, une seule fois même après une coupure", async () => {
    const workshop = charge(1, "1re tranche", "2026-10-01", {
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
    const tuition = charge(3, "2e tranche", "2027-01-15");
    const operating = charge(4, "2e tranche", "2027-01-15", {
      fee_type_name: "Fonctionnement",
      amount_minor: 2500,
    });
    const enrollment = {
      id: fakeId(80),
      student: fakeId(30),
      academic_year: fakeId(40),
      academic_year_name: "2026-2027",
      class_group: fakeId(50),
      class_group_name: "3e Électricité A",
      status: "active",
      enrolled_on: "2026-09-01",
      left_on: null,
    };
    const student = {
      id: fakeId(30),
      matricule: "ALPHA-2026-0412",
      last_name: "Kambale",
      middle_name: "Muhindo",
      first_name: "Josué",
      sex: "M",
      birth_date: "2011-03-02",
      family: fakeId(60),
      family_code: "FAM-0412",
      enrollment,
      primary_guardian: null,
    };
    const all = routes({
      "GET /api/cash-sessions/current/": current(session),
      "GET /api/students/": { count: 1, next: null, previous: null, results: [student] },
      "GET /api/student-charges/": [workshop, motivation, tuition, operating],
      "GET /api/student-charges/balance/": {
        currencies: [
          {
            currency: "USD",
            total_minor: 16500,
            paid_minor: 0,
            remaining_minor: 16500,
            overdue_minor: 2000,
            next_due_minor: 14500,
          },
          {
            currency: "CDF",
            total_minor: 30000,
            paid_minor: 0,
            remaining_minor: 30000,
            overdue_minor: 30000,
            next_due_minor: 0,
          },
        ],
        next_due_on: "2027-01-15",
      },
    });
    let attempts = 0;
    all["POST /api/payments/"] = () => {
      attempts += 1;
      // Première fois : le réseau coupe avant la réponse.
      if (attempts === 1) throw new TypeError("Failed to fetch");
      return json({ id: fakeId(90), receipt_number: "ALPHA-C2-26-000184" }, 201);
    };
    const requests = mockApi(all);
    const { user } = renderApp("/cash");

    await user.type(await screen.findByLabelText("Élève qui paie"), "Kambale");
    await user.click(await screen.findByRole("button", { name: /KAMBALE MUHINDO Josué/ }));
    const amount = await screen.findByLabelText("Montant reçu en USD");
    const collect = screen.getByRole("button", { name: /Encaisser/ });

    // Plus que ce que doit l'élève en dollars : refusé (le crédit vient en 3.6).
    await user.type(amount, "500");
    expect(await screen.findByText(/335,00 \$ de trop pour les frais cochés/)).toBeTruthy();
    expect((collect as HTMLButtonElement).disabled).toBe(true);

    await user.clear(amount);
    await user.type(amount, "150");
    await user.click(collect);
    await waitFor(() => expect(attempts).toBe(1));
    await user.click(collect);

    expect(await screen.findByText("Paiement enregistré : reçu ALPHA-C2-26-000184.")).toBeTruthy();
    const sent = requests.filter((request) => request.method === "POST").map((r) => r.body);
    // Anciennes échéances d'abord, francs non touchés, le fonctionnement en partie ; même `id`.
    expect(sent[0]).toEqual({
      id: expect.any(String),
      enrollment: enrollment.id,
      received_amount_minor: 15000,
      received_currency: "USD",
      convert: false,
      allocations: [
        { student_charge: workshop.id, received_minor: 2000 },
        { student_charge: tuition.id, received_minor: 12000 },
        { student_charge: operating.id, received_minor: 1000 },
      ],
      note: "",
    });
    expect(sent[1]).toEqual(sent[0]);
  });
});
