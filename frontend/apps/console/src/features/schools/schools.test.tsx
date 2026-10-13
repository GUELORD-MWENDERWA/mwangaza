import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, mockApi, renderApp } from "../../test/render";

const ADMIN = {
  id: "a1",
  phone: "+243000000000",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
};

const GAMMA = {
  id: "s1",
  code: "gamma",
  name: "Institut Gamma",
  official_name: "",
  url: "http://gamma.localhost:5173",
  environment: "live",
  status: "active",
  plan: "Standard",
  trial_ends_on: null,
  paid_until: "2027-06-30",
  modules: ["students"],
  enabled_currencies: ["USD", "CDF"],
  default_currency: "USD",
  student_count: 0,
  last_activity_at: null,
  created_at: "2026-10-03T08:00:00Z",
  history: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("Écoles de la console", () => {
  it("crée l'école avec son directeur et montre une seule fois le mot de passe provisoire", async () => {
    let refuse = true;
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "POST /api/console/schools/": () =>
        refuse
          ? apiError("invalid", 400, { code: [{ code: "reserved", message: "x" }] })
          : {
              school: GAMMA,
              head: {
                id: "u1",
                phone: "+243000003001",
                last_name: "Kasereka",
                middle_name: "",
                first_name: "Dieudonné",
              },
              temporary_password: "kivu-lac-42",
            },
    });
    const { user } = renderApp("/schools/new?type=test");

    const [name, headName] = await screen.findAllByLabelText("Nom");
    await user.type(name!, "Institut Gamma");
    await user.type(screen.getByLabelText("Code (adresse)"), "admin");
    await user.type(screen.getByLabelText("Téléphone"), "0000003001");
    await user.type(headName!, "Kasereka");
    // Les six modules sont cochés d'office ; retirer les élèves retire ce qui en dépend.
    await user.click(screen.getByRole("checkbox", { name: "Élèves, familles et inscriptions" }));
    await user.click(screen.getByRole("button", { name: "Créer l'école" }));

    // Refus du serveur placé sous le champ.
    expect(await screen.findByText("Ce code est réservé par la plateforme.")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toMatchObject({
      code: "admin",
      // Type de l'onglet d'où l'on vient (`?type=test`).
      environment: "test",
      status: "trial",
      paid_until: null,
      enabled_currencies: ["USD", "CDF"],
      modules: ["communication", "notifications", "offline"],
      head: { phone: "0000003001", last_name: "Kasereka" },
    });

    refuse = false;
    const code = screen.getByLabelText("Code (adresse)");
    await user.clear(code);
    await user.type(code, "gamma");
    await user.click(screen.getByRole("button", { name: "Créer l'école" }));
    expect(await screen.findByText("kivu-lac-42")).toBeTruthy();
    expect(screen.getByText(/Affiché une seule fois/)).toBeTruthy();
  });

  it("donne un module à l'école et n'envoie que les modules", async () => {
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/schools/s1/": GAMMA,
      "PATCH /api/console/schools/s1/": { ...GAMMA, modules: ["students", "finance"] },
    });
    const { user } = renderApp("/schools/s1");

    await user.click(await screen.findByRole("checkbox", { name: "Frais, caisse et paiements" }));
    await user.click(screen.getAllByRole("button", { name: "Enregistrer" }).at(-1)!);

    expect(await screen.findByText("Modules enregistrés.")).toBeTruthy();
    const patch = requests.find((r) => r.method === "PATCH");
    expect(patch?.body).toEqual({ modules: ["students", "finance"] });
  });

  it("ne suspend une école qu'après confirmation", async () => {
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/schools/s1/": GAMMA,
      "POST /api/console/schools/s1/suspend/": {
        ...GAMMA,
        status: "suspended",
        history: [
          {
            id: "h1",
            created_at: "2026-10-03T09:00:00Z",
            action: "school.suspended",
            actor: ADMIN,
            before: { status: "active" },
            after: { status: "suspended" },
          },
        ],
      },
    });
    const { user } = renderApp("/schools/s1");

    expect(await screen.findByRole("link", { name: "Ouvrir en tant qu'école" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Suspendre" }));
    expect(requests.some((r) => r.method === "POST")).toBe(false);
    await user.click(await screen.findByRole("button", { name: "Suspendre" }));

    expect(
      await screen.findByText(/École suspendue : personne ne peut s'y connecter/),
    ).toBeTruthy();
    expect(requests.filter((r) => r.method === "POST")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Réactiver" })).toBeTruthy();
    // Plus de session support dans une école suspendue.
    expect(screen.queryByRole("link", { name: "Ouvrir en tant qu'école" })).toBeNull();
  });

  it("range les espaces par type et n'en arrête un qu'avec un motif", async () => {
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/dashboard/": apiError("not_found", 404),
      "GET /api/console/schools/": () => ({
        count: 1,
        next: null,
        previous: null,
        results: requests.at(-1)?.search.includes("environment=test")
          ? [{ ...GAMMA, id: "s2", name: "Essai Kivu", environment: "test" }]
          : [GAMMA],
      }),
      "GET /api/console/schools/s1/": GAMMA,
      "POST /api/console/schools/s1/stop/": { ...GAMMA, status: "stopped" },
    });
    const { user } = renderApp("/schools");

    expect(await screen.findByRole("link", { name: "Institut Gamma" })).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "Essai" }));
    expect(await screen.findByRole("link", { name: "Essai Kivu" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Institut Gamma" })).toBeNull();

    await user.click(screen.getByRole("tab", { name: "Réels" }));
    await user.click(await screen.findByRole("link", { name: "Gérer" }));
    await user.click(await screen.findByRole("button", { name: "Arrêter" }));
    // Un espace réel s'arrête, il ne se supprime pas.
    expect(screen.queryByRole("button", { name: "Supprimer" })).toBeNull();
    // Sans motif : rien n'est envoyé.
    await user.click(await screen.findByRole("button", { name: "Arrêter" }));
    expect(await screen.findByText("Indiquez le motif.")).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);

    await user.type(screen.getByLabelText("Motif"), "A quitté la plateforme");
    await user.click(screen.getByRole("button", { name: "Arrêter" }));

    expect(await screen.findByText(/Espace arrêté : personne ne peut s'y connecter/)).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({
      reason: "A quitté la plateforme",
    });
    // Arrêté : ni session support, ni « Arrêter » ; « Relancer » rattrape une erreur.
    expect(screen.getByRole("button", { name: "Relancer" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Ouvrir en tant qu'école" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Arrêter" })).toBeNull();
  });

  it("ne supprime un espace d'essai qu'une fois son code retapé", async () => {
    const ESSAI = { ...GAMMA, id: "s2", code: "kivu", name: "Essai Kivu", environment: "test" };
    let deleting = false;
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/schools/": () => ({
        count: 1,
        next: null,
        previous: null,
        results: [{ ...ESSAI, status: deleting ? "deleting" : "active" }],
      }),
      "GET /api/console/schools/s2/": ESSAI,
      "POST /api/console/schools/s2/delete/": () => {
        deleting = true;
        return new Response(null, { status: 204 });
      },
    });
    const { user } = renderApp("/schools/s2");

    await user.click(await screen.findByRole("button", { name: "Supprimer" }));
    const code = await screen.findByLabelText(/tapez le code de l'espace : kivu/);
    // Mauvais code : rien n'est envoyé.
    await user.type(code, "gamma");
    await user.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(await screen.findByText("Ce n'est pas le code de cet espace.")).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);

    await user.clear(code);
    await user.type(code, "Kivu");
    await user.click(screen.getByRole("button", { name: "Supprimer" }));

    // Retour à l'onglet « Essai », où l'espace attend la fin de la suppression.
    expect(await screen.findByText("Suppression en cours")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({ confirm: "kivu" });
    expect(requests.some((r) => r.search.includes("environment=test"))).toBe(true);
    expect(screen.queryByRole("link", { name: "Ouvrir en tant qu'école" })).toBeNull();
  });

  it("crée un espace de démonstration, suit son remplissage et le remet à zéro", async () => {
    const demo = (state: string, status = "active") => ({
      ...GAMMA,
      id: "d1",
      code: "vitrine",
      name: "Vitrine",
      environment: "demo",
      status,
      demonstration: { profile: "large", state, steps_done: 3, steps_total: 15 },
    });
    let reads = 0;
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "POST /api/console/schools/demo/": () => demo("filling"),
      "GET /api/console/schools/d1/": () => demo(reads++ ? "ready" : "filling"),
      "POST /api/console/schools/d1/reset/": () => demo("resetting", "deleting"),
    });
    const { user } = renderApp("/schools/new?type=demo");

    // Ni directeur, ni devises, ni abonnement : le serveur écrit tout.
    await user.type(await screen.findByLabelText("Nom"), "Vitrine");
    await user.type(screen.getByLabelText("Code (adresse)"), "vitrine");
    await user.click(screen.getByText("Grande école"));
    await user.click(screen.getByRole("button", { name: "Créer l'espace de démonstration" }));

    expect(await screen.findByText("Création en cours : étape 3 sur 15.")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")).toMatchObject({
      path: "/api/console/schools/demo/",
      body: { name: "Vitrine", code: "vitrine", profile: "large" },
    });
    // La fiche se relit seule : prête, elle donne la fiche d'accès.
    const sheet = await screen.findByRole("link", { name: "Fiche d'accès" }, { timeout: 6000 });
    expect(sheet.getAttribute("href")).toBe("/schools/d1/access");

    await user.click(screen.getByRole("button", { name: "Remettre à zéro" }));
    await screen.findByText(/le mot de passe change/);
    await user.click(screen.getByRole("button", { name: "Remettre à zéro" }));

    expect(await screen.findByText(/Remise à zéro en cours/)).toBeTruthy();
    expect(requests.filter((r) => r.method === "POST").at(-1)?.body).toEqual({
      confirm: "vitrine",
    });
  }, 15_000);
});
