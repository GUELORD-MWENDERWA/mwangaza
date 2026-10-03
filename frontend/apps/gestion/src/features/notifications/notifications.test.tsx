import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, noContent } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const NEWS = {
  id: "n1",
  kind: "platform_news",
  title: "Maintenance du serveur samedi soir",
  body: "L'application sera indisponible samedi de 22 h à minuit.",
  url: "/platform-news",
  created_at: "2026-10-02T08:00:00Z",
  read_at: null,
};
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});
const PREFERENCES = { vapid_public_key: "cle", kinds: ["platform_news"], muted: [] };

describe("notifications (5.5)", () => {
  it("cloche → centre : toucher une notification la note comme lue et ouvre l'écran lié", async () => {
    let read = false;
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("cashier"),
      "GET /api/notifications/": (request) =>
        new URL(request.url).searchParams.get("unread") && read
          ? page([])
          : page([{ ...NEWS, read_at: read ? NEWS.created_at : null }]),
      "POST /api/notifications/read/": () => {
        read = true;
        return noContent();
      },
      "GET /api/notifications/preferences/": PREFERENCES,
      "GET /api/platform-announcements/": page([]),
    });
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("link", { name: "Notifications : 1 non lue" }));
    const row = await screen.findByRole("button", { name: /Maintenance du serveur/ });
    expect(within(row).getByText("Nouvelle")).toBeTruthy();
    await user.click(row);

    expect(await screen.findByRole("heading", { name: /^Annonces de/ })).toBeTruthy();
    const posts = requests.filter((r) => r.method === "POST");
    expect(posts.map((r) => r.body)).toEqual([{ ids: ["n1"] }]);
    expect(await screen.findByRole("link", { name: "Notifications" })).toBeTruthy();
  });

  it("couper une sorte : préférence du compte enregistrée, la liste la garde", async () => {
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/notifications/": page([]),
      "GET /api/notifications/preferences/": PREFERENCES,
      "PUT /api/notifications/preferences/": { ...PREFERENCES, muted: ["platform_news"] },
    });
    const { user } = renderApp("/notifications");

    const toggle = await screen.findByRole("switch", { name: /^Annonces de/ });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    await user.click(toggle);

    expect(requests.find((r) => r.method === "PUT")?.body).toEqual({ muted: ["platform_news"] });
    expect(
      (await screen.findByRole("switch", { name: /^Annonces de/ })).getAttribute("aria-checked"),
    ).toBe("false");
  });
});
