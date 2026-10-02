import { cleanup, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCOUNT } from "../../test/fixtures";
import { apiError, mockApi, renderApp } from "../../test/render";

describe("guide du parent (M20)", () => {
  it("après l'activation : 3 étapes, puis « Installer » ; relancé depuis le profil, « Passer » ramène à l'accueil", async () => {
    // Le serveur ouvre la session à l'activation.
    let session = false;
    mockApi({
      "GET /api/portal/me/": () => (session ? ACCOUNT : apiError("not_authenticated", 403)),
      "GET /api/auth/csrf/": {},
      "POST /api/portal/auth/activate/": () => ((session = true), ACCOUNT),
    });
    const first = renderApp("/activate");
    await first.user.type(await screen.findByLabelText("Numéro de téléphone"), "0971234567");
    await first.user.type(screen.getByLabelText("Code famille"), "k7m4-p9tx");
    await first.user.type(screen.getByLabelText("Choisissez un mot de passe"), "Lac-Kivu-2026");
    await first.user.click(screen.getByRole("button", { name: "Activer mon compte" }));

    expect(await screen.findByText(/Votre compte famille est activé/)).toBeTruthy();
    for (const title of ["Vos enfants", "Paiements et reçus", "Annonces et coordonnées"]) {
      expect(screen.getByRole("heading", { name: title })).toBeTruthy();
      await first.user.click(screen.getByRole("button", { name: /Suivant|Commencer/ }));
    }
    expect(first.router.state.location.pathname).toBe("/install");
    cleanup();

    mockApi({ "GET /api/portal/me/": ACCOUNT, "GET /api/portal/families/": [] });
    const again = renderApp("/guide");
    expect(await screen.findByText("L'essentiel du portail en 3 étapes.")).toBeTruthy();
    await again.user.click(screen.getByRole("button", { name: "Passer" }));
    expect(again.router.state.location.pathname).toBe("/");
  });
});
