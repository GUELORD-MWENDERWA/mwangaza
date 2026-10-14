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

const IDENTITY = {
  name: "Lampe",
  short_name: "Lampe",
  logo: null,
  icon: null,
  primary_color: "#0B5FCC",
  accent_color: "#F2B632",
  support_phone: "",
  support_email: "",
  legal_notice: "",
  updated_at: "2026-10-02T12:00:00Z",
  history: [
    {
      id: "h1",
      created_at: "2026-10-02T12:00:00Z",
      action: "platform.updated",
      actor: { id: "a1", last_name: "Mwenderwa", middle_name: "", first_name: "Guelord" },
      before: { support_phone: "" },
      after: { support_phone: "+243000000999" },
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("Identité de la plateforme", () => {
  it("enregistre la saisie et place le refus d'une couleur sous son champ", async () => {
    let refuse = true;
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/platform/": IDENTITY,
      "PATCH /api/console/platform/": () =>
        refuse
          ? apiError("invalid", 400, {
              accent_color: [{ code: "unreadable_color", message: "x" }],
            })
          : { ...IDENTITY, name: "Lumière", accent_color: "#FFD166" },
    });
    const { user } = renderApp("/identity");

    // Journal : la modification, avant → après.
    expect(
      await screen.findByText(/Téléphone du support : \(vide\) → \+243000000999/),
    ).toBeTruthy();
    const name = screen.getByLabelText("Nom");
    await user.clear(name);
    await user.type(name, "Lumière");
    const accent = screen.getByRole("textbox", { name: "Couleur d'accent" });
    await user.clear(accent);
    await user.type(accent, "#1E262C");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText(/Couleur trop sombre/)).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toMatchObject({
      name: "Lumière",
      accent_color: "#1E262C",
    });

    refuse = false;
    await user.clear(accent);
    await user.type(accent, "#FFD166");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByText(/Identité enregistrée/)).toBeTruthy();
  });
});
