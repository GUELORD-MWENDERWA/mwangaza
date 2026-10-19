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
  platform_permissions: [RIGHTS.siteEdit, RIGHTS.newsPublish],
};

const entry = (id: string, kind: string, title_fr: string, extra = {}) => ({
  id,
  kind,
  title_fr,
  title_en: "",
  text_fr: "Réponse.",
  text_en: "",
  position: 1,
  published: true,
  updated_at: "2026-10-18T07:42:00Z",
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe("Site public dans la console", () => {
  it("garde le menu de la communication, ajoute une question à la bonne page et monte une ligne", async () => {
    const requests = mockApi({
      "GET /api/me/": COMMUNICATION,
      "GET /api/console/site/entries/": [
        entry("h1", "home_question", "Faut-il internet ?", { title_en: "Need internet?" }),
        entry("h2", "home_question", "Combien ça coûte ?", { published: false }),
        entry("p1", "parent_question", "J'ai perdu mon code"),
        entry("u1", "upcoming", "Mobile Money"),
      ],
      "POST /api/console/site/entries/": entry("p2", "parent_question", "Deux écoles ?"),
      "POST /api/console/site/entries/h2/move/": [],
    });
    const { user } = renderApp("/site");

    expect(await screen.findByText("Faut-il internet ?")).toBeTruthy();
    // Menu réduit aux droits du membre ; les écoles n'y sont pas.
    const menu = screen.getAllByRole("navigation")[0] as HTMLElement;
    expect(within(menu).getByRole("link", { name: "Site" })).toBeTruthy();
    expect(within(menu).queryByRole("link", { name: "Écoles" })).toBeNull();
    // Brouillon, et sans anglais : le français s'affiche.
    expect(screen.getByText("Brouillon")).toBeTruthy();
    expect(screen.getByText("Anglais : le français s'affiche")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Monter « Combien ça coûte ? »" }));
    expect(requests.find((r) => r.path.endsWith("/move/"))?.body).toEqual({ direction: "up" });

    await user.click(screen.getByRole("radio", { name: "Parents · 1" }));
    await user.type(screen.getAllByLabelText("Question")[0] as HTMLElement, "Deux écoles ?");
    await user.type(screen.getAllByLabelText("Réponse")[0] as HTMLElement, "Un seul compte.");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    const post = requests.find(
      (r) => r.method === "POST" && r.path === "/api/console/site/entries/",
    );
    expect(post?.body).toMatchObject({
      kind: "parent_question",
      title_fr: "Deux écoles ?",
      text_fr: "Un seul compte.",
      title_en: "",
      published: false,
    });
  });
});
