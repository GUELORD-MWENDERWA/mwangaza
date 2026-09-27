import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const role = (n: number, code: string, name = "", permissions: string[] = []) => ({
  id: id(n),
  code,
  name,
  is_system: code !== "",
  permissions,
  member_count: 1,
});
const roles = [
  role(1, "head", "", ["roles.manage"]),
  role(2, "cashier", "", ["finance.collect_payment"]),
  role(3, "teacher"),
  role(4, "", "Chef d'atelier", ["students.view"]),
];
const person = (n: number, last: string, first: string, extra = {}) => ({
  id: id(100 + n),
  user: {
    id: id(200 + n),
    phone: `+24397${String(n).padStart(7, "0")}`,
    last_name: last,
    middle_name: "",
    first_name: first,
  },
  roles: [id(2)],
  is_active: true,
  totp: "enabled",
  last_login_at: "2026-10-19T05:40:00Z",
  account_managed_here: true,
  created_at: "2026-09-28T08:00:00Z",
  ...extra,
});
const staff = [
  person(1, "Kavira", "Jeanne"),
  person(2, "Mugisho", "Innocent", { totp: "to_enable", last_login_at: null, roles: [id(1)] }),
  person(3, "Kakule", "Nzanzu", {
    is_active: false,
    totp: "not_required",
    roles: [id(4)],
    account_managed_here: false,
  }),
];
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
    "GET /api/staff/": page(staff),
    ...extra,
  };
}

const card = async (title: string | RegExp) =>
  within((await screen.findByRole("heading", { name: title })).closest("section")!);

