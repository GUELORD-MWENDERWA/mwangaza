import { screen } from "@testing-library/react";
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

const USE = {
  code: "timetable_constraints",
  label: "Règles de l'horaire en phrases",
  module: "timetable",
  module_label: "Emploi du temps",
  model: "claude-opus-5-5",
  max_input_tokens: 6000,
  max_output_tokens: 3000,
  changed: false,
  calls: 96,
  kept_percent: 64,
  abandoned: 6,
  cost_micro: 1_680_000,
};

const OVERVIEW = {
  month: "2026-11-01",
  live: true,
  spent_micro: 12_400_000,
  cap_micro: 50_000_000,
  calls: 96,
  refused: 2,
  errors: 0,
  kept_percent: 64,
  schools_with_ai: 1,
  schools_paused: 0,
  alerts: [{ kind: "school_credits", percent: 84, id: "s1", name: "Institut Les Volcans" }],
  schools: [
    {
      id: "s1",
      code: "volcans",
      name: "Institut Les Volcans",
      uses: 1,
      paused: false,
      granted_credits: 2000,
      spent_credits: 1680,
      remaining_credits: 320,
      calls: 96,
      kept_percent: 64,
    },
  ],
  uses: [USE],
  settings: {
    enabled: true,
    monthly_cap_micro: 50_000_000,
    hourly_limit: 20,
    prices: [
      {
        model: "claude-opus-5-5",
        input: 4_000_000,
        output: 20_000_000,
        cache_read: 200_000,
        changed: false,
      },
    ],
  },
};

describe("Page « IA » de la console (IA.1.2)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("montre la dépense face au plafond, les écoles et les réglages en mode réel", async () => {
    mockApi({ "GET /api/me/": ADMIN, "GET /api/console/ai/": OVERVIEW });
    renderApp("/ai");
    expect(await screen.findByText(/12,40/)).toBeTruthy();
    expect(screen.getByText(/sur un plafond de 50,00/)).toBeTruthy();
    expect(screen.getAllByText("Institut Les Volcans").length).toBe(2); // alerte et tableau
    expect(screen.getByText("IA allumée")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Modifier" })).toBeTruthy();
  });

  it("en démonstration : ni plafond, ni réglages, ni bouton pour changer un usage", async () => {
    mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/ai/": {
        ...OVERVIEW,
        live: false,
        cap_micro: null,
        settings: null,
        alerts: [],
      },
    });
    renderApp("/ai", "demo");
    expect(await screen.findByText(/crédits fictifs/)).toBeTruthy();
    expect(screen.queryByText("IA allumée")).toBeNull();
    expect(screen.queryByRole("button", { name: "Modifier" })).toBeNull();
  });

  it("le menu n'offre « IA » qu'avec le droit de l'IA", async () => {
    mockApi({
      "GET /api/me/": {
        ...ADMIN,
        platform_roles: ["communication"],
        platform_permissions: ["platform.site.edit", "platform.news.publish"],
      },
    });
    renderApp("/site");
    await screen.findAllByText("Site public");
    expect(screen.queryByRole("link", { name: "IA" })).toBeNull();
  });
});
