import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const ARTICLE = {
  key: "take-payment",
  title: "Encaisser un paiement",
  summary: "Recevoir l'argent d'un parent.",
  group: "cash",
  group_label: "Caisse",
  roles: ["Caissier"],
  minutes: 2,
  updated: "2026-11-04",
  html: "<p>Cherchez l'élève.</p>",
  url: "https://example.org/aide/encaisser-un-paiement/",
  related: [],
  title_html: "",
  excerpt_html: "",
};
const NEWS = {
  day: "2026-11-04",
  summary: "Un bouton « Aide » sur chaque écran.",
  html: "<ul><li>Aide sur chaque écran.</li></ul>",
  url: "https://example.org/aide/nouveautes/",
};

describe("bouton « Aide » et « Quoi de neuf » (AIDE.1, AIDE.2)", () => {
  beforeEach(() => localStorage.clear());

  it("le panneau montre l'article de l'écran ouvert", async () => {
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("cashier"),
      "GET /api/help/gestion/take-payment/": ARTICLE,
    });
    const { user } = renderApp("/cash");

    await user.click(await screen.findByRole("button", { name: "Aide" }));

    expect(await screen.findByRole("heading", { name: ARTICLE.title })).toBeTruthy();
    expect(screen.getByText("Cherchez l'élève.")).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/help/gestion/take-payment/")).toBe(true);
  });

  it("« Quoi de neuf » s'ouvre une fois par compte, puis plus", async () => {
    mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/help/whats-new/": NEWS,
    });
    const first = renderApp("/");
    await first.user.click(await screen.findByRole("button", { name: "Compris" }));
    expect(screen.queryByRole("button", { name: "Compris" })).toBeNull();
    first.unmount();

    renderApp("/");
    await screen.findByRole("button", { name: "Aide" });
    expect(screen.queryByRole("button", { name: "Compris" })).toBeNull();
  });
});
