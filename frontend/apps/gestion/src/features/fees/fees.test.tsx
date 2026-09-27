import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const year = {
  id: id(1),
  name: "2026-2027",
  starts_on: "2026-09-01",
  ends_on: "2027-07-02",
  is_current: true,
  status: "open",
  terms: [],
};
const feeType = (n: number, name: string, extra = {}) => ({
  id: id(n),
  name,
  category: "tuition",
  funds_teacher_bonus: false,
  accounting_code: "",
  is_active: true,
  rule_count: 0,
  ...extra,
});
const tranche = (n: number, due_on: string) => ({
  id: id(90 + n),
  label: n === 1 ? "1re tranche" : `${n}e tranche`,
  amount_minor: 12000,
  due_on,
  order: n - 1,
});
const minerval3e = {
  id: id(81),
  academic_year: year.id,
  fee_type: id(71),
  level: id(32),
  track: null,
  class_group: null,
  scope_name: "3e",
  currency: "USD",
  total_amount_minor: 36000,
  schedule_kind: "installments",
  installments: [tranche(1, "2026-10-15"), tranche(2, "2027-01-15"), tranche(3, "2027-04-15")],
};
const rate = {
  id: id(61),
  academic_year: year.id,
  rate: "2850.000000",
  reason: "",
  set_by: { id: id(100), last_name: "Paluku", middle_name: "", first_name: "Jean" },
  set_at: "2026-09-01T05:35:00Z",
};

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/academic-years/": [year],
    "GET /api/levels/": [
      { id: id(31), name: "7e EB", cycle: "basic", order: 0 },
      { id: id(32), name: "3e", cycle: "secondary_technical", order: 1 },
    ],
    "GET /api/tracks/": [],
    "GET /api/class-groups/": [],
    "GET /api/fee-types/": [
      feeType(71, "Minerval", { accounting_code: "706", rule_count: 1 }),
      feeType(72, "Motivation des enseignants", { category: "custom", funds_teacher_bonus: true }),
    ],
    "GET /api/fee-rules/": [minerval3e],
    "GET /api/exchange-rates/": [rate],
    ...extra,
  };
}

const sent = (requests: ReturnType<typeof mockApi>, method: string) =>
  requests.filter((request) => request.method === method);

describe("Frais et barèmes (E1, E2, E5)", () => {
  it("barème : rien n'est envoyé tant que les tranches ne font pas le total ; montants en entiers", async () => {
    const requests = mockApi(routes({ [`PUT /api/fee-rules/${id(81)}/`]: minerval3e }));
    const { user } = renderApp("/fees");

    const row = await screen.findByRole("row", { name: /^3e/ });
    expect(row.textContent).toContain("360,00\u00a0$");
    expect(row.textContent).toContain("3 × 120,00\u00a0$");
    await user.click(within(row).getByRole("button", { name: "Modifier" }));
    const first = await screen.findByLabelText("Montant de la ligne 1");
    await user.clear(first);
    await user.type(first, "110,00");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(
      await screen.findByText("La somme des tranches doit égaler le total annuel."),
    ).toBeTruthy();
    expect(sent(requests, "PUT")).toEqual([]);

    const second = screen.getByLabelText("Montant de la ligne 2");
    await user.clear(second);
    await user.type(second, "130");
    expect(screen.getByText("✓ égal au total annuel")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(sent(requests, "PUT")).toHaveLength(1));
    expect(sent(requests, "PUT")[0]!.body).toMatchObject({
      level: id(32),
      track: null,
      class_group: null,
      currency: "USD",
      total_amount_minor: 36000,
      schedule_kind: "installments",
      installments: [
        { label: "1re tranche", amount_minor: 11000, due_on: "2026-10-15" },
        { label: "2e tranche", amount_minor: 13000, due_on: "2027-01-15" },
        { label: "3e tranche", amount_minor: 12000, due_on: "2027-04-15" },
      ],
    });
  });

  it("mensuel en FC : un mois par ligne de septembre à juin, total réparti sans perte", async () => {
    const requests = mockApi(routes({ "POST /api/fee-rules/": minerval3e }));
    const { user } = renderApp("/fees");

    await user.click(await screen.findByRole("button", { name: /Motivation des enseignants/ }));
    await user.click(screen.getByRole("button", { name: "Barème" }));
    await user.selectOptions(await screen.findByLabelText("Devise"), "CDF");
    await user.type(screen.getByLabelText(/Total annuel/), "100 001");
    await user.click(screen.getByRole("radio", { name: "Mensuel" }));
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(sent(requests, "POST")).toHaveLength(1));
    const body = sent(requests, "POST")[0]!.body as {
      currency: string;
      total_amount_minor: number;
      installments: { label: string; amount_minor: number; due_on: string }[];
    };
    expect(body).toMatchObject({
      academic_year: year.id,
      fee_type: id(72),
      level: null,
      currency: "CDF",
      total_amount_minor: 100001,
      schedule_kind: "monthly",
    });
    expect(body.installments).toHaveLength(10);
    expect(body.installments[0]).toEqual({
      label: "Septembre",
      amount_minor: 10001,
      due_on: "2026-09-10",
    });
    expect(body.installments[9]).toMatchObject({ label: "Juin", due_on: "2027-06-10" });
    expect(body.installments.reduce((total, line) => total + line.amount_minor, 0)).toBe(100001);
  });

  it("taux de l'année : une correction demande son motif", async () => {
    const requests = mockApi(routes({ "POST /api/exchange-rates/": rate }));
    const { user } = renderApp("/fees");

    expect(await screen.findByText(/^1 \$ = 2\s850 FC$/)).toBeTruthy();
    await user.type(screen.getByLabelText(/Nouveau taux/), "2 875,5");
    await user.click(screen.getByRole("button", { name: "Corriger le taux" }));
    expect(await screen.findByText("Donnez le motif de la correction.")).toBeTruthy();
    expect(sent(requests, "POST")).toEqual([]);

    await user.type(screen.getByLabelText(/Motif de la correction/), "Erreur de saisie");
    await user.click(screen.getByRole("button", { name: "Corriger le taux" }));

    await waitFor(() => expect(sent(requests, "POST")).toHaveLength(1));
    expect(sent(requests, "POST")[0]!.body).toEqual({
      academic_year: year.id,
      rate: "2875.5",
      reason: "Erreur de saisie",
    });
  });

  it("avec seulement le droit d'accorder des réductions : lecture seule", async () => {
    const reader = me("head");
    reader.school!.permissions = ["finance.grant_discount"];
    mockApi(routes({ "GET /api/me/": reader }));
    renderApp("/fees");

    expect(await screen.findByRole("row", { name: /^3e/ })).toBeTruthy();
    expect(await screen.findByText(/^1 \$ = 2\s850 FC$/)).toBeTruthy();
    for (const name of ["Type de frais", "Barème", "Modifier", "Corriger le taux"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });
});
