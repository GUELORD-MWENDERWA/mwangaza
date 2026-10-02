import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCOUNT, ITIG } from "../../test/fixtures";
import { mockApi, renderApp } from "../../test/render";

const PROFILE = {
  address: { commune: "Goma", quartier: "Majengo", avenue: "Kabanda", number: "23" },
  email: "",
  emergency_contact: { full_name: "", phone: "" },
  pending_schools: [],
};

describe("Profil du portail", () => {
  it("envoie les coordonnées aux écoles, contact d'urgence complet seulement", async () => {
    const requests = mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG],
      "GET /api/auth/csrf/": {},
      "GET /api/portal/profile/": PROFILE,
      "POST /api/portal/profile/": { ...PROFILE, pending_schools: ["ITIG Don Bosco Goma"] },
    });
    const { user } = renderApp("/profile");

    const quartier = await screen.findByLabelText("Quartier");
    await user.clear(quartier);
    await user.type(quartier, "Himbi");
    await user.type(screen.getByLabelText("Nom"), "Amani Pierre");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(
      await screen.findByText("Donnez le nom et le téléphone du contact d'urgence."),
    ).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);

    await user.type(screen.getByLabelText("Téléphone"), "0815539071");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText(/Envoyé à : ITIG Don Bosco Goma/)).toBeTruthy();
    await waitFor(() =>
      expect(requests.find((r) => r.method === "POST")?.body).toEqual({
        address: { ...PROFILE.address, quartier: "Himbi" },
        email: "",
        emergency_contact: { full_name: "Amani Pierre", phone: "0815539071" },
      }),
    );
  });
});
