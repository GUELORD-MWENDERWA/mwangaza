import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { enablePush } from "../../lib/push";
import { ACCOUNT, ITIG } from "../../test/fixtures";
import { mockApi, renderApp } from "../../test/render";

// Pas de service worker dans les tests : l'abonnement du navigateur est simulé.
vi.mock("../../lib/push", () => ({
  pushState: vi.fn(async () => "off"),
  enablePush: vi.fn(async () => "on"),
  disablePush: vi.fn(async () => undefined),
}));

const notification = (id: string, title: string, school_name: string) => ({
  id,
  kind: "test",
  title,
  body: "Les nouvelles des écoles de vos enfants s'afficheront ici.",
  url: "/notifications",
  created_at: "2026-10-01T08:00:00Z",
  read_at: null,
  school_name,
  school_timezone: "Africa/Lubumbashi",
});

describe("Notifications du portail", () => {
  it("montre celles de toutes les écoles, compte les non lues, active ce téléphone et marque lue", async () => {
    const results = [
      notification("n2", "Essai du matin", "Les Volcans"),
      notification("n1", "Essai de la veille", "ITIG Don Bosco Goma"),
    ];
    const requests = mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG],
      "GET /api/portal/notifications/": { count: 2, next: null, previous: null, results },
      "GET /api/portal/notifications/preferences/": {
        vapid_public_key: "cle-publique",
        kinds: [],
        muted: [],
      },
      "POST /api/portal/notifications/read/": new Response(null, { status: 204 }),
    });
    const { user } = renderApp("/notifications");

    expect(await screen.findByText("Essai du matin")).toBeTruthy();
    expect(screen.getByText(/Les Volcans/)).toBeTruthy();
    expect(screen.getByText(/ITIG Don Bosco Goma/)).toBeTruthy();
    expect(await screen.findByRole("link", { name: "Notifications : 2 non lues" })).toBeTruthy();

    await user.click(await screen.findByRole("button", { name: "Activer sur cet appareil" }));
    expect(enablePush).toHaveBeenCalledWith("cle-publique");
    expect(await screen.findByText("Activées")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /Essai du matin/ }));
    await waitFor(() =>
      expect(requests.filter((r) => r.method === "POST").map((r) => r.body)).toContainEqual({
        ids: ["n2"],
      }),
    );
  });
});
