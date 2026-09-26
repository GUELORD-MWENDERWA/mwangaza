import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, noContent, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

function account(overrides: Parameters<typeof me>[1] = {}, extra: Routes = {}): Routes {
  return { "GET /api/school/": school, "GET /api/me/": me("head", overrides), ...extra };
}

const card = async (title: string) =>
  within((await screen.findByRole("heading", { name: title })).closest("section")!);

describe("Mon compte (M4)", () => {
  it("identité en lecture seule : l'école la modifie", async () => {
    mockApi(account());
    renderApp("/account");

    const identity = await card("Identité");
    const lastName = identity.getByLabelText("Nom") as HTMLInputElement;
    expect([lastName.value, lastName.readOnly]).toEqual(["Test", true]);
    expect(
      identity.getByText("Pour changer de nom ou de numéro, adressez-vous au directeur."),
    ).toBeTruthy();
  });

  it("langue enregistrée sur le compte, l'interface change", async () => {
    const routes = account();
    const requests = mockApi(routes);
    const { user } = renderApp("/account");

    routes["PATCH /api/me/"] = me("head", { language: "en" });
    await user.click(await screen.findByRole("radio", { name: "English" }));

    expect(await screen.findByRole("heading", { name: "My account" })).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({ language: "en" });
  });

  it("mot de passe : l'actuel est vérifié par le serveur", async () => {
    const requests = mockApi(
      account({}, { "POST /api/auth/password/": apiError("wrong_password", 400) }),
    );
    const { user } = renderApp("/account");

    const password = await card("Mot de passe");
    await user.type(password.getByLabelText("Mot de passe actuel"), "ancien-faux");
    await user.type(password.getByLabelText("Nouveau"), "nouveau-mot-de-passe");
    await user.type(password.getByLabelText("Confirmer"), "nouveau-mot-de-passe");
    await user.click(password.getByRole("button", { name: "Changer le mot de passe" }));

    expect(await password.findByText("Le mot de passe actuel n'est pas correct.")).toBeTruthy();
    expect(requests.find((r) => r.path === "/api/auth/password/")?.body).toEqual({
      current_password: "ancien-faux",
      new_password: "nouveau-mot-de-passe",
    });
  });

  it("mot de passe changé : confirmation, champs vidés", async () => {
    mockApi(account({}, { "POST /api/auth/password/": { step: "done" } }));
    const { user } = renderApp("/account");

    const password = await card("Mot de passe");
    await user.type(password.getByLabelText("Mot de passe actuel"), "ancien-mot-de-passe");
    await user.type(password.getByLabelText("Nouveau"), "nouveau-mot-de-passe");
    await user.type(password.getByLabelText("Confirmer"), "nouveau-mot-de-passe");
    await user.click(password.getByRole("button", { name: "Changer le mot de passe" }));

    expect(
      await password.findByText("Mot de passe changé. Vos autres appareils sont déconnectés."),
    ).toBeTruthy();
    expect((password.getByLabelText("Nouveau") as HTMLInputElement).value).toBe("");
  });

  it("2 codes de secours ou moins : alerte", async () => {
    mockApi(account({ recovery_codes_left: 2 }));
    renderApp("/account");

    const twoFactor = await card("Double authentification");
    expect(twoFactor.getByText("2 sur 8")).toBeTruthy();
    expect(twoFactor.getByText(/Il vous reste peu de codes de secours/)).toBeTruthy();
  });

  it("assez de codes : pas d'alerte", async () => {
    mockApi(account({ recovery_codes_left: 3 }));
    renderApp("/account");

    const twoFactor = await card("Double authentification");
    expect(twoFactor.queryByText(/Il vous reste peu de codes de secours/)).toBeNull();
  });

  it("exigée par un rôle : pas de bouton « Désactiver »", async () => {
    mockApi(account({ totp_required: true }));
    renderApp("/account");

    const twoFactor = await card("Double authentification");
    expect(twoFactor.queryByRole("button", { name: "Désactiver" })).toBeNull();
    expect(
      twoFactor.getByText("Un de vos rôles l'exige : elle ne peut pas être désactivée."),
    ).toBeTruthy();
  });

  it("pas exigée : désactivée avec le code actuel", async () => {
    const routes = account(
      { totp_required: false },
      { "POST /api/auth/totp/disable/": noContent() },
    );
    const requests = mockApi(routes);
    const { user } = renderApp("/account");

    await user.click(
      (await card("Double authentification")).getByRole("button", { name: "Désactiver" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Désactiver" });
    await user.type(within(dialog).getByLabelText(/Code actuel/), "123456");
    routes["GET /api/me/"] = me("head", { totp_required: false, totp_enabled: false });
    await user.click(within(dialog).getByRole("button", { name: "Désactiver" }));

    expect(await screen.findByText("Double authentification désactivée.")).toBeTruthy();
    expect(requests.find((r) => r.path === "/api/auth/totp/disable/")?.body).toEqual({
      code: "123456",
    });
  });

  it("nouveaux codes de secours : code faux, puis les codes une seule fois", async () => {
    const routes = account(
      { recovery_codes_left: 1 },
      { "POST /api/auth/totp/recovery-codes/": apiError("invalid_code", 400) },
    );
    mockApi(routes);
    const { user } = renderApp("/account");

    await user.click(
      (await card("Double authentification")).getByRole("button", {
        name: "Nouveaux codes de secours",
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Nouveaux codes de secours" });
    await user.type(within(dialog).getByLabelText(/Code actuel/), "000000");
    await user.click(within(dialog).getByRole("button", { name: "Générer" }));
    expect(
      await within(dialog).findByText("Ce code n'est pas valable, ou il a déjà servi."),
    ).toBeTruthy();

    routes["POST /api/auth/totp/recovery-codes/"] = { recovery_codes: ["AAAA-1111", "BBBB-2222"] };
    await user.click(within(dialog).getByRole("button", { name: "Générer" }));
    expect(await within(dialog).findByText("AAAA-1111")).toBeTruthy();
    const finish = within(dialog).getByRole("button", { name: "Terminer" }) as HTMLButtonElement;
    expect(finish.disabled).toBe(true);
    await user.click(within(dialog).getByLabelText(/J'ai imprimé ou recopié/));
    await user.click(finish);

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("pas activée : « Activer » mène à l'activation, clé demandée tout de suite", async () => {
    const routes = account(
      { totp_enabled: false, totp_required: false, recovery_codes_left: 0 },
      {
        "POST /api/auth/totp/setup/": {
          secret: "JBSWY3DPEHPK3PXP",
          otpauth_uri: "otpauth://totp/Mwangaza:test?secret=JBSWY3DPEHPK3PXP",
        },
      },
    );
    mockApi(routes);
    const { user } = renderApp("/account");

    await user.click(await screen.findByRole("link", { name: "Activer" }));

    expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Activer la double authentification" }),
    ).toBeTruthy();
  });

  it("changer de téléphone : le code actuel avant la nouvelle clé", async () => {
    const routes = account(
      {},
      {
        "POST /api/auth/totp/setup/": (request: Request) =>
          request
            .clone()
            .json()
            .then((body: { code?: string }) =>
              body.code === "123456"
                ? { secret: "JBSWY3DPEHPK3PXP", otpauth_uri: "otpauth://totp/x" }
                : apiError("invalid_code", 400),
            ),
      },
    );
    const requests = mockApi(routes);
    const { user } = renderApp("/account/two-factor");

    expect(await screen.findByRole("heading", { name: "Changer de téléphone" })).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/auth/totp/setup/")).toBe(false);
    await user.type(screen.getByLabelText(/Code actuel/), "123456");
    await user.click(screen.getByRole("button", { name: "Afficher la nouvelle clé" }));

    expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeTruthy();
  });

  it("mes écoles : l'actuelle, les autres à leur adresse", async () => {
    mockApi(
      account({
        schools: [
          me().schools[0]!,
          {
            ...me().schools[0]!,
            code: "beta",
            name: "École Beta (fictive)",
            url: "http://beta.localhost:5173",
          },
        ],
      }),
    );
    renderApp("/account");

    const schools = await card("Mes écoles");
    expect(schools.getByText("actuelle")).toBeTruthy();
    expect(schools.getByRole("link", { name: /Ouvrir/ }).getAttribute("href")).toBe(
      "http://beta.localhost:5173/app/",
    );
  });

  it("déconnexion refusée faute de réseau : on reste connecté, avec le message", async () => {
    const routes = account();
    mockApi(routes);
    const { user, router } = renderApp("/account");

    routes["POST /api/auth/logout/"] = () => Promise.reject(new TypeError("Failed to fetch"));
    const buttons = await screen.findAllByRole("button", { name: "Se déconnecter" });
    await user.click(buttons[buttons.length - 1]!);

    expect(await screen.findByText(/Pas de connexion au serveur/)).toBeTruthy();
    expect(router.state.location.pathname).toBe("/account");
  });
});
