import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const DEVICE = "00000000-0000-7000-8000-000000000001";
const device = {
  id: DEVICE,
  label: "Windows · Chrome",
  prefix: "P2",
  created_at: "2026-10-01T07:00:00Z",
  last_seen_at: "2026-10-19T08:47:00Z",
  is_current: false,
  kind: "browser",
  user_name: "ZAWADI Alice",
};

function routes(role: "head" | "cashier"): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me(role),
    "GET /api/devices/": { count: 1, next: null, previous: null, results: [device] },
  };
}

describe("Appareils et synchro", () => {
  it("un responsable révoque un appareil de l'école, après l'avertissement sur la file perdue", async () => {
    const requests = mockApi({
      ...routes("head"),
      [`POST /api/devices/${DEVICE}/revoke/`]: new Response(null, { status: 204 }),
    });
    const { user } = renderApp("/devices");

    await user.click(await screen.findByRole("button", { name: "Révoquer" }));
    const dialog = screen.getByRole("dialog");
    within(dialog).getByText(/pas encore envoyé \(encaissements, reçus\) sera perdu/);
    await user.click(within(dialog).getByRole("button", { name: "Révoquer" }));

    const sent = requests.filter((request) => request.method === "POST");
    expect(sent.map((request) => request.path)).toEqual([`/api/devices/${DEVICE}/revoke/`]);
  });

  it("un caissier voit cet appareil, jamais les appareils de l'école", async () => {
    const requests = mockApi(routes("cashier"));
    renderApp("/devices");

    await screen.findByText(/n'est pas mémorisé/);
    expect(screen.queryByRole("heading", { name: "Appareils de l'école" })).toBeNull();
    expect(requests.some((request) => request.path === "/api/devices/")).toBe(false);
  });
});
