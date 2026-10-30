import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RIGHTS } from "../../lib/rights";
import { mockApi, renderApp } from "../../test/render";

const COMMUNICATION = {
  id: "c1",
  phone: "+243000000002",
  last_name: "Kahindo",
  middle_name: "",
  first_name: "Amani",
  language: "fr",
  is_platform_admin: true,
  platform_roles: ["communication"],
  platform_permissions: [RIGHTS.siteEdit],
};

const article = (id: string, title: string, state: string, extra = {}) => ({
  id,
  language: "fr",
  title,
  slug: "",
  url: null,
  summary: "Résumé.",
  body: "Texte.",
  photo: null,
  author_name: "",
  status: state === "draft" ? "draft" : "published",
  published_at: state === "draft" ? null : "2026-11-04T08:00:00Z",
  state,
  updated_by: null,
  updated_at: "2026-10-29T10:00:00Z",
  ...extra,
});

const page = (key: string, extra = {}) => ({
  key,
  title_fr: "",
  title_en: "",
  description_fr: "",
  description_en: "",
  photo: null,
  has_photo_slot: key !== "news",
  updated_at: "2026-10-29T10:00:00Z",
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe("Actualités et photothèque dans la console", () => {
  it("montre l'état de chaque article et ses effectifs, avec le droit du site seulement", async () => {
    mockApi({
      "GET /api/me/": COMMUNICATION,
      "GET /api/console/site/articles/": {
        count: 2,
        next: null,
        previous: null,
        results: [
          article("a1", "Mobile Money : ce qui se prépare", "scheduled"),
          article("a2", "Brouillon sur les bulletins", "draft"),
        ],
      },
      "GET /api/console/site/articles/counts/": { all: 2, draft: 1, scheduled: 1, published: 0 },
    });
    renderApp("/news");

    expect(await screen.findByText("Mobile Money : ce qui se prépare")).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Programmés · 1" })).toBeTruthy();
    const list = screen.getAllByRole("list")[0] as HTMLElement;
    expect(within(list).getByText("Programmé")).toBeTruthy();
    expect(within(list).getByText("Brouillon")).toBeTruthy();
  });

  it("n'enregistre que les titres de recherche changés", async () => {
    const requests = mockApi({
      "GET /api/me/": COMMUNICATION,
      "GET /api/console/site/entries/": [],
      "GET /api/console/site/pages/": [page("home"), page("schools")],
      "PATCH /api/console/site/pages/schools/": page("schools", { title_fr: "Logiciel à Goma" }),
    });
    const { user } = renderApp("/site");

    await user.click(await screen.findByRole("tab", { name: "Titres de recherche" }));
    await user.type(await screen.findByLabelText(/Titre dans Google | Écoles/), "Logiciel à Goma");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    const patches = requests.filter((r) => r.method === "PATCH");
    expect(patches).toHaveLength(1);
    expect(patches[0]?.path).toBe("/api/console/site/pages/schools/");
    expect(patches[0]?.body).toEqual({ title_fr: "Logiciel à Goma" });
  });

  it("change la photo du haut d'une page depuis la photothèque", async () => {
    const photo = {
      id: "11111111-1111-4111-8111-111111111111",
      url: "/api/platform/photos/x-1600.webp",
      small_url: "/api/platform/photos/x-600.webp",
      width: 1600,
      height: 1000,
      alt_fr: "Élèves en uniforme",
      alt_en: "Pupils in uniform",
      credit: "Institut Les Volcans",
      source_url: "",
      license: "consent",
      recognizable: false,
      has_consent: true,
      uses: 0,
      created_at: "2026-10-29T10:00:00Z",
    };
    const requests = mockApi({
      "GET /api/me/": COMMUNICATION,
      "GET /api/console/site/pages/": [page("home"), page("news")],
      "GET /api/console/site/photos/": { count: 1, next: null, previous: null, results: [photo] },
      "PATCH /api/console/site/pages/home/": page("home", { photo: photo.id }),
    });
    const { user } = renderApp("/photos");

    await user.click(await screen.findByRole("button", { name: "Choisir…" }));
    await user.click(await screen.findByRole("button", { name: /Élèves en uniforme/ }));

    const patch = requests.find((r) => r.method === "PATCH");
    expect(patch?.path).toBe("/api/console/site/pages/home/");
    expect(patch?.body).toEqual({ photo: photo.id });
    // La page des actualités n'a pas de photo à choisir.
    expect(screen.getAllByRole("button", { name: "Choisir…" })).toHaveLength(1);
  });
});
