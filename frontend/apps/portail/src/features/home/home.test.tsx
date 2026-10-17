import { cleanup, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCOUNT, ITIG } from "../../test/fixtures";
import { apiError, mockApi, renderApp } from "../../test/render";

const VOLCANS = {
  id: "f2",
  school_name: "C.S. Les Volcans",
  school_timezone: "Africa/Lubumbashi",
  school_environment: "live",
  school_modules: ["students", "finance", "communication", "portal"],
  status: "suspended",
  children: [],
};

describe("accueil du portail", () => {
  it("une carte par enfant avec la situation de son école ; famille suspendue : rien de ses enfants", async () => {
    mockApi({ "GET /api/portal/me/": ACCOUNT, "GET /api/portal/families/": [ITIG, VOLCANS] });
    renderApp("/");

    await screen.findByText("KASEREKA Muhindo Jean");
    expect(screen.getByText("ITIG Don Bosco Goma · 3e Électricité A")).toBeTruthy();
    // (Testing Library lit les espaces insécables des montants comme des espaces.)
    // Retards par devise, jamais additionnés ; le plus ancien frais en retard.
    expect(screen.getByText("70,00 $ + 25 000 FC")).toBeTruthy();
    expect(screen.getByText(/\(Fonctionnement\)/)).toBeTruthy();
    expect(screen.getByText("50,00 $ sur 360,00 $")).toBeTruthy();
    expect(screen.getByText("0 FC sur 25 000 FC")).toBeTruthy();
    expect(screen.getByText("C.S. Les Volcans")).toBeTruthy();
    expect(screen.getByText(/L'école a suspendu l'accès au portail/)).toBeTruthy();
  });

  it("une école de démonstration ou d'essai affiche son bandeau, une école réelle non", async () => {
    mockApi({ "GET /api/portal/me/": ACCOUNT, "GET /api/portal/families/": [ITIG] });
    renderApp("/");
    await screen.findByText("KASEREKA Muhindo Jean");
    expect(screen.queryByText(/Démonstration|Essai —/)).toBeNull();
    cleanup();

    mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [{ ...ITIG, school_environment: "demo" }],
    });
    renderApp("/");
    expect(await screen.findByText("Démonstration — données fictives")).toBeTruthy();
  });

  it("le menu ne propose que ce que l'école a : sans frais ni annonces, ni Paiements ni Annonces", async () => {
    mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [{ ...ITIG, school_modules: ["students", "portal"] }],
    });
    renderApp("/");
    await screen.findByText("KASEREKA Muhindo Jean");
    expect(screen.getByRole("link", { name: "Calendrier" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Paiements" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Annonces" })).toBeNull();
  });

  it("place de l'année suivante : le parent répond, puis peut changer d'avis", async () => {
    const place = {
      id: "p1",
      student: "s1",
      full_name: "MASIKA Ruth",
      sex: "F",
      school_name: "ITIG Don Bosco Goma",
      school_timezone: "Africa/Lubumbashi",
      year_name: "2027-2028",
      starts_on: "2027-09-01",
      class_name: "4HT Électronique A",
      answer: "",
      answered_at: null,
    };
    const routes: Record<string, object> = {
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG],
      "GET /api/portal/places/": [place],
      "PUT /api/portal/places/p1/": { ...place, answer: "no" },
    };
    const requests = mockApi(routes);
    const { user } = renderApp("/");

    expect(await screen.findByText(/Revient-elle \?/)).toBeTruthy();
    routes["GET /api/portal/places/"] = [
      { ...place, answer: "no", answered_at: "2027-07-12T08:00:00Z" },
    ];
    await user.click(screen.getByRole("button", { name: "Non, elle ne revient pas" }));
    expect(requests.find((r) => r.method === "PUT")?.body).toEqual({ answer: "no" });
    expect(await screen.findByText("Vous avez répondu : ne revient pas · 12/07/2027")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Changer" }));
    expect(screen.getByRole("button", { name: "Oui, elle revient" })).toBeTruthy();
  });

  it("ajouter une autre école : le code envoyé, l'erreur du serveur traduite", async () => {
    const requests = mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG],
      "GET /api/auth/csrf/": {},
      "POST /api/portal/families/link/": apiError("invalid_link_code", 400),
    });
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("link", { name: /Ajouter un enfant/ }));
    await user.type(await screen.findByLabelText("Code famille"), "ydtn-y79c");
    await user.click(screen.getByRole("button", { name: "Ajouter" }));

    await screen.findByText(/Code famille inconnu, ou cette école a un autre numéro/);
    expect(requests.find((r) => r.path === "/api/portal/families/link/")?.body).toEqual({
      code: "ydtn-y79c",
    });
  });
});
