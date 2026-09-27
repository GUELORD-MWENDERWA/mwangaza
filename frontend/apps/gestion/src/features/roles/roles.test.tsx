import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, type Routes } from "../../test/api";
import { me, PERMISSIONS, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const role = (n: number, code: string, permissions: string[], extra = {}) => ({
  id: id(n),
  code,
  name: "",
  is_system: code !== "",
  permissions,
  member_count: 2,
  ...extra,
});
const roles = [
  role(1, "head", PERMISSIONS.head, { member_count: 1 }),
  role(2, "cashier", PERMISSIONS.cashier),
  role(3, "parent", [], { member_count: 0 }),
  role(4, "", ["finance.view_reports"], { name: "Surveillant de caisse", member_count: 0 }),
];
const person = (n: number, last: string, first: string, roleIds: string[]) => ({
  id: id(100 + n),
  user: {
    id: id(200 + n),
    phone: "+243970000001",
    last_name: last,
    middle_name: "",
    first_name: first,
  },
  roles: roleIds,
  is_active: true,
  totp: "enabled",
  last_login_at: null,
  account_managed_here: true,
  created_at: "2026-09-28T08:00:00Z",
});
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/roles/": page(roles),
    "GET /api/staff/": (request: Request) =>
      new URL(request.url).searchParams.get("role")
        ? page([person(1, "Kavira", "Jeanne", [id(2)])])
        : page([person(1, "Kavira", "Jeanne", [id(2)]), person(2, "Zawadi", "Alice", [])]),
    ...extra,
  };
}

const editor = async (title: string) =>
  within((await screen.findByRole("heading", { name: title })).closest("section")!);

describe("Rôles et permissions (B1-B2)", () => {
  it("liste des rôles ; permissions cochées ; double authentification déduite des droits", async () => {
    const requests = mockApi(
      routes({ "PATCH /api/roles/00000000-0000-7000-8000-000000000002/": roles[1]! }),
    );
    const { user } = renderApp("/roles");

    const nav = within(await screen.findByRole("navigation", { name: "Rôles et permissions" }));
    expect(nav.getByRole("button", { name: /Caissier.*2 utilisateurs · prédéfini/ })).toBeTruthy();
    expect(
      nav.getByRole("button", { name: /Surveillant de caisse.*0 utilisateur · personnalisé/ }),
    ).toBeTruthy();
    await user.click(nav.getByRole("button", { name: /Caissier/ }));

    const cashier = await editor("Caissier");
    expect(cashier.getByText("Double authentification obligatoire")).toBeTruthy();
    expect(cashier.getByRole("checkbox", { name: "Encaisser" }).getAttribute("aria-checked")).toBe(
      "true",
    );
    expect(
      cashier.getByRole("checkbox", { name: "Configurer l'école" }).getAttribute("aria-checked"),
    ).toBe("false");
    for (const name of ["Encaisser", "Demander une annulation", "Clôturer sa caisse"]) {
      await user.click(cashier.getByRole("checkbox", { name }));
    }
    expect(cashier.getByText("Double authentification non exigée")).toBeTruthy();
    await user.click(cashier.getByRole("button", { name: "Enregistrer" }));

    expect(await cashier.findByText("Rôle enregistré.")).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({
      name: "",
      permissions: ["students.view"],
    });
  });

  it("renommer un rôle prédéfini ; nom déjà pris : refus traduit", async () => {
    mockApi(
      routes({
        "PATCH /api/roles/00000000-0000-7000-8000-000000000001/": apiError("role_name_taken", 409),
      }),
    );
    const { user } = renderApp("/roles");

    const head = await editor("Directeur");
    expect(head.getByText("Vide : « Directeur ».")).toBeTruthy();
    await user.type(head.getByLabelText("Nom du rôle"), "Préfet des études");
    expect(head.getByRole("heading", { name: "Préfet des études" })).toBeTruthy();
    await user.click(head.getByRole("button", { name: "Enregistrer" }));
    expect(await head.findByText("L'école a déjà un rôle de ce nom.")).toBeTruthy();
  });

  it("utilisateurs du rôle ; donner le rôle à quelqu'un", async () => {
    const requests = mockApi(
      routes({
        "PATCH /api/staff/00000000-0000-7000-8000-000000000102/": person(2, "Zawadi", "Alice", [
          id(2),
        ]),
      }),
    );
    const { user } = renderApp("/roles");

    await user.click(await screen.findByRole("button", { name: /Caissier/ }));
    const cashier = await editor("Caissier");
    expect(await cashier.findByText("Jeanne Kavira")).toBeTruthy();
    await user.click(cashier.getByRole("button", { name: "Ajouter" }));
    await user.click(await cashier.findByRole("button", { name: "Alice Zawadi" }));

    await waitFor(() =>
      expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({ roles: [id(2)] }),
    );
    expect(requests.find((r) => r.method === "GET" && r.query.role === id(2))?.query).toEqual({
      role: id(2),
      is_active: "true",
    });
  });

  it("nouveau rôle, puis supprimé ; un rôle donné ne se supprime pas", async () => {
    const created = role(5, "", [], { name: "Chef d'atelier", member_count: 0 });
    const all = routes({
      "POST /api/roles/": created,
      "DELETE /api/roles/00000000-0000-7000-8000-000000000005/": () =>
        new Response(null, { status: 204 }),
    });
    const requests = mockApi(all);
    const { user } = renderApp("/roles");

    await user.click(await screen.findByRole("button", { name: "Nouveau rôle" }));
    const dialog = within(await screen.findByRole("dialog"));
    await user.type(dialog.getByLabelText(/Nom du rôle/), " Chef d'atelier ");
    all["GET /api/roles/"] = page([...roles, created]);
    await user.click(dialog.getByRole("button", { name: "Créer le rôle" }));

    const workshop = await editor("Chef d'atelier");
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({
      name: "Chef d'atelier",
      permissions: [],
    });
    await user.click(workshop.getByRole("button", { name: "Supprimer le rôle" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Supprimer le rôle" }),
    );
    await waitFor(() => expect(requests.some((r) => r.method === "DELETE")).toBe(true));

    await user.click(screen.getByRole("button", { name: /Caissier/ }));
    expect(
      (await editor("Caissier")).queryByRole("button", { name: "Supprimer le rôle" }),
    ).toBeNull();
  });

  it("parent : rien dans la Gestion", async () => {
    mockApi(routes());
    const { user } = renderApp("/roles");

    await user.click(await screen.findByRole("button", { name: /Parent/ }));
    expect(await screen.findByText(/Les parents utilisent le portail des familles/)).toBeTruthy();
  });

  it("sans le droit : page refusée", async () => {
    mockApi(routes({ "GET /api/me/": me("promoter") }));
    renderApp("/roles");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
  });
});
