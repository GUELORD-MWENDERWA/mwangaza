import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const CREDIT = id(1);
const credit = {
  id: CREDIT,
  enrollment: id(80),
  student: { id: id(70), full_name: "SAFARI BIRINGANINE Patrick", matricule: "ITIG-2026-0179" },
  class_group: "2e Mécanique auto A",
  origin: "offline_surplus",
  amount_minor: 12000,
  currency: "USD",
  used_minor: 0,
  remaining_minor: 12000,
  state: "to_process",
  created_at: "2026-10-19T09:06:00Z",
  voided_at: null,
  receipt_number: "ITIG-C2-26-000101",
  cash_register_name: "Caisse 2",
  paid_at: "2026-10-19T07:51:00Z",
  discount_reason: null,
  discount_fee_type: null,
};
const part = {
  student_charge: id(501),
  fee_type_name: "Minerval",
  label: "2e tranche",
  due_on: "2027-01-15",
  amount_minor: 12000,
};
const detail = { ...credit, allocations: [], proposal: [part] };
const used = {
  ...detail,
  state: "used",
  used_minor: 12000,
  remaining_minor: 0,
  proposal: [],
  allocations: [
    {
      ...part,
      created_at: "2026-10-19T10:00:00Z",
      created_by: { id: id(2), last_name: "Kasereka", middle_name: "", first_name: "Paluku" },
    },
  ],
};

function routes(role: "head" | "promoter", extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me(role),
    "GET /api/student-credits/": { count: 1, next: null, previous: null, results: [credit] },
    "GET /api/student-credits/summary/": {
      to_process: 1,
      amounts: [{ currency: "USD", amount_minor: 12000 }],
      used_this_month: 0,
    },
    [`GET /api/student-credits/${CREDIT}/`]: detail,
    ...extra,
  };
}

describe("Crédits d'élèves (M14)", () => {
  it("le comptable utilise le crédit sur l'échéance proposée, sans encaisser", async () => {
    const all = routes("head");
    all[`POST /api/student-credits/${CREDIT}/use/`] = () => {
      all[`GET /api/student-credits/${CREDIT}/`] = used;
      return used;
    };
    const requests = mockApi(all);
    const { user } = renderApp("/credits");

    await screen.findByText("Minerval 2e tranche 120,00 $ (sur 120,00 $)");
    await user.click(screen.getByRole("button", { name: "Utiliser le crédit" }));

    await screen.findByRole("button", { name: "Imprimer le justificatif" });
    const sent = requests.filter((request) => request.method === "POST");
    expect(sent.map((request) => request.path)).toEqual([`/api/student-credits/${CREDIT}/use/`]);
    expect(screen.queryByRole("button", { name: "Utiliser le crédit" })).toBeNull();
  });

  it("sans le droit d'annulation, le crédit se lit mais ne s'utilise pas", async () => {
    mockApi(routes("promoter"));
    renderApp("/credits");

    const panel = (await screen.findByText("Utiliser sur les prochaines échéances")).closest(
      "div",
    )!.parentElement!;
    within(panel).getByText("Rendre l'argent au parent");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Utiliser le crédit" })).toBeNull(),
    );
  });
});
