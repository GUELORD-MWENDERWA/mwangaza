import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Schemas } from "@mwangaza/api";

import type { Permission } from "../../lib/permissions";
import { mockApi } from "../../test/api";
import { me, PERMISSIONS, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import { guideFor } from "./guides";

const loggedIn = (account: ReturnType<typeof me>) => ({
  "GET /api/school/": school,
  "GET /api/me/": account,
});

const coach = async () => within(await screen.findByRole("dialog"));

describe("guide de première connexion (M20)", () => {
  it("choisi par les droits, jamais par le nom du rôle", () => {
    const withRights = (permissions: Permission[], roles = me("teacher").school!.roles) =>
      me("teacher", { school: { ...me("teacher").school!, roles, permissions } });
    const codes = Object.keys(PERMISSIONS) as (keyof typeof PERMISSIONS)[];

    // Rôles de départ : le même guide qu'avec les codes de rôle.
    expect(Object.fromEntries(codes.map((code) => [code, guideFor(me(code))]))).toEqual({
      head: null,
      cashier: "cashier",
      promoter: null,
      study_director: null,
      teacher: null,
      accountant: "accountant",
    });
    // Rôle créé par l'école : guidé comme quiconque a ces droits.
    const counter = [{ id: "00000000-0000-7000-8000-000000000009", name: "Guichet" }];
    expect(guideFor(withRights(PERMISSIONS.cashier, counter as Schemas["RoleSummary"][]))).toBe(
      "cashier",
    );
    // Directeur qui tient aussi la caisse : il encaisse, donc le guide de la caisse.
    expect(guideFor(withRights([...PERMISSIONS.head, ...PERMISSIONS.cashier]))).toBe("cashier");
  });

  it("caissier : mène à la caisse, reprend à la même étape sans changer de page, « Passer » le termine, « Aide et guide » le relance", async () => {
    mockApi(loggedIn(me("cashier")));
    const first = renderApp("/", { guide: true });

    expect((await coach()).getByText("Guide du caissier · étape 1 sur 5")).toBeTruthy();
    expect(first.router.state.location.pathname).toBe("/cash");
    await first.user.click((await coach()).getByRole("button", { name: "Suivant" }));
    expect((await coach()).getByRole("heading", { name: "Cherchez l'élève" })).toBeTruthy();
    first.unmount();

    // Nouvelle ouverture sur cet appareil : même étape, l'utilisateur reste où il est.
    const again = renderApp("/students", { guide: true });
    expect((await coach()).getByText("Guide du caissier · étape 2 sur 5")).toBeTruthy();
    expect(again.router.state.location.pathname).toBe("/students");
    await again.user.click((await coach()).getByRole("button", { name: "Passer le guide" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    again.unmount();

    const later = renderApp("/students", { guide: true });
    await screen.findAllByRole("navigation", { name: "Menu principal" });
    expect(screen.queryByRole("dialog")).toBeNull();
    await later.user.click(screen.getAllByRole("button", { name: "Aide et guide" })[0]!);
    expect((await coach()).getByText("Guide du caissier · étape 1 sur 5")).toBeTruthy();
    expect(later.router.state.location.pathname).toBe("/cash");
  });

  it("comptable : seulement les étapes que ses droits ouvrent ; aucun guide pour le directeur", async () => {
    const permissions = PERMISSIONS.accountant.filter(
      (permission) => permission !== "finance.approve_cancellation",
    );
    mockApi(loggedIn(me("accountant", { school: { ...me("accountant").school!, permissions } })));
    const accountant = renderApp("/", { guide: true });

    expect((await coach()).getByText("Guide du comptable · étape 1 sur 5")).toBeTruthy();
    for (const path of ["/fees", "/students", "/cash-closings", "/unpaid"]) {
      await accountant.user.click((await coach()).getByRole("button", { name: "Suivant" }));
      expect(accountant.router.state.location.pathname).toBe(path);
    }
    await accountant.user.click((await coach()).getByRole("button", { name: "Terminer" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    accountant.unmount();

    mockApi(loggedIn(me("head")));
    renderApp("/", { guide: true });
    await screen.findAllByRole("navigation", { name: "Menu principal" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: "Aide et guide" })).toBeNull();
  });
});
