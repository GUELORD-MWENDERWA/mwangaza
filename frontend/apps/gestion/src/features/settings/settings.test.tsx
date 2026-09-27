import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiError, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const settings = {
  code: "alpha",
  name: "École Alpha (fictive)",
  official_name: "Institut Alpha",
  primary_color: "#0E5C6B",
  text_color: "#FFFFFF",
  logo: null,
  timezone: "Africa/Lubumbashi",
  enabled_currencies: ["USD", "CDF"],
  default_currency: "USD",
};

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/school/settings/": settings,
    ...extra,
  };
}

const card = async (title: string) =>
  within((await screen.findByRole("heading", { name: title })).closest("section")!);

describe("Paramètres de l'école (M5)", () => {
  it("enregistre les changements ; le code ne change que par le support", async () => {
    const all = routes();
    const requests = mockApi(all);
    const { user } = renderApp("/settings");

    const identity = await card("Identité de l'école");
    const address = identity.getByLabelText("Adresse de l'application") as HTMLInputElement;
    expect(address.readOnly).toBe(true);
    expect(identity.getByText("Modifiable seulement par le support Mwangaza.")).toBeTruthy();
    const name = identity.getByLabelText(/Nom court/);
    await user.clear(name);
    await user.type(name, "Institut Alpha");
    await user.selectOptions(identity.getByLabelText("Fuseau horaire"), "Africa/Kinshasa");
    all["PATCH /api/school/settings/"] = { ...settings, name: "Institut Alpha" };
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Paramètres enregistrés.")).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({
      name: "Institut Alpha",
      official_name: "Institut Alpha",
      timezone: "Africa/Kinshasa",
      primary_color: "#0E5C6B",
      enabled_currencies: ["USD", "CDF"],
      default_currency: "USD",
    });
    // Le nom de l'école (menu, connexion) est relu.
    await waitFor(() =>
      expect(requests.filter((r) => r.path === "/api/school/").length).toBeGreaterThan(1),
    );
  });

  it("couleur illisible : teinte voisine proposée, comme le serveur", async () => {
    mockApi(routes());
    const { user } = renderApp("/settings");

    const color = (await card("Logo et couleur")).getByLabelText("Couleur de l'école");
    await user.clear(color);
    await user.type(color, "#ff0000");

    expect(await screen.findByText(/Texte illisible sur cette couleur.*#ED0000/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Utiliser #ED0000" }));
    expect((color as HTMLInputElement).value).toBe("#ED0000");
    expect(screen.queryByText(/Texte illisible/)).toBeNull();
  });

  it("refus du serveur sous le champ, traduit par son code", async () => {
    mockApi(
      routes({
        "PATCH /api/school/settings/": apiError("invalid", 400, {
          fields: { primary_color: [{ code: "invalid_color", detail: "Enter a colour." }] },
        }),
      }),
    );
    const { user } = renderApp("/settings");

    await card("Logo et couleur");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Couleur au format #RRGGBB, ex. #0E5C6B.")).toBeTruthy();
  });

  it("devises : au moins une ; la devise principale suit", async () => {
    mockApi(routes());
    const { user } = renderApp("/settings");

    const currencies = await card("Devises");
    await user.click(currencies.getByRole("switch", { name: /Dollar américain/ }));
    expect(
      (currencies.getByLabelText("Devise principale des rapports") as HTMLSelectElement).value,
    ).toBe("CDF");
    await user.click(currencies.getByRole("switch", { name: /Franc congolais/ }));
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await currencies.findByText("Gardez au moins une devise.")).toBeTruthy();
  });

  it("logo envoyé aussitôt ; refus traduit", async () => {
    const all = routes({
      "POST /api/school/settings/logo/": apiError("invalid", 400, {
        fields: { logo: [{ code: "logo_too_large", detail: "Too large." }] },
      }),
    });
    const requests = mockApi(all);
    const { user } = renderApp("/settings");

    // `FormData` et fichier de Node : le `Request` de Node ne lit pas ceux de jsdom.
    const form = await new Response(new URLSearchParams("a=b")).formData();
    vi.stubGlobal("FormData", form.constructor);
    const blob = await new Response("png", { headers: { "Content-Type": "image/png" } }).blob();
    const file = Object.assign(blob, { name: "logo.png" }) as unknown as File;
    const logo = await card("Logo et couleur");
    await user.upload(logo.getByLabelText("Changer", { selector: "input" }), file);
    expect(await logo.findByText("Le logo dépasse 1 Mo.")).toBeTruthy();

    all["POST /api/school/settings/logo/"] = { ...settings, logo: "/api/school/logo/?v=1" };
    await user.upload(logo.getByLabelText("Changer", { selector: "input" }), file);
    expect(await logo.findByText("Logo enregistré.")).toBeTruthy();
    expect(logo.getByRole("img", { name: "Logo de l'école" })).toBeTruthy();
    const sent = requests.filter((r) => r.path === "/api/school/settings/logo/");
    expect(sent).toHaveLength(2);
    expect(sent[1]!.body).toContain('name="logo"');
  });

  it("sans le droit : page refusée, rien n'est lu", async () => {
    const requests = mockApi(routes({ "GET /api/me/": me("cashier") }));
    renderApp("/settings");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/school/settings/")).toBe(false);
  });
});
