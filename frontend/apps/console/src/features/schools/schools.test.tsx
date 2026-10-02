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
  status: "active",
  plan: "Standard",
  trial_ends_on: null,
  paid_until: "2027-06-30",
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
    const { user } = renderApp("/schools/new");

    const [name, headName] = await screen.findAllByLabelText("Nom");
    await user.type(name!, "Institut Gamma");
    await user.type(screen.getByLabelText("Code (adresse)"), "admin");
    await user.type(screen.getByLabelText("Téléphone"), "0000003001");
    await user.type(headName!, "Kasereka");
    await user.click(screen.getByRole("button", { name: "Créer l'école" }));

    // Refus du serveur placé sous le champ.
    expect(await screen.findByText("Ce code est réservé par la plateforme.")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toMatchObject({
      code: "admin",
      status: "trial",
      paid_until: null,
      enabled_currencies: ["USD", "CDF"],
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
});
