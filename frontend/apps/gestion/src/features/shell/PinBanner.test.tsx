import { cleanup, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { localDevice, type LocalDevice } from "../../lib/device";
import { mockApi } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

// Pas d'IndexedDB dans jsdom : l'appareil mémorisé est donné par le test.
vi.mock("../../lib/device", async (original) => ({
  ...(await original<typeof import("../../lib/device")>()),
  localDevice: vi.fn(),
}));

const device = { user: me().id, id: "d1", prefix: "A1" } as unknown as LocalDevice;
const banner = { name: "Travailler sans internet sur cet appareil" };

describe("bandeau « Travailler sans internet » (L.6)", () => {
  it("appareil mémorisé sans PIN : proposé, mène à la carte de Mon compte ; avec PIN : rien", async () => {
    mockApi({ "GET /api/school/": school, "GET /api/me/": me("cashier") });
    vi.mocked(localDevice).mockResolvedValue(device);
    renderApp("/");

    const region = await screen.findByRole("region", banner);
    const link = screen.getByRole("link", { name: "Choisir mon code PIN" });
    expect(region.contains(link) && link.getAttribute("href")?.endsWith("/account#pin")).toBe(true);

    cleanup();
    vi.mocked(localDevice).mockResolvedValue({
      ...device,
      pin: { salt: "s", hash: "h", iterations: 1 },
    });
    renderApp("/");

    expect(await screen.findByRole("heading", { name: /Bonjour/ })).toBeTruthy();
    expect(screen.queryByRole("region", banner)).toBeNull();
  });
});
