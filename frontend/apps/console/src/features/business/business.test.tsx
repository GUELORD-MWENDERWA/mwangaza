import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OWNER, mockApi, renderApp } from "../../test/render";

const ADMIN = {
  id: "a1",
  phone: "+243000000000",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
  ...OWNER,
};

const BUSINESS = {
  day: "2026-11-03",
  schools: { trial: 3, active: 9, readonly: 2, suspended: 0, stopped: 1 },
  trials_ending: 1,
  billed_students: 11480,
  money: [
    { currency: "USD", invoiced: 540000, collected: 315000, outstanding: 427500, overdue: 120000 },
    { currency: "CDF", invoiced: 0, collected: 0, outstanding: 5000000, overdue: 0 },
  ],
  renewals: {
    count: 1,
    items: [
      {
        school_id: "s1",
        code: "bahati",
        name: "Institut Bahati",
        end_date: "2026-11-20",
        auto_renew: false,
      },
    ],
  },
  prospects_open: 7,
};

afterEach(() => vi.unstubAllGlobals());

describe("console : affaires", () => {
  it("montre chaque devise à part, les contrats à renouveler et les exports permis", async () => {
    mockApi({ "GET /api/me/": ADMIN, "GET /api/console/business/": BUSINESS });
    renderApp("/business");

    const table = (await screen.findByText("Ce mois-ci, par devise")).closest("section")!;
    expect(within(table).getByText(/5 400,00/)).toBeTruthy();
    // Les francs ne s'ajoutent jamais aux dollars : leur propre ligne.
    expect(within(table).getByText(/5 000 000 FC/)).toBeTruthy();
    expect(screen.getByText("Institut Bahati")).toBeTruthy();
    expect(screen.getByText("11 480")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Factures (Excel)" })).toBeTruthy();
  });

  it("n'affiche pas une section que le serveur n'a pas envoyée (commercial)", async () => {
    mockApi({
      "GET /api/me/": {
        ...ADMIN,
        platform_roles: ["commercial"],
        platform_permissions: ["platform.leads.manage", "platform.demos.manage"],
      },
      "GET /api/console/business/": {
        ...BUSINESS,
        schools: null,
        trials_ending: null,
        billed_students: null,
        money: null,
        renewals: null,
      },
    });
    renderApp("/business");

    expect(await screen.findByText("Prospects ouverts")).toBeTruthy();
    expect(screen.queryByText("Écoles payantes")).toBeNull();
    expect(screen.queryByText("Ce mois-ci, par devise")).toBeNull();
    expect(screen.queryByRole("link", { name: "Factures (Excel)" })).toBeNull();
  });
});
