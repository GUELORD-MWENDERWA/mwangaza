import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const year = id(900);

function routes(): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/academic-years/": [{ id: year, name: "2026-2027", is_current: true }],
    "GET /api/budget/": {
      academic_year: year,
      currency: "USD",
      currencies: ["USD", "CDF"],
      planned_minor: 480000,
      spent_minor: 600000,
      budget: [
        {
          category: id(1),
          name: "Atelier mécanique",
          is_active: true,
          planned_minor: 300000,
          spent_minor: 124000,
        },
        {
          category: id(2),
          name: "Fournitures",
          is_active: true,
          planned_minor: 120000,
          spent_minor: 139000,
        },
        { category: id(3), name: "Entretien", is_active: true, planned_minor: 0, spent_minor: 0 },
      ],
      months: [],
      accounts: [],
    },
    "PUT /api/budget/": {},
  };
}

describe("Budget et rapports (FIN.3)", () => {
  it("signale le dépassement et n'envoie au serveur que les lignes changées", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/budget");

    const over = (await screen.findByText("Fournitures")).closest("tr")!;
    within(over).getByText("Dépassé");
    within(over).getByText("116 %");
    within(screen.getByText("Atelier mécanique").closest("tr")!).getByText("Dans le budget");

    await user.click(screen.getByRole("button", { name: "Régler le budget" }));
    const field = screen.getByLabelText("Prévu pour Entretien");
    await user.type(field, "250");
    await user.click(screen.getByRole("button", { name: "Enregistrer le budget" }));

    const put = requests.find((r) => r.method === "PUT" && r.path === "/api/budget/")!;
    expect(put.body).toEqual({
      academic_year: year,
      currency: "USD",
      lines: [{ category: id(3), amount_minor: 25000 }],
    });
  });
});
