import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, renderApp } from "../../test/render";

const ACCOUNT = { id: "01", phone: "+243971234567", name: "Kahindo Neema", language: "fr" };
const LOGGED_OUT = apiError("not_authenticated", 403);

describe("accès au portail", () => {
  it("sans session, mène à la connexion ; connecté, à l'accueil du compte", async () => {
    const requests = mockApi({
      "GET /api/portal/me/": LOGGED_OUT,
      "GET /api/auth/csrf/": {},
      "POST /api/portal/auth/login/": ACCOUNT,
    });
    const { user, router } = renderApp("/");

    await screen.findByRole("heading", { name: "Se connecter" });
    expect(router.state.location.pathname).toBe("/login");
    await user.type(screen.getByLabelText("Numéro de téléphone"), "0971234567");
    await user.type(screen.getByLabelText("Mot de passe"), "Lac-Kivu-2026");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    await screen.findByRole("heading", { name: "Bonjour, Kahindo Neema" });
    expect(requests.find((r) => r.path === "/api/portal/auth/login/")?.body).toEqual({
      phone: "0971234567",
      password: "Lac-Kivu-2026",
      remember: true,
    });
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
});
