import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ITIG } from "../../test/fixtures";
import { apiError, mockApi, renderApp } from "../../test/render";
import { codeFromLink } from "./ActivatePage";

const ACCOUNT = { id: "01", phone: "+243971234567", name: "Kahindo Neema", language: "fr" };
const LOGGED_OUT = apiError("not_authenticated", 403);

describe("accès au portail", () => {
  it("sans session, mène à la connexion ; connecté, à l'accueil du compte", async () => {
    const requests = mockApi({
      "GET /api/portal/me/": LOGGED_OUT,
      "GET /api/auth/csrf/": {},
      "POST /api/portal/auth/login/": ACCOUNT,
      "GET /api/portal/families/": [],
    });
    const { user, router } = renderApp("/");

    await screen.findByRole("heading", { name: "Se connecter" });
    expect(router.state.location.pathname).toBe("/login");
    await user.type(screen.getByLabelText("Numéro de téléphone"), "0971234567");
    await user.type(screen.getByLabelText("Mot de passe"), "Lac-Kivu-2026");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    await screen.findByRole("heading", { name: "Mes enfants" });
    expect(screen.getByText("Bonjour, Kahindo Neema")).toBeTruthy();
    expect(requests.find((r) => r.path === "/api/portal/auth/login/")?.body).toEqual({
      phone: "0971234567",
      password: "Lac-Kivu-2026",
      remember: true,
    });
  });

  it("session finie en cours d'usage : numéro rempli, message, retour à la page demandée ; déconnexion : rien de gardé", async () => {
    let session = false;
    const guarded = (body: object) => () => (session ? body : LOGGED_OUT);
    mockApi({
      "GET /api/portal/me/": guarded(ACCOUNT),
      "GET /api/auth/csrf/": {},
      "POST /api/portal/auth/login/": () => ((session = true), ACCOUNT),
      "GET /api/portal/families/": guarded([ITIG]),
      "GET /api/portal/announcements/": guarded({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
      "POST /api/auth/logout/": () => ((session = false), new Response(null, { status: 204 })),
    });
    const { user, router } = renderApp("/login");
    const phone = () => screen.getByLabelText<HTMLInputElement>("Numéro de téléphone");
    const logIn = async () => {
      await user.type(screen.getByLabelText("Mot de passe"), "Lac-Kivu-2026");
      await user.click(screen.getByRole("button", { name: "Se connecter" }));
    };
    await user.type(await screen.findByLabelText("Numéro de téléphone"), "0971234567");
    await logIn();
    await screen.findByRole("heading", { name: "Mes enfants" });

    session = false; // le serveur ne reconnaît plus le compte
    await user.click(await screen.findByRole("link", { name: "Annonces" }));
    await screen.findByText("Votre session est terminée. Reconnectez-vous pour continuer.");
    expect(phone().value).toBe(ACCOUNT.phone);
    await logIn();
    await waitFor(() => expect(router.state.location.pathname).toBe("/announcements"));

    await user.click(await screen.findByRole("link", { name: "Accueil" }));
    await user.click(await screen.findByRole("button", { name: "Se déconnecter" }));
    await screen.findByRole("heading", { name: "Se connecter" });
    expect(phone().value).toBe("");
    expect(screen.queryByText(/session est terminée/)).toBeNull();
  });

  it("réseau coupé au retour dans l'application : la page reste, pas de retour à la connexion", async () => {
    let offline = false;
    const online = (body: object) => () => {
      if (offline) throw new TypeError("Failed to fetch");
      return body;
    };
    const requests = mockApi({
      "GET /api/portal/me/": online(ACCOUNT),
      "GET /api/portal/families/": online([]),
    });
    const { router } = renderApp("/");
    await screen.findByRole("heading", { name: "Mes enfants" });

    offline = true;
    window.dispatchEvent(new Event("visibilitychange"));
    await waitFor(() =>
      expect(requests.filter((r) => r.path === "/api/portal/me/")).toHaveLength(2),
    );
    await screen.findByText("Pas de connexion au serveur. Vérifiez internet et réessayez.");
    expect(screen.getByRole("heading", { name: "Mes enfants" })).toBeTruthy();
    expect(router.state.location.pathname).toBe("/");
  });

  it("activation refusée : l'erreur du serveur traduite, et sous le champ quand elle le vise", async () => {
    const refusals = [
      apiError("invalid_family_code", 400),
      apiError("invalid", 400, { phone: [{ code: "invalid_phone", message: "" }] }),
    ];
    mockApi({
      "GET /api/portal/me/": LOGGED_OUT,
      "GET /api/auth/csrf/": {},
      "POST /api/portal/auth/activate/": () => refusals.shift()!,
    });
    const { user } = renderApp("/activate");

    await user.type(await screen.findByLabelText("Numéro de téléphone"), "0971234567");
    await user.type(screen.getByLabelText("Code famille"), "k7m4-p9tx");
    await user.type(screen.getByLabelText("Choisissez un mot de passe"), "Lac-Kivu-2026");
    await user.click(screen.getByRole("button", { name: "Activer mon compte" }));
    await screen.findByText("Numéro de téléphone ou code famille incorrect.");

    await user.click(screen.getByRole("button", { name: "Activer mon compte" }));
    expect((await screen.findByText(/Numéro invalide/)).id).toBe("phone-error");
  });

  it("code de la lettre d'invitation (après « # ») prérempli s'il a 8 caractères, sinon rien", () => {
    expect(codeFromLink("#k7qm3hpv")).toBe("K7QM-3HPV");
    expect(codeFromLink("#K7QM-3HPV")).toBe("K7QM-3HPV");
    expect(codeFromLink("#abc")).toBe("");
    expect(codeFromLink("")).toBe("");
  });
});
