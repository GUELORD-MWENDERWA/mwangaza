import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OWNER, mockApi, renderApp } from "../../test/render";

const ADMIN = {
  id: "a1",
  phone: "+243000000000",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
  ...OWNER,
};

const DEVICE = {
  id: "d1",
  label: "Windows · Edge",
  kind: "browser",
  prefix: "P1",
  school: { id: "s1", code: "alpha", name: "École Alpha" },
  user: { id: "u1", name: "Kasereka Dieudonné" },
  created_at: "2026-09-01T08:00:00Z",
  last_seen_at: "2026-10-03T09:12:00Z",
  revoked_at: null,
};

afterEach(() => vi.unstubAllGlobals());

describe("Appareils de la console", () => {
  it("déconnecte un appareil seulement après confirmation, en service par défaut", async () => {
    let revoked = false;
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/devices/": () => ({
        count: 1,
        next: null,
        previous: null,
        results: [revoked ? { ...DEVICE, revoked_at: "2026-10-03T10:00:00Z" } : DEVICE],
      }),
      "POST /api/console/devices/d1/revoke/": () => {
        revoked = true;
        return { ...DEVICE, revoked_at: "2026-10-03T10:00:00Z" };
      },
    });
    const { user } = renderApp("/devices");

    await user.click(await screen.findByRole("button", { name: "Déconnecter" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Kasereka Dieudonné, École Alpha/)).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "Déconnecter" }));

    expect(await screen.findByText(/Déconnecté le/)).toBeTruthy();
    expect(requests.filter((r) => r.method === "POST")).toHaveLength(1);
    expect(requests.find((r) => r.path === "/api/console/devices/")?.search).toContain(
      "state=active",
    );
  });
});
