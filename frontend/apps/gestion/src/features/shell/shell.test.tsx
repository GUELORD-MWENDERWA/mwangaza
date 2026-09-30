import { act, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, noContent, offline, type Routes } from "../../test/api";
import { me, school, schoolEntry } from "../../test/fixtures";
import { keys } from "../../lib/queries";
import { renderApp } from "../../test/render";

function loggedIn(account = me("head"), extra: Routes = {}): Routes {
  return { "GET /api/school/": school, "GET /api/me/": account, ...extra };
}

const mainMenu = async () =>
  within((await screen.findAllByRole("navigation", { name: "Menu principal" }))[0]!);

describe("coquille et menu (M7)", () => {
  it("menu filtré par les droits du compte dans l'école", async () => {
    mockApi(loggedIn(me("cashier")));
    renderApp("/");

    const menu = await mainMenu();
    expect(menu.getByRole("link", { name: "Caisse" })).toBeTruthy();
    expect(menu.queryByRole("link", { name: "Frais et barèmes" })).toBeNull();
    // Paramètres : seulement son appareil et sa file d'attente.
    expect(menu.getByRole("link", { name: "Appareils et synchro" })).toBeTruthy();
    expect(menu.queryByRole("link", { name: "Rôles et permissions" })).toBeNull();
  });

  it("nom et rôle en haut à droite, lien vers Mon compte", async () => {
    mockApi(loggedIn(me("cashier")));
    renderApp("/");

    const account = await screen.findByRole("link", { name: "Aline Test — Mon compte" });
    expect(within(account).getByText("Caissier")).toBeTruthy();
  });

  it("écran interdit ouvert par son adresse : 403 sans aucune donnée", async () => {
    mockApi(loggedIn(me("cashier")));
    renderApp("/fees");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
    expect(screen.getByText(/ne permet pas d'ouvrir « Frais et barèmes »/)).toBeTruthy();
  });

  it("écran permis pas encore construit : « bientôt disponible »", async () => {
    mockApi(loggedIn(me("promoter")));
    renderApp("/unpaid");

    expect(await screen.findByText("Cet écran arrive bientôt")).toBeTruthy();
    expect(
      screen.getByText("« Impayés » n'est pas encore disponible dans cette version."),
    ).toBeTruthy();
  });

  it("adresse inconnue : 404 dans la coquille", async () => {
    mockApi(loggedIn());
    renderApp("/nimporte-quoi");

    expect(await screen.findByText("Cette page n'existe pas")).toBeTruthy();
    expect(await mainMenu()).toBeTruthy();
  });

  it("aucun écran permis (enseignant en V1.0) : message, menu vide", async () => {
    mockApi(loggedIn(me("teacher")));
    renderApp("/");

    expect(await screen.findByText(/ne donne encore accès à aucun écran/)).toBeTruthy();
    expect(
      within(
        (await screen.findAllByRole("navigation", { name: "Menu principal" }))[0]!,
      ).queryAllByRole("link"),
    ).toEqual([]);
  });

  it("hors ligne : indiqué en haut", async () => {
    mockApi(loggedIn());
    Object.defineProperty(navigator, "onLine", { value: false, configurable: true });
    try {
      renderApp("/");
      expect(await screen.findByText("Hors ligne")).toBeTruthy();
    } finally {
      Object.defineProperty(navigator, "onLine", { value: true, configurable: true });
    }
  });

  it("menu tiroir : s'ouvre, se ferme après un choix", async () => {
    mockApi(loggedIn());
    const { user, router } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Ouvrir le menu" }));
    const drawer = await screen.findByRole("dialog", { name: "Menu principal" });
    await user.click(within(drawer).getByRole("link", { name: "Élèves" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(router.state.location.pathname).toBe("/students");
  });

  it("déconnexion depuis le menu tiroir", async () => {
    const routes = loggedIn(me(), {
      "POST /api/auth/logout/": noContent(),
      "GET /api/auth/login/": { step: "password" },
    });
    mockApi(routes);
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Ouvrir le menu" }));
    routes["GET /api/me/"] = apiError("not_authenticated", 403);
    await user.click(await screen.findByRole("button", { name: "Se déconnecter" }));

    expect(await screen.findByRole("heading", { name: "Se connecter" })).toBeTruthy();
  });
});

describe("école de l'adresse", () => {
  it("école suspendue : rien d'autre que le message (A1)", async () => {
    mockApi({ "GET /api/school/": apiError("school_suspended", 403) });
    renderApp("/");

    expect(await screen.findByText("L'accès à cette école est suspendu")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("adresse sans école", async () => {
    mockApi({ "GET /api/school/": apiError("school_not_found", 404) });
    renderApp("/");

    expect(await screen.findByText("Aucune école à cette adresse")).toBeTruthy();
  });

  it("pas de réseau au démarrage : message, puis « Réessayer »", async () => {
    offline();
    const { user } = renderApp("/");

    expect(await screen.findByText("Pas de connexion au serveur")).toBeTruthy();
    mockApi(loggedIn());
    await user.click(screen.getByRole("button", { name: "Réessayer" }));

    expect(await screen.findByRole("heading", { name: /Bonjour/ })).toBeTruthy();
  });

  it("erreur du serveur : « Un problème est survenu » avec le numéro", async () => {
    mockApi({ "GET /api/school/": apiError("server_error", 500) });
    renderApp("/");

    expect(await screen.findByText("Un problème est survenu")).toBeTruthy();
    expect(screen.getByText("Erreur 500")).toBeTruthy();
  });
});

describe("session", () => {
  it("session fermée pendant le travail : « Votre session a expiré »", async () => {
    const routes = loggedIn();
    mockApi(routes);
    const { queryClient } = renderApp("/");
    await screen.findByRole("heading", { name: /Bonjour/ });

    routes["GET /api/me/"] = apiError("not_authenticated", 403);
    await act(() => queryClient.invalidateQueries({ queryKey: keys.me }));

    expect(await screen.findByText("Votre session a expiré")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Se reconnecter" })).toBeTruthy();
  });

  it("la langue du compte s'applique à l'interface", async () => {
    mockApi(loggedIn(me("head", { language: "en" })));
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Hello Aline Test" })).toBeTruthy();
  });
});

describe("changer d'école (M2)", () => {
  const twoSchools = me("head", {
    schools: [
      schoolEntry(),
      schoolEntry({
        code: "beta",
        name: "École Beta (fictive)",
        url: "http://beta.localhost:5173",
        last_login_at: "2026-09-20T06:00:00Z",
      }),
      schoolEntry({ code: "gamma", name: "École Gamma (fictive)", status: "suspended" }),
    ],
  });

  it("le nom de l'école ouvre la liste des écoles du compte", async () => {
    mockApi(loggedIn(twoSchools));
    const { user } = renderApp("/");

    const [switcher] = await screen.findAllByRole("button", {
      name: `${school.name} — Changer d'école`,
    });
    await user.click(switcher!);

    const list = await screen.findByRole("menu");
    expect(
      within(list).getByRole("menuitem", { name: "École Beta (fictive)" }).getAttribute("href"),
    ).toBe("http://beta.localhost:5173/app/");
    expect(
      within(list)
        .getByRole("menuitem", { name: "École Gamma (fictive)" })
        .getAttribute("aria-disabled"),
    ).toBe("true");
    expect(within(list).getByRole("menuitem", { name: "Toutes mes écoles…" })).toBeTruthy();
  });

  it("une seule école : pas de liste", async () => {
    mockApi(loggedIn());
    renderApp("/");

    await screen.findByRole("heading", { name: /Bonjour/ });
    expect(screen.queryByRole("button", { name: /Changer d'école/ })).toBeNull();
  });

  it("aucun rôle dans l'école de l'adresse : choisir une école", async () => {
    mockApi(loggedIn({ ...twoSchools, school: null }));
    const { router } = renderApp("/");

    expect(await screen.findByRole("heading", { name: "Choisir l'école" })).toBeTruthy();
    expect(router.state.location.pathname).toBe("/schools");
    expect(screen.getByText(/Vous n.avez pas de rôle actif dans cette école/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Ouvrir/ }).getAttribute("href")).toBe(
      "http://beta.localhost:5173/app/",
    );
    // École suspendue, ou celle de cette adresse (aucun droit ici) : grisées, pas de lien.
    const unavailable = screen.getAllByRole("button", { name: "Indisponible" });
    expect(unavailable.map((button) => (button as HTMLButtonElement).disabled)).toEqual([
      true,
      true,
    ]);
  });
});
