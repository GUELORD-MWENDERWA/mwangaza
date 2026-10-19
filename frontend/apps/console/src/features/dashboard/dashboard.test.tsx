import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OWNER, apiError, mockApi, renderApp } from "../../test/render";

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

const DASHBOARD = {
  day: "2026-10-02",
  schools: { active: 1, trial: 1, suspended: 0, trial_ending: 1 },
  students: 950,
  today: [
    { currency: "USD", amount_minor: 17000, count: 2 },
    { currency: "CDF", amount_minor: 10000, count: 1 },
  ],
  payments_today: 3,
  active_schools: [
    {
      id: "s1",
      code: "itig",
      name: "ITIG Don Bosco Goma",
      status: "trial",
      payments: 2,
      today: [
        { currency: "USD", amount_minor: 12000 },
        { currency: "CDF", amount_minor: 10000 },
      ],
    },
  ],
  health: {
    status: "error",
    checks: [
      { name: "database", status: "ok", value: 3 },
      { name: "redis", status: "error", value: null },
      { name: "workers", status: "off", value: null },
      { name: "disk", status: "warning", value: 18 },
      { name: "memory", status: "ok", value: 40 },
      { name: "swap", status: "warning", value: 62 },
    ],
  },
  platform: {
    containers: [
      {
        name: "django",
        used_mb: 752,
        limit_mb: 768,
        percent: 98,
        status: "error",
        oom_killed: false,
        restarted_at: "2026-10-13T08:30:00Z",
      },
      {
        name: "redis",
        used_mb: 4,
        limit_mb: 96,
        percent: 4,
        status: "ok",
        oom_killed: false,
        restarted_at: null,
      },
    ],
    print: { status: "warning", queued: 2, running: 1, longest_wait_seconds: 720 },
    scheduler: { status: "ok", last_tick_at: "2026-10-13T10:00:00Z", queue_size: 2 },
    backup: {
      status: "error",
      done_at: null,
      copied_status: "off",
      copied_at: null,
    },
    syncs: [{ id: "s1", code: "itig", name: "ITIG Don Bosco Goma", last_sync_at: null }],
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("console : tableau de bord", () => {
  it("montre chaque devise à part et le service en panne", async () => {
    mockApi({ "GET /api/me/": ADMIN, "GET /api/console/dashboard/": DASHBOARD });
    renderApp("/");

    const collected = (await screen.findByText("Encaissé aujourd'hui")).closest("section")!;
    // Dollars et francs jamais additionnés : les francs à part, sous les dollars.
    expect(within(collected).getByText(/170,00/)).toBeTruthy();
    expect(within(collected).getByText(/10 000 FC/)).toBeTruthy();
    expect(screen.getByText("Un service est en panne")).toBeTruthy();
    const redis = screen.getByText("Redis (file des tâches)").closest("li")!;
    expect(within(redis).getByText("en panne")).toBeTruthy();
    expect(screen.getByText("18 % libre")).toBeTruthy();
    // Nom clair, rôle en une phrase, nom technique en petit, redémarrage récent.
    const django = screen.getByText("Application web").closest("li")!;
    expect(within(django).getByText("django")).toBeTruthy();
    expect(within(django).getByText("752 / 768 Mo (98 %)")).toBeTruthy();
    expect(within(django).getByText("Ce que voient les écoles et les parents.")).toBeTruthy();
    expect(within(django).getByText(/Redémarré le/)).toBeTruthy();
    // « Que faire » déjà ouvert pour ce qui n'est pas vert.
    expect(
      within(redis)
        .getByText(/make deploy-logs service=redis/)
        .closest("details")!.open,
    ).toBe(true);
    expect(
      screen.getByText(/1 en cours · 2 en attente · attente la plus longue 12 min/),
    ).toBeTruthy();
    expect(screen.getByText("62 % utilisé")).toBeTruthy();
    // Une sauvegarde jamais notée se voit : jamais « bonne » sans preuve.
    const backup = screen.getByText("Dernière sauvegarde").closest("li")!;
    expect(within(backup).getByText("jamais notée")).toBeTruthy();
    // … et l'école qui ne s'est jamais synchronisée aussi.
    expect(screen.getAllByText("jamais notée")).toHaveLength(1);
    expect(screen.getByText("jamais synchronisée")).toBeTruthy();
  });

  it("renvoie vers la connexion sans session, puis demande le code", async () => {
    const requests = mockApi({
      "GET /api/me/": apiError("not_authenticated", 403),
      "GET /api/auth/login/": { step: "password" },
      "GET /api/auth/csrf/": new Response(null, { status: 204 }),
      "POST /api/auth/login/": { step: "totp" },
    });
    const { user } = renderApp("/");

    await user.type(await screen.findByLabelText("Numéro de téléphone"), "0000000000");
    await user.type(screen.getByLabelText("Mot de passe"), "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByLabelText("Code à 6 chiffres")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({
      phone: "0000000000",
      password: "secret",
    });
  });
});
