import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiError, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

// Règles de délibération : préréglage « courant » (NB.4).
const RULES = {
  pass_percent: 50,
  course_pass_percent: 50,
  resit_percent: 50,
  max_resit_courses: 4,
  max_main_resits: 1,
  max_option_resits: 4,
  practical_resit: false,
  final_pass_percent: 0,
  orientation_percent: 40,
  age_exception_years: 0,
  age_exception_percent: 40,
  age_limit: 0,
  exclude_repeated_class: true,
  max_repeats: 0,
  conduct_ma_to_exclude: 2,
  conduct_me_to_exclude: 3,
  application_counts: false,
  resit_failures_to_fail: 2,
};

const settings = {
  code: "alpha",
  name: "École Alpha (fictive)",
  official_name: "Institut Alpha",
  primary_color: "#0B5FCC",
  text_color: "#FFFFFF",
  logo: null,
  logo_monochrome: null,
  timezone: "Africa/Lubumbashi",
  enabled_currencies: ["USD", "CDF"],
  default_currency: "USD",
  receipt: { printer: "thermal_80", sheet_size: "half", header: "", footer: "" },
  alerts: {
    difference_minor: { USD: 1000, CDF: 20000 },
    cancellations_per_day: 3,
    closing_time: "18:00",
  },
  reminders: { enabled: false, days_before: 3, overdue_every_days: 7 },
  portal: { teacher_phone: false },
  grading: { entry: "detailed" },
  pass_rules: RULES,
  pass_rule_presets: { common: RULES, catholic: { ...RULES, resit_percent: 53 } },
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
  it("enregistre les changements et les réglages du reçu ; le code ne change que par le support", async () => {
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
    // Reçus : la hauteur de la feuille seulement pour une imprimante ordinaire.
    const receipt = await card("Reçus");
    expect(receipt.queryByLabelText("Hauteur de la feuille")).toBeNull();
    await user.click(receipt.getByRole("radio", { name: "Feuille A4" }));
    await user.selectOptions(receipt.getByLabelText("Hauteur de la feuille"), "third");
    await user.type(receipt.getByLabelText(/Lignes d'en-tête/), "Av. du Lac 1{Enter}Goma");
    // Seuil d'écart saisi comme à la caisse, envoyé en centimes.
    const alerts = await card("Alertes au directeur");
    expect((alerts.getByLabelText(/FC/) as HTMLInputElement).value).toMatch(/^20\s000$/);
    const usd = alerts.getByLabelText(/\$/);
    await user.clear(usd);
    await user.type(usd, "12,50");
    // Relances aux parents : désactivées tant que l'école ne les active pas.
    const reminders = await card("Relances aux parents");
    await user.click(reminders.getByRole("switch", { name: /Envoyer les relances/ }));
    const before = reminders.getByLabelText(/Échéance proche/);
    await user.clear(before);
    await user.type(before, "5");
    // Règles de délibération : le préréglage « réseau catholique » remplit le formulaire.
    const rules = await card("Règles de délibération");
    await user.click(rules.getAllByRole("button", { name: "Appliquer" })[1]!);
    all["PATCH /api/school/settings/"] = { ...settings, name: "Institut Alpha" };
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Paramètres enregistrés.")).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({
      name: "Institut Alpha",
      official_name: "Institut Alpha",
      timezone: "Africa/Kinshasa",
      primary_color: "#0B5FCC",
      enabled_currencies: ["USD", "CDF"],
      default_currency: "USD",
      head_name: "",
      head_title: "",
      epst_code: "",
      province: "",
      city: "",
      commune: "",
      regime: "",
      receipt: {
        printer: "sheet",
        sheet_size: "third",
        header: "Av. du Lac 1\nGoma",
        footer: "",
      },
      alerts: {
        difference_minor: { USD: 1250, CDF: 20000 },
        cancellations_per_day: 3,
        closing_time: "18:00",
      },
      reminders: { enabled: true, days_before: 5, overdue_every_days: 7 },
      portal: { teacher_phone: false },
      grading: { entry: "detailed" },
      pass_rules: { ...RULES, resit_percent: 53 },
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

    expect(await screen.findByText(/Texte illisible sur cette couleur.*#FF0F0F/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Utiliser #FF0F0F" }));
    expect((color as HTMLInputElement).value).toBe("#FF0F0F");
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

    expect(await screen.findByText("Couleur au format #RRGGBB, ex. #0B5FCC.")).toBeTruthy();
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
        fields: { logo: [{ code: "image_too_large", detail: "Too large." }] },
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
    expect(await logo.findByText("L'image dépasse 1 Mo.")).toBeTruthy();

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
