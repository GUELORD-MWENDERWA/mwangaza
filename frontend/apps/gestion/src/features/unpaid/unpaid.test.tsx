import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const CLASS = { id: id(31), name: "3e Électricité A" };
const safari = {
  enrollment: id(1),
  student: {
    id: id(11),
    full_name: "Patrick Biringanine Safari",
    matricule: "ITIG-2026-0179",
    last_name: "Safari",
    middle_name: "Biringanine",
    first_name: "Patrick",
  },
  class_group: "2e Mécanique auto A",
  charges: [
    {
      fee_type_name: "Minerval",
      label: "1re tranche",
      due_on: "2026-10-15",
      currency: "USD",
      remaining_minor: 17500,
      days_late: 34,
    },
    {
      fee_type_name: "Motivation",
      label: "Septembre",
      due_on: "2026-09-10",
      currency: "CDF",
      remaining_minor: 60000,
      days_late: 39,
    },
  ],
  amounts: [
    { currency: "USD", overdue_minor: 17500 },
    { currency: "CDF", overdue_minor: 60000 },
  ],
  days_late: 39,
  guardian: { full_name: "Biringanine A.", phone: "+243827451360" },
  last_payment: {
    paid_at: "2026-09-02T08:00:00Z",
    received_amount_minor: 14000,
    received_currency: "USD",
  },
};

function routes(): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/unpaid/": { count: 1, next: null, previous: null, results: [safari] },
    "GET /api/unpaid/summary/": {
      students: 412,
      enrolled: 1187,
      amounts: [
        { currency: "USD", overdue_minor: 6145000 },
        { currency: "CDF", overdue_minor: 8910000 },
      ],
      long_overdue: 37,
      class_groups: [CLASS],
      fee_types: [{ id: id(41), name: "Minerval" }],
      installments: ["Septembre", "1re tranche"],
    },
  };
}

describe("Impayés (G1)", () => {
  it("montre ce qui est échu par devise, jamais additionné, et ouvre la fiche élève", async () => {
    mockApi(routes());
    renderApp("/unpaid");

    const row = (await screen.findByText("SAFARI BIRINGANINE Patrick")).closest("tr")!;
    within(row).getByText("175,00 $ + 60 000 FC");
    within(row).getByText("39 jours");
    within(row).getByText("Minerval 1re tranche + Motivation Septembre");
    within(row).getByText("02/09 · 140,00 $");
    expect(within(row).getByRole("link").getAttribute("href")).toMatch(
      new RegExp(`/students/${safari.student.id}/finances$`),
    );
    screen.getByText("61 450,00 $");
    screen.getByText("8 910 000 FC");
    screen.getByText("sur 1187 (35 %)");
  });

  it("les filtres choisis passent à la liste, aux chiffres, à l'Excel et à l'écran d'export", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/unpaid");

    const classes = await screen.findByRole("combobox", { name: "Classe" });
    await screen.findByRole("option", { name: "Classe : 3e Électricité A" });
    await user.selectOptions(classes, CLASS.id);
    await user.selectOptions(screen.getByRole("combobox", { name: "Retard" }), "30");

    await screen.findByRole("link", { name: "Excel" });
    const excel = screen.getByRole("link", { name: "Excel" }).getAttribute("href")!;
    expect(excel).toContain(`class_group=${CLASS.id}`);
    expect(excel).toContain("over_days=30");
    const filtered = requests.filter(
      (request) => request.query.class_group === CLASS.id && request.query.over_days === "30",
    );
    expect(new Set(filtered.map((request) => request.path))).toEqual(
      new Set(["/api/unpaid/", "/api/unpaid/summary/"]),
    );

    await user.click(screen.getByRole("link", { name: "PDF par classe" }));
    await screen.findByText(
      "Les filtres de la liste des impayés sont repris : 3e Électricité A · tous les frais · Retard : plus de 30 jours.",
    );
    const preview = screen.getByTitle("Aperçu de la liste des impayés").getAttribute("src")!;
    expect(preview).toContain(`class_group=${CLASS.id}`);
    expect(preview).toContain("output=html");
  });
});
