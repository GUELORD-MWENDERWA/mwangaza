import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const cashier = { id: fakeId(1), last_name: "Zawadi", middle_name: "", first_name: "Alice" };
const payment = {
  id: fakeId(90),
  receipt_number: "ALPHA-C2-26-000098",
  enrollment: fakeId(80),
  student: { id: fakeId(30), full_name: "KATEMBO MALIRO Jonathan", matricule: "ALPHA-2026-0587" },
  class_group: "8e EB A",
  cash_register: "C2",
  cash_register_name: "Caisse 2",
  academic_year: "2026-2027",
  cash_session: fakeId(20),
  cashier,
  received_amount_minor: 8500,
  received_currency: "USD",
  rate_used: "2850.000000",
  paid_at: "2026-10-19T07:52:00Z",
  method: "cash",
  note: "",
  allocations: [
    {
      student_charge: fakeId(501),
      fee_type_name: "Minerval",
      label: "1re tranche",
      currency: "USD",
      due_on: "2026-10-15",
      received_minor: 8500,
      amount_minor: 8500,
    },
  ],
};
const request = {
  id: fakeId(60),
  payment,
  reason: "Mauvais élève sélectionné (homonyme)",
  requested_by: cashier,
  requested_at: "2026-10-19T07:58:00Z",
  offline: false,
  status: "pending",
  decided_by: null,
  decided_at: null,
  decision_note: "",
  cancellation: null,
};
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

describe("Annulations (F7)", () => {
  it("à la caisse, le caissier demande l'annulation avec un motif, envoyée une seule fois", async () => {
    const session = {
      id: fakeId(20),
      cash_register: { id: fakeId(12), name: "Caisse 2", code: "C2", is_active: true },
      cashier,
      opened_at: "2026-10-19T05:35:00Z",
      closed_at: null,
    };
    const listed = {
      ...payment,
      cancelled: false,
      cancelled_at: null,
      cancellation_pending: false,
    };
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("cashier"),
      "GET /api/cash-sessions/current/": {
        session,
        totals: [],
        rate: "2850.000000",
        rate_is_fallback: false,
      },
      "GET /api/payments/": page([listed]),
      "GET /api/student-charges/credits/": [],
      "POST /api/cancellations/": request,
    });
    const { user } = renderApp("/cash");

    await user.click(
      await screen.findByRole("button", {
        name: "Demander l'annulation du reçu ALPHA-C2-26-000098",
      }),
    );
    const dialog = await screen.findByRole("dialog");
    // Sans motif : refusé avant l'envoi.
    await user.click(within(dialog).getByRole("button", { name: "Envoyer la demande" }));
    expect(await within(dialog).findByText("Ce champ est obligatoire.")).toBeTruthy();
    await user.type(within(dialog).getByLabelText(/Motif/), "Mauvais élève sélectionné");
    await user.click(within(dialog).getByRole("button", { name: "Envoyer la demande" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const sent = requests.filter((item) => item.method === "POST");
    expect(sent.map((item) => item.body)).toEqual([
      { id: expect.any(String), payment: payment.id, reason: "Mauvais élève sélectionné" },
    ]);
  });

  it("le directeur valide avec un commentaire et le reçu d'annulation s'imprime", async () => {
    const approved = {
      ...request,
      status: "approved",
      decided_by: { id: fakeId(100), last_name: "Test", middle_name: "", first_name: "Aline" },
      decided_at: "2026-10-19T08:05:00Z",
      decision_note: "Argent rendu",
      cancellation: {
        receipt_number: "ALPHA-AN-26-000007",
        approved_by: { id: fakeId(100), last_name: "Test", middle_name: "", first_name: "Aline" },
        approved_at: "2026-10-19T08:05:00Z",
      },
      balance: {
        situation: "overdue",
        next_due_on: null,
        currencies: [{ currency: "USD", remaining_minor: 8500, overdue_minor: 8500 }],
      },
    };
    const printed: string[] = [];
    vi.spyOn(window, "print").mockImplementation(() => {
      printed.push(document.querySelector(".print-area")?.textContent ?? "");
    });
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/cancellations/": page([request]),
      [`POST /api/cancellations/${request.id}/approve/`]: approved,
    });
    const { user } = renderApp("/cancellations");

    await user.type(await screen.findByLabelText("Commentaire du validateur"), "Argent rendu");
    await user.click(screen.getByRole("button", { name: "Valider l'annulation" }));

    await waitFor(() => expect(printed).toHaveLength(1));
    expect(printed[0]).toContain("Reçu d'annulation n° ALPHA-AN-26-000007");
    expect(printed[0]).toContain("Annule le reçu ALPHA-C2-26-000098");
    expect(printed[0]).toContain("Quatre-vingt-cinq dollars américains");
    expect(printed[0]).toMatch(/Reste dû après annulation85,00\s\$/);
    const sent = requests.find((item) => item.method === "POST");
    expect(sent?.body).toEqual({ note: "Argent rendu" });
  });

  it("sa propre demande ne se valide pas ; sans le droit, pas de décision", async () => {
    const own = { ...request, requested_by: { ...cashier, id: me("head").id } };
    mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/cancellations/": page([own]),
    });
    renderApp("/cancellations");

    expect(await screen.findByText(/C'est votre demande/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Valider l'annulation" })).toBeNull();
  });
});