describe("Comptes du personnel (M3)", () => {
  it("liste : rôles, double authentification, dernière connexion, état", async () => {
    mockApi(routes());
    renderApp("/staff");

    const rows = (await screen.findAllByRole("row")).slice(1).map((row) => row.textContent);
    expect(rows[0]).toMatch(
      /^JKJeanne Kavira\+243 97 000 00 01CaissierActivée\d{2}\/\d{2}\/2026Actif$/,
    );
    expect(rows[1]).toContain("À activer");
    expect(rows[1]).toContain("jamais");
    expect(rows[1]).toContain("Invité");
    expect(rows[2]).toContain("Chef d'atelier");
    expect(rows[2]).toContain("non exigée");
    expect(rows[2]).toContain("Désactivé");
    expect(screen.getByText("3 comptes")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Gérer les rôles et leurs permissions" })).toBeTruthy();
  });

  it("filtres envoyés au serveur", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/staff");

    await user.type(await screen.findByLabelText("Nom ou téléphone"), "kavira");
    await user.selectOptions(screen.getByLabelText("Rôle"), id(2));
    await user.selectOptions(screen.getByLabelText("État"), "inactive");

    await waitFor(() =>
      expect(requests.filter((r) => r.path === "/api/staff/").at(-1)?.query).toEqual({
        search: "kavira",
        role: id(2),
        is_active: "false",
      }),
    );
  });

  it("rôles d'une personne : enregistrés ; refus du serveur traduit", async () => {
    const all = routes({
      "PATCH /api/staff/00000000-0000-7000-8000-000000000101/": apiError("last_role_manager", 409),
    });
    const requests = mockApi(all);
    const { user } = renderApp("/staff");

    await user.click(await screen.findByRole("button", { name: /Jeanne Kavira/ }));
    const detail = await card("Jeanne Kavira");
    expect(detail.getByText("+243 97 000 00 01")).toBeTruthy();
    await user.click(detail.getByRole("checkbox", { name: /Chef d'atelier/ }));
    await user.click(detail.getByRole("button", { name: "Enregistrer les rôles" }));

    expect(
      await detail.findByText(
        "Ce changement laisserait l'école sans personne pour gérer les rôles.",
      ),
    ).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({ roles: [id(2), id(4)] });
  });

  it("nouveau mot de passe affiché une fois ; double auth. et désactivation confirmées", async () => {
    const path = "/api/staff/00000000-0000-7000-8000-000000000101/";
    const requests = mockApi(
      routes({
        [`POST ${path}new-password/`]: { temporary_password: "abcd-efgh-jkmn" },
        [`POST ${path}reset-totp/`]: staff[0]!,
        [`PATCH ${path}`]: { ...staff[0]!, is_active: false },
      }),
    );
    const { user } = renderApp("/staff");

    await user.click(await screen.findByRole("button", { name: /Jeanne Kavira/ }));
    const detail = await card("Jeanne Kavira");
    await user.click(detail.getByRole("button", { name: "Nouveau mot de passe" }));
    let dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByText("abcd-efgh-jkmn")).toBeTruthy();
    expect(dialog.getByText(/il ne sera plus affiché/)).toBeTruthy();
    await user.click(dialog.getByRole("button", { name: "J'ai noté le mot de passe" }));

    await user.click(detail.getByRole("button", { name: "Réinitialiser la double auth." }));
    dialog = within(await screen.findByRole("dialog"));
    await user.click(dialog.getByRole("button", { name: "Réinitialiser la double auth." }));
    expect(await detail.findByText("Double authentification réinitialisée.")).toBeTruthy();

    await user.click(detail.getByRole("button", { name: "Désactiver" }));
    dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByText(/Son compte reste valable dans ses autres écoles/)).toBeTruthy();
    await user.click(dialog.getByRole("button", { name: "Désactiver" }));

    await waitFor(() =>
      expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({ is_active: false }),
    );
  });

  it("compte utilisé dans une autre école : boutons du compte désactivés", async () => {
    mockApi(routes());
    const { user } = renderApp("/staff");

    await user.click(await screen.findByRole("button", { name: /Nzanzu Kakule/ }));
    const detail = await card("Nzanzu Kakule");
    for (const name of [
      "Nouveau mot de passe",
      "Réinitialiser la double auth.",
      "Noms et téléphone",
    ]) {
      expect((detail.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(
      detail.getByText("Compte utilisé ailleurs : contactez le support Mwangaza."),
    ).toBeTruthy();
    expect(detail.getByRole("button", { name: "Réactiver" })).toBeTruthy();
  });

  it("nouveau compte : mot de passe provisoire affiché une fois", async () => {
    const created = {
      ...person(9, "Furaha", "Masika"),
      existing_account: false,
      temporary_password: "wxyz-2345-abcd",
    };
    const requests = mockApi(routes({ "POST /api/staff/": created }));
    const { user } = renderApp("/staff");

    const form = await card("Nouveau compte");
    await user.click(form.getByRole("button", { name: "Créer le compte" }));
    expect(await form.findByText("Saisissez votre numéro de téléphone.")).toBeTruthy();
    expect(form.getByText("Choisissez au moins un rôle.")).toBeTruthy();

    await user.type(form.getByLabelText(/Numéro de téléphone/), "0998614503");
    await user.type(form.getByLabelText("Nom"), "Furaha");
    await user.type(form.getByLabelText("Prénom"), "Masika");
    await user.click(form.getByRole("checkbox", { name: "Caissier" }));
    await user.click(form.getByRole("button", { name: "Créer le compte" }));

    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByText("wxyz-2345-abcd")).toBeTruthy();
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({
      phone: "0998614503",
      last_name: "Furaha",
      middle_name: "",
      first_name: "Masika",
      roles: [id(2)],
    });
  });

  it("numéro déjà connu : ajouté sans mot de passe ; numéro inconnu sans nom : refus traduit", async () => {
    const all = routes({ "POST /api/staff/": apiError("names_required", 400) });
    mockApi(all);
    const { user } = renderApp("/staff");

    const form = await card("Nouveau compte");
    await user.type(form.getByLabelText(/Numéro de téléphone/), "0998614503");
    await user.click(form.getByRole("checkbox", { name: "Enseignant" }));
    await user.click(form.getByRole("button", { name: "Créer le compte" }));
    expect(
      await form.findByText("Ce numéro n'a pas encore de compte : saisissez au moins le nom."),
    ).toBeTruthy();

    all["POST /api/staff/"] = {
      ...person(8, "Katembo", "Olivier"),
      existing_account: true,
      temporary_password: null,
    };
    await user.click(form.getByRole("button", { name: "Créer le compte" }));
    expect(
      await form.findByText(
        "Olivier Katembo a déjà un compte Mwangaza : ajouté à l'école avec ses rôles.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("sans le droit : page refusée", async () => {
    const requests = mockApi(routes({ "GET /api/me/": me("cashier") }));
    renderApp("/staff");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/staff/")).toBe(false);
  });
});
