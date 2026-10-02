import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { json, mockApi, type Routes } from "../../test/api";
import { charge, fakeId, me, school, studentCredit } from "../../test/fixtures";
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
const found = { count: 1, next: null, previous: null, results: [student] };

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("cashier"),
    "GET /api/payments/": noPayments,
    "GET /api/student-charges/credits/": [],
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

  it("encaisse la répartition affichée une seule fois, imprime le reçu, puis un duplicata", async () => {
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
    const all = routes({
      "GET /api/cash-sessions/current/": current(session),
      "GET /api/students/": found,
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
    const receipt = {
      id: fakeId(90),
      receipt_number: "ALPHA-C2-26-000184",
      enrollment: enrollment.id,
      student: { id: student.id, full_name: "KAMBALE MUHINDO Josué", matricule: student.matricule },
      class_group: "3e Électricité A",
      cash_register: "C2",
      cash_register_name: "Caisse 2",
      cashier,
      received_amount_minor: 15000,
      received_currency: "USD",
      rate_used: "2850.000000",
      paid_at: "2026-10-19T08:42:00Z",
      method: "cash",
      note: "",
      cancelled: false,
      academic_year: "2026-2027",
      allocations: [workshop, tuition, operating].map((item, index) => ({
        student_charge: item.id,
        fee_type_name: item.fee_type_name,
        label: item.label,
        currency: "USD",
        due_on: item.due_on,
        received_minor: [2000, 12000, 1000][index],
        amount_minor: [2000, 12000, 1000][index],
      })),
      balance: {
        situation: "partial",
        next_due_on: "2027-01-15",
        currencies: [
          { currency: "USD", remaining_minor: 1500, overdue_minor: 0 },
          { currency: "CDF", remaining_minor: 30000, overdue_minor: 30000 },
        ],
      },
    };
    let attempts = 0;
    all["POST /api/payments/"] = () => {
      attempts += 1;
      // Première fois : le réseau coupe avant la réponse.
      if (attempts === 1) throw new TypeError("Failed to fetch");
      return json(receipt, 201);
    };
    all[`POST /api/payments/${receipt.id}/reprint/`] = receipt;
    const printed: string[] = [];
    vi.spyOn(window, "print").mockImplementation(() => {
      printed.push(document.querySelector(".print-area")?.textContent ?? "");
    });
    const requests = mockApi(all);
    const { user } = renderApp("/cash");

    await user.type(await screen.findByLabelText("Élève qui paie"), "Kambale");
    await user.click(await screen.findByRole("button", { name: /KAMBALE MUHINDO Josué/ }));
    const amount = await screen.findByLabelText("Montant reçu en USD");
    const collect = screen.getByRole("button", { name: /Encaisser/ });

    // Plus que ce que doit l'élève en dollars : refusé (le caissier rend la monnaie).
    await user.type(amount, "500");
    expect(await screen.findByText(/335,00 \$ de trop pour les frais cochés/)).toBeTruthy();
    expect((collect as HTMLButtonElement).disabled).toBe(true);

    await user.clear(amount);
    await user.type(amount, "150");
    await user.click(collect);
    await waitFor(() => expect(attempts).toBe(1));
    // Deux F9 avant le prochain rendu : un seul envoi, donc un seul reçu.
    fireEvent.keyDown(window, { key: "F9" });
    fireEvent.keyDown(window, { key: "F9" });

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
    expect(sent).toHaveLength(2);
    expect(sent[1]).toEqual(sent[0]);

    // Reçu (F3) : montant en lettres, solde juste après ce paiement, pas de taux sans conversion.
    await waitFor(() => expect(printed).toHaveLength(1));
    expect(printed[0]).toContain("Reçu n° ALPHA-C2-26-000184");
    expect(printed[0]).toContain("Cent cinquante dollars américains");
    expect(printed[0]).toMatch(/Reste en retard30\s000\sFC/);
    expect(printed[0]).toMatch(/Reste de l'année15,00\s\$ \+ 30\s000\sFC/);
    expect(printed[0]).not.toContain("Taux utilisé");
    expect(printed[0]).not.toContain("Duplicata");
    // Réimpression (F6) : notée par le serveur, marquée DUPLICATA.
    await user.click(screen.getByRole("button", { name: "Réimprimer" }));
    await waitFor(() => expect(printed).toHaveLength(2));
    expect(printed[1]).toMatch(/DuplicataRéimprimé le \d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/);
    expect(requests.at(-1)?.path).toBe(`/api/payments/${receipt.id}/reprint/`);
  });

  it("propose le crédit de l'élève avant l'encaissement et l'utilise d'un clic, sans paiement", async () => {
    const workshop = charge(1, "1re tranche", "2026-10-01", {
      fee_type_name: "Frais d'atelier",
      amount_minor: 2000,
      state: "overdue",
    });
    const tuition = charge(3, "2e tranche", "2027-01-15");
    const credit = studentCredit();
    const all = routes({
      "GET /api/cash-sessions/current/": current(session),
      "GET /api/students/": found,
      "GET /api/student-charges/": [workshop, tuition],
      "GET /api/student-charges/balance/": { currencies: [], next_due_on: null },
      "GET /api/student-charges/credits/": [credit],
    });
    all[`POST /api/student-credits/${credit.id}/use/`] = () => {
      all["GET /api/student-charges/credits/"] = [];
      return { ...credit, used_minor: 3000, remaining_minor: 0, state: "used" };
    };
    const requests = mockApi(all);
    const { user } = renderApp("/cash");

    await user.type(await screen.findByLabelText("Élève qui paie"), "Kambale");
    await user.click(await screen.findByRole("button", { name: /KAMBALE MUHINDO Josué/ }));
    // Échéances les plus anciennes de sa devise d'abord.
    expect(
      await screen.findByText(
        /Il paiera : Frais d'atelier · 1re tranche 20,00 \$ ; Minerval · 2e tranche 10,00 \$/,
      ),
    ).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Utiliser le crédit" }));

    expect(
      await screen.findByText("Crédit de 30,00 $ utilisé : le reste dû est à jour."),
    ).toBeTruthy();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Utiliser le crédit" })).toBeNull(),
    );
    const posts = requests.filter((request) => request.method === "POST");
    expect(posts.map((request) => request.path)).toEqual([
      `/api/student-credits/${credit.id}/use/`,
    ]);
  });

  it("clôture : l'écart s'explique avant d'envoyer, puis le bordereau s'imprime", async () => {
    const summary = {
      session,
      currencies: [
        { currency: "USD", expected_minor: 265000, count: 40 },
        { currency: "CDF", expected_minor: 480000, count: 1 },
      ],
      fee_types: [
        { fee_type: "Minerval", currency: "USD", amount_minor: 265000 },
        { fee_type: "Motivation", currency: "CDF", amount_minor: 480000 },
      ],
      payments_count: 42,
      first_receipt: "ALPHA-C2-26-000144",
      last_receipt: "ALPHA-C2-26-000185",
      cancelled: [{ currency: "USD", amount_minor: 5000, count: 1 }],
      cancellations_pending: 1,
      closing: null,
    };
    const lines = [
      { currency: "USD", expected_minor: 265000, counted_minor: 264500, difference_minor: -500 },
      { currency: "CDF", expected_minor: 480000, counted_minor: 480000, difference_minor: 0 },
    ];
    const all = routes({
      "GET /api/cash-sessions/current/": current(session),
      [`GET /api/cash-sessions/${session.id}/closing/`]: summary,
    });
    all[`POST /api/cash-sessions/${session.id}/close/`] = () => {
      all["GET /api/cash-sessions/current/"] = current(null);
      all["GET /api/cash-registers/"] = [register(2)];
      const closing = {
        lines,
        note: "Billet déchiré rendu au parent",
        closed_at: "2026-10-19T14:51:00Z",
        closed_by: cashier,
        offline: false,
        received_at: "2026-10-19T14:51:00Z",
      };
      return json({ ...summary, closing });
    };
    const printed: string[] = [];
    vi.spyOn(window, "print").mockImplementation(() => {
      printed.push(document.querySelector(".print-area")?.textContent ?? "");
    });
    const requests = mockApi(all);
    const { user } = renderApp("/cash");

    await user.click(await screen.findByRole("button", { name: "Clôturer la caisse" }));
    await user.type(await screen.findByLabelText("Argent compté en USD"), "2645");
    await user.type(screen.getByLabelText("Argent compté en FC"), "480000");
    expect(screen.getByText(/Écart constaté : − 5,00\s\$/)).toBeTruthy();
    await user.click(screen.getByRole("checkbox"));
    const submit = screen.getByRole("button", { name: /Clôturer et imprimer/ });
    await user.click(submit);
    expect(screen.getByText("Obligatoire quand il y a un écart.")).toBeTruthy();
    expect(requests.some((request) => request.method === "POST")).toBe(false);

    await user.type(
      screen.getByLabelText(/Explication de l'écart/),
      "Billet déchiré rendu au parent",
    );
    await user.click(submit);

    expect(await screen.findByText("Caisse 2 clôturée")).toBeTruthy();
    const [sent] = requests.filter((request) => request.method === "POST");
    expect(sent?.body).toEqual({
      counted: [
        { currency: "USD", amount_minor: 264500 },
        { currency: "CDF", amount_minor: 480000 },
      ],
      note: "Billet déchiré rendu au parent",
    });
    await waitFor(() => expect(printed).toHaveLength(1));
    expect(printed[0]).toContain("Bordereau de clôture · Caisse 2");
    expect(printed[0]).toMatch(/Écart USD− 5,00\s\$/);
    await user.click(screen.getByRole("button", { name: "Terminer" }));
    expect(await screen.findByRole("button", { name: /Ouvrir la caisse C2/ })).toBeTruthy();
  });
});
