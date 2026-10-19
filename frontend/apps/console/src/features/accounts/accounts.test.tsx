import { cleanup, screen } from "@testing-library/react";
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

const ALPHA = { id: "s1", code: "alpha", name: "École Alpha" };

const ACCOUNT = {
  id: "u1",
  phone: "+243970001122",
  last_name: "Kasereka",
  middle_name: "",
  first_name: "Dieudonné",
  is_active: true,
  is_platform_admin: false,
  totp_enabled: true,
  must_change_password: false,
  last_login: null,
  memberships: [
    { id: "m1", school: ALPHA, roles: ["Caissier"], is_active: true, last_login_at: null },
  ],
  families: [],
  created_at: "2026-10-01T08:00:00Z",
  history: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("Fiche d'un compte dans la console", () => {
  it("donne un mot de passe provisoire après confirmation et l'affiche une seule fois", async () => {
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/accounts/u1/": ACCOUNT,
      "POST /api/console/accounts/u1/new-password/": { temporary_password: "kivu-7mpq-23xa" },
    });
    const { user } = renderApp("/accounts/u1");

    await user.click(
      await screen.findByRole("button", { name: "Donner un mot de passe provisoire" }),
    );
    expect(requests.some((r) => r.method === "POST")).toBe(false);
    await user.click(await screen.findByRole("button", { name: "Donner le mot de passe" }));

    expect(await screen.findByText("kivu-7mpq-23xa")).toBeTruthy();
    expect(screen.getByText(/Affiché une seule fois/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Réinitialiser (téléphone perdu)" })).toBeTruthy();
  });

  it("ne propose rien pour un compte de la plateforme, ni de mot de passe à un parent seul", async () => {
    mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/accounts/a1/": {
        ...ACCOUNT,
        ...ADMIN,
        memberships: [],
        history: [],
      },
      "GET /api/console/accounts/u2/": {
        ...ACCOUNT,
        id: "u2",
        totp_enabled: false,
        memberships: [],
        families: [
          {
            id: "f1",
            code: "FAMALPH1",
            school: ALPHA,
            activated_at: null,
            portal_suspended_at: null,
          },
        ],
      },
    });
    renderApp("/accounts/a1");
    expect(await screen.findByText(/ne se modifie que dans l'administration Django/)).toBeTruthy();
    for (const name of [
      "Enregistrer",
      "Donner un mot de passe provisoire",
      "Désactiver le compte",
    ]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    cleanup();

    renderApp("/accounts/u2");
    expect(await screen.findByText(/l'école donne un nouveau code famille/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Donner un mot de passe provisoire" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Réinitialiser (téléphone perdu)" })).toBeNull();
    expect(screen.getByRole("button", { name: "Désactiver le compte" })).toBeTruthy();
  });
});
