import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const terms = {
  id: "d1",
  kind: "terms",
  version: 2,
  published_at: "2026-11-01T08:00:00Z",
  title_fr: "Conditions générales",
  title_en: "Terms",
  body_fr: "Article 1",
  body_en: "Article 1",
};

const routes = (account: ReturnType<typeof me>): Routes => ({
  "GET /api/school/": school,
  "GET /api/me/": account,
  "GET /api/legal/pending/": [terms],
});

describe("acceptation des conditions (CTR.1)", () => {
  it("proposée à l'administrateur, qui coche avant d'accepter", async () => {
    mockApi({
      ...routes(me("head")),
      "POST /api/legal/accept/": new Response(null, { status: 204 }),
    });
    renderApp("/");
    const accept = (await screen.findByRole("button", { name: "Accepter" })) as HTMLButtonElement;
    expect(screen.getByText("Conditions mises à jour")).toBeTruthy();
    expect(accept.disabled).toBe(true);
    await userEvent.click(screen.getByRole("checkbox"));
    expect(accept.disabled).toBe(false);
  });

  it("jamais demandée à un membre sans le droit « rôles » : le serveur n'est même pas interrogé", async () => {
    const requests = mockApi(routes(me("cashier")));
    renderApp("/");
    await screen.findAllByRole("navigation", { name: "Menu principal" });
    expect(screen.queryByText("Conditions mises à jour")).toBeNull();
    expect(requests.some((r) => r.path === "/api/legal/pending/")).toBe(false);
    cleanup();
  });
});
