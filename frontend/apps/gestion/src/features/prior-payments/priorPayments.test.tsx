import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { json, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const line = {
  line: 2,
  matricule: "ITIG-2026-0001",
  student: "KAMBALE Josué",
  class_group: "3e Électricité A",
  amount: "150",
  amount_minor: 15000,
  currency: "USD",
  fee: "",
  issues: [],
};
const preview = {
  recorded: false,
  ready_count: 1,
  error_count: 1,
  empty_count: 3,
  totals: [{ currency: "USD", amount_minor: 15000, count: 1 }],
  errors: [
    {
      ...line,
      line: 3,
      amount: "900",
      amount_minor: 90000,
      issues: [{ code: "more_than_due", due_minor: 36000, currency: "USD" }],
    },
  ],
  ready: [line],
};

function routes(role: Parameters<typeof me>[0]): Routes {
  return { "GET /api/school/": school, "GET /api/me/": me(role) };
}

describe("reprise en cours d'année (E6)", () => {
  it("n'ouvre l'écran qu'avec le droit finance.import_prior_payments", async () => {
    mockApi(routes("cashier"));
    renderApp("/fees/prior-payments");
    await screen.findByRole("navigation");
    expect(screen.queryByLabelText(/Fichier Excel/)).toBeNull();
  });

  it("montre les totaux et les erreurs, puis enregistre avec les totaux validés", async () => {
    const all: Routes = { ...routes("accountant"), "POST /api/prior-payments/": json(preview) };
    const requests = mockApi(all);
    const posted = () => requests.filter((request) => request.method === "POST");
    const { user } = renderApp("/fees/prior-payments");

    // `FormData` et fichier de Node : le `Request` de Node ne lit pas ceux de jsdom.
    const form = await new Response(new URLSearchParams("a=b")).formData();
    vi.stubGlobal("FormData", form.constructor);
    const blob = await new Response("xlsx").blob();
    const file = Object.assign(blob, { name: "reprise.xlsx" }) as unknown as File;
    await user.upload(await screen.findByLabelText(/Fichier Excel/), file);
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));

    // Rien n'est encore enregistré : l'erreur dit ce que doit l'élève, le total est à valider.
    expect(await screen.findByText(/Plus que ce que doit l'élève \(360,00/)).toBeTruthy();
    expect(String(posted()[0].body)).not.toContain('name="expected"');
    all["POST /api/prior-payments/"] = json({ ...preview, recorded: true }, 201);
    await user.click(screen.getByRole("button", { name: "Enregistrer 1 paiement" }));

    expect(await screen.findByText(/1 paiement enregistré/)).toBeTruthy();
    expect(posted()).toHaveLength(2);
    expect(String(posted()[1].body)).toContain(JSON.stringify(preview.totals));
  });
});
