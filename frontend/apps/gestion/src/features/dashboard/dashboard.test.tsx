import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const cashier = { id: id(5), last_name: "Kahindo", middle_name: "", first_name: "Grâce" };
const session = {
  id: id(6),
  cash_register: { id: id(7), name: "Caisse 2", code: "C2", is_active: true },
  cashier,
  opened_at: "2026-10-18T05:42:00Z",
  closed_at: null,
};
const amounts = (usd: number, cdf: number, counts = [0, 0]) => [
  { currency: "USD", amount_minor: usd, count: counts[0] },
  { currency: "CDF", amount_minor: cdf, count: counts[1] },
];

const dashboard = {
  date: "2026-10-19",
  academic_year: "2026-2027",
  today: amounts(284500, 1260000, [20, 12]),
  month: amounts(4832000, 21450000),
  previous_month: amounts(4314000, 18000000),
  daily: [{ date: "2026-10-19", amounts: amounts(284500, 1260000) }],
  overdue: amounts(6145000, 8910000),
  overdue_students: 412,
  recovery_percent: 71,
  enrolled: 1187,
  male: 1071,
  female: 116,
  classes: [
    {
      id: id(31),
      name: "2e Mécanique auto A",
      track: "Mécanique automobile",
      cycle: "secondary_technical",
      enrolled: 41,
      male: 40,
      female: 1,
      recovery_percent: 49,
    },
  ],
  recent_payments: [],
  alerts: {
    pending_cancellations: 2,
    unclosed: [session],
    differences: [
      {
        id: id(8),
        cash_session: session,
        currency: "USD",
        difference_minor: -1500,
        closed_at: "2026-10-17T15:00:00Z",
      },
    ],
    cancellations: [{ cashier, date: "2026-10-18", count: 4 }],
  },
};

const render = (role: "head" | "promoter") => {
  mockApi({
    "GET /api/school/": school,
    "GET /api/me/": me(role),
    "GET /api/dashboard/": dashboard,
  });
  return renderApp("/dashboard");
};

describe("Tableau de bord (G3)", () => {
  it("montants par devise jamais additionnés, alertes de l'école, classe vers ses impayés", async () => {
    render("head");

    const today = (await screen.findByText("Encaissé aujourd'hui")).parentElement!;
    within(today).getByText("2 845,00 $");
    within(today).getByText("+ 1 260 000 FC · 32 paiements");
    screen.getByText("+ 21 450 000 FC · ▲ 12 % vs septembre 2026");
    screen.getByText("71 %");

    screen.getByText("2 annulations attendent une validation.");
    screen.getByText(/pas clôturée : ouverte le 18\/10\/2026 à 07:42 par Grâce Kahindo/);
    screen.getByText(/écart de −15,00 \$ à la clôture du 17\/10\/2026/);
    screen.getByText(/a demandé 4 annulations le 18\/10\/2026/);
    expect(screen.getAllByRole("link", { name: "Voir" })).toHaveLength(4);

    const link = screen.getByRole("link", { name: "Impayés de 2e Mécanique auto A" });
    expect(link.getAttribute("href")).toMatch(new RegExp(`/unpaid\\?class_group=${id(31)}$`));
  });

  it("le promoteur (lecture seule) n'a de lien que vers les clôtures, pas vers les annulations", async () => {
    render("promoter");

    await screen.findByText("2 annulations attendent une validation.");
    const links = screen.getAllByRole("link", { name: "Voir" });
    expect(links.map((link) => link.getAttribute("href"))).toEqual(
      Array(2).fill(expect.stringMatching(/\/cash-closings$/)),
    );
  });
});
