import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RIGHTS } from "../../lib/rights";
import { OWNER, apiError, mockApi, renderApp } from "../../test/render";

const ME = {
  id: "a1",
  phone: "+243970000001",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
  ...OWNER,
};

const member = (id: string, last_name: string, roles: string[], extra = {}) => ({
  id,
  phone: "+243971220145",
  last_name,
  middle_name: "",
  first_name: "",
  roles,
  totp_enabled: true,
  must_change_password: false,
  last_login: "2026-10-18T14:40:00Z",
  created_at: "2026-10-01T08:00:00Z",
  ...extra,
});

const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

afterEach(() => vi.unstubAllGlobals());

describe("Menu de la console selon les rôles", () => {
  it("un commercial ne voit que ses pages ; l'accueil et l'équipe ne lui sont pas ouverts", async () => {
    mockApi({
      "GET /api/me/": {
        ...ME,
        platform_roles: ["commercial"],
        platform_permissions: [RIGHTS.leadsManage, RIGHTS.demosManage],
      },
      "GET /api/console/schools/": page([]),
    });
    const { router, user } = renderApp("/");

    // Sans « voir les écoles », l'accueil mène à sa première page.
    const nav = await screen.findByRole("navigation");
    expect(
      within(nav)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Écoles", "Demandes"]);
    expect(router.state.location.pathname).toBe("/schools");
    // Pas d'onglet « Réels », pas d'administration de dépannage.
    expect(screen.queryByRole("tab", { name: "Réels" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Menu du compte" }));
    expect(screen.queryByText("Administration de dépannage")).toBeNull();

    await router.navigate("/team");
    expect(await screen.findByText("Cette page n'est pas dans vos rôles")).toBeTruthy();
  });
});

describe("Équipe de la plateforme", () => {
  it("invite un membre et montre son mot de passe provisoire une seule fois", async () => {
    const requests = mockApi({
      "GET /api/me/": ME,
      "GET /api/console/team/": page([member("a1", "Mwenderwa", ["owner"])]),
      "GET /api/console/team/roles/": [],
      "POST /api/console/team/": {
        member: member("m2", "Muhindo", ["commercial"], { must_change_password: true }),
        temporary_password: "kivu-4tgw-81mz",
      },
    });
    const { user } = renderApp("/team");

    // Sa propre ligne : pas de « Retirer ».
    expect(await screen.findByText("Vous")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retirer" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Inviter un membre" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Nom"), "Muhindo");
    await user.type(within(dialog).getByLabelText("Téléphone"), "0812004377");
    // Sans rôle : rien n'est envoyé.
    await user.click(within(dialog).getByRole("button", { name: "Inviter" }));
    expect(await within(dialog).findByText("Choisissez au moins un rôle.")).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);

    await user.click(within(dialog).getByRole("checkbox", { name: /Commercial/ }));
    await user.click(within(dialog).getByRole("button", { name: "Inviter" }));

    expect(await screen.findByText("kivu-4tgw-81mz")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toMatchObject({
      last_name: "Muhindo",
      phone: "0812004377",
      roles: ["commercial"],
    });
    await user.click(screen.getByRole("button", { name: "J'ai noté le mot de passe" }));
    expect(screen.queryByText("kivu-4tgw-81mz")).toBeNull();
  });

  it("retire un membre après confirmation et montre le refus du dernier propriétaire", async () => {
    const requests = mockApi({
      "GET /api/me/": ME,
      "GET /api/console/team/": page([
        member("a1", "Mwenderwa", ["owner"]),
        member("m2", "Kahambu", ["support"], { totp_enabled: false }),
      ]),
      "GET /api/console/team/roles/": [],
      "POST /api/console/team/m2/remove/": new Response(null, { status: 204 }),
      "PATCH /api/console/team/a1/": apiError("last_owner", 409),
    });
    const { user } = renderApp("/team");

    expect(await screen.findByText("À activer")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Retirer" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/sessions se ferment tout de suite/)).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "Retirer" }));
    expect(requests.filter((r) => r.path === "/api/console/team/m2/remove/")).toHaveLength(1);

    // Le serveur garde au moins un propriétaire : son refus s'affiche, la fenêtre reste ouverte.
    await user.click(screen.getAllByRole("button", { name: "Rôles" })[0] as HTMLElement);
    const roles = await screen.findByRole("dialog");
    await user.click(within(roles).getByRole("checkbox", { name: /Administrateur principal/ }));
    await user.click(within(roles).getByRole("checkbox", { name: /Technique/ }));
    await user.click(within(roles).getByRole("button", { name: "Enregistrer" }));
    expect(await within(roles).findByText("last_owner")).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({ roles: ["technical"] });
  });
});
