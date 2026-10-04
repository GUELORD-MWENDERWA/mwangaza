import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, noContent, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

/** Pas connecté : l'étape de connexion vient du serveur, `/api/me/` refuse. */
function loggedOut(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": apiError("not_authenticated", 403),
    "GET /api/auth/login/": { step: "password" },
    "GET /api/auth/csrf/": noContent(),
    ...extra,
  };
}

async function submitPassword(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText("Numéro de téléphone"), "0000000100");
  await user.type(screen.getByLabelText("Mot de passe"), "mot-de-passe-fictif");
  await user.click(screen.getByRole("button", { name: "Se connecter" }));
}

describe("connexion (M1)", () => {
  it("l'écran de connexion montre l'école de l'adresse", async () => {
    mockApi(loggedOut());
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Se connecter" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: school.name })).toBeTruthy();
  });

  it("mot de passe puis code : la page demandée au départ", async () => {
    const routes = loggedOut({
      "POST /api/auth/login/": { step: "totp" },
      "POST /api/auth/login/totp/": { step: "done" },
    });
    const requests = mockApi(routes);
    const { user, router } = renderApp("/account");
    await screen.findByRole("heading", { name: "Se connecter" });
    expect(router.state.location.search).toBe("?next=%2Faccount");

    await submitPassword(user);
    await user.type(await screen.findByLabelText("Code à 6 chiffres"), "123456");
    routes["GET /api/me/"] = me("head");
    await user.click(screen.getByRole("button", { name: "Vérifier" }));

    expect(await screen.findByRole("heading", { name: "Mon compte" })).toBeTruthy();
    expect(router.state.location.pathname).toBe("/account");
    expect(
      requests.find((r) => r.method === "POST" && r.path === "/api/auth/login/")?.body,
    ).toEqual({
      phone: "0000000100",
      password: "mot-de-passe-fictif",
    });
    // « Ne plus demander sur cet appareil » : décoché par défaut.
    expect(requests.find((r) => r.path === "/api/auth/login/totp/")?.body).toEqual({
      code: "123456",
      trust_device: false,
    });
  });

  it("numéro ou mot de passe incorrect : message traduit, mot de passe effacé", async () => {
    mockApi(loggedOut({ "POST /api/auth/login/": apiError("invalid_credentials", 400) }));
    const { user } = renderApp("/login");

    await submitPassword(user);

    expect(await screen.findByText("Numéro de téléphone ou mot de passe incorrect.")).toBeTruthy();
    expect((screen.getByLabelText("Mot de passe") as HTMLInputElement).value).toBe("");
  });

  it("trop d'essais : le temps d'attente", async () => {
    mockApi(
      loggedOut({
        "POST /api/auth/login/": apiError("too_many_attempts", 429, { retryAfter: 600 }),
      }),
    );
    const { user } = renderApp("/login");

    await submitPassword(user);

    expect(await screen.findByText("Trop d'essais ratés. Réessayez dans 10 minutes.")).toBeTruthy();
  });

  it("champs vides : rien n'est envoyé", async () => {
    const requests = mockApi(loggedOut());
    const { user } = renderApp("/login");

    await user.click(await screen.findByRole("button", { name: "Se connecter" }));

    expect(await screen.findByText("Saisissez votre numéro de téléphone.")).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);
  });

  it("code faux : message sous les cases", async () => {
    mockApi(
      loggedOut({
        "GET /api/auth/login/": { step: "totp" },
        "POST /api/auth/login/totp/": apiError("invalid_code", 400),
      }),
    );
    const { user } = renderApp("/login/code");

    await user.type(await screen.findByLabelText("Code à 6 chiffres"), "000000");
    await user.click(screen.getByRole("button", { name: "Vérifier" }));

    expect(await screen.findByText("Ce code n'est pas valable, ou il a déjà servi.")).toBeTruthy();
  });

  it("page rechargée au milieu de la connexion : l'étape en cours", async () => {
    mockApi(loggedOut({ "GET /api/auth/login/": { step: "totp" } }));
    const { router } = renderApp("/login");

    expect(await screen.findByRole("heading", { name: "Code de vérification" })).toBeTruthy();
    expect(router.state.location.pathname).toBe("/login/code");
  });

  it("mot de passe provisoire : l'erreur du serveur sous le champ", async () => {
    mockApi(
      loggedOut({
        "GET /api/auth/login/": { step: "new_password" },
        "POST /api/auth/password/": apiError("invalid", 400, {
          fields: { new_password: [{ code: "password_too_common", detail: "…" }] },
        }),
      }),
    );
    const { user } = renderApp("/login/new-password");

    await user.type(await screen.findByLabelText("Nouveau mot de passe"), "motdepasse");
    await user.type(screen.getByLabelText("Confirmer"), "motdepasse");
    await user.click(screen.getByRole("button", { name: "Enregistrer le mot de passe" }));

    expect(
      await screen.findByText("Ce mot de passe est trop courant : choisissez-en un autre."),
    ).toBeTruthy();
  });

  it("mot de passe provisoire : les deux saisies doivent être identiques", async () => {
    const requests = mockApi(loggedOut({ "GET /api/auth/login/": { step: "new_password" } }));
    const { user } = renderApp("/login/new-password");

    await user.type(await screen.findByLabelText("Nouveau mot de passe"), "motdepasse-1");
    await user.type(screen.getByLabelText("Confirmer"), "motdepasse-2");
    await user.click(screen.getByRole("button", { name: "Enregistrer le mot de passe" }));

    expect(await screen.findByText("Les deux mots de passe ne sont pas identiques.")).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/auth/password/")).toBe(false);
  });

  it("activation obligatoire : lien vers l'application, clé copiée, « Terminer » bloqué sans la case", async () => {
    const routes = loggedOut({
      "GET /api/auth/login/": { step: "totp_setup" },
      "POST /api/auth/totp/setup/": {
        secret: "JBSWY3DPEHPK3PXP",
        otpauth_uri: "otpauth://totp/Mwangaza:test?secret=JBSWY3DPEHPK3PXP&issuer=Mwangaza",
      },
      "POST /api/auth/totp/activate/": {
        step: "done",
        recovery_codes: ["AAAA-1111", "BBBB-2222", "CCCC-3333", "DDDD-4444"],
      },
    });
    mockApi(routes);
    const { user, router } = renderApp("/login");

    expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeTruthy();
    // Sur le téléphone : le lien ouvre l'application, qui ajoute le compte ; ou la clé copiée.
    const openApp = screen.getByRole("link", { name: "Ajouter à mon application" });
    expect(openApp.getAttribute("href")).toMatch(/^otpauth:\/\/totp\/.*secret=JBSWY3DPEHPK3PXP/);
    await user.click(screen.getByRole("button", { name: "Copier la clé" }));
    expect(await navigator.clipboard.readText()).toBe("JBSWY3DPEHPK3PXP");
    await user.type(screen.getByLabelText("Code à 6 chiffres"), "123456");
    await user.click(screen.getByRole("button", { name: "Vérifier et activer" }));

    expect(await screen.findByText("AAAA-1111")).toBeTruthy();
    const finish = screen.getByRole("button", { name: "Terminer" }) as HTMLButtonElement;
    expect(finish.disabled).toBe(true);
    await user.click(screen.getByLabelText("J'ai imprimé ou recopié mes 8 codes de secours"));
    expect(finish.disabled).toBe(false);

    routes["GET /api/me/"] = me("promoter");
    await user.click(finish);
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(await screen.findByRole("heading", { name: /Bonjour/ })).toBeTruthy();
  });

  it("« Retour » depuis le code : la connexion est oubliée", async () => {
    const requests = mockApi(
      loggedOut({
        "GET /api/auth/login/": { step: "totp" },
        "POST /api/auth/logout/": noContent(),
      }),
    );
    const { user } = renderApp("/login/code");

    await user.click(await screen.findByRole("button", { name: "Retour" }));

    expect(await screen.findByRole("heading", { name: "Se connecter" })).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/auth/logout/")).toBe(true);
  });

  it("langue de l'écran de connexion : English", async () => {
    mockApi(loggedOut());
    const { user } = renderApp("/login");

    const languages = await screen.findAllByRole("navigation", { name: "Langue de l'interface" });
    await user.click(within(languages[0]!).getByRole("button", { name: "English" }));

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeTruthy();
    expect(document.documentElement.lang).toBe("en");
  });
});
