import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { UpdatePrompt } from "./UpdatePrompt";

const sync = vi.hoisted(() => ({ pending: 2, syncNow: vi.fn(async () => {}) }));
vi.mock("../../lib/sync/session", () => ({
  useSyncStatus: () => ({ pending: sync.pending }),
  syncNow: sync.syncNow,
}));

afterEach(() => {
  vi.unstubAllEnvs();
});

it("nouvelle version avec des opérations en attente : installée seulement une fois la file vide (M8)", async () => {
  // Application construite, une version en service et la suivante installée, en attente.
  vi.stubEnv("PROD", true);
  const waiting = { state: "installed", postMessage: vi.fn(), addEventListener: vi.fn() };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      controller: {},
      register: async () => ({ waiting, addEventListener: vi.fn(), update: vi.fn() }),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    },
  });
  const { rerender } = render(<UpdatePrompt />);

  await userEvent.click(await screen.findByRole("button", { name: "Mettre à jour" }));
  expect(sync.syncNow).toHaveBeenCalled();
  expect(waiting.postMessage).not.toHaveBeenCalled();

  sync.pending = 0;
  rerender(<UpdatePrompt />);
  expect(waiting.postMessage).toHaveBeenCalledWith({ type: "SKIP_WAITING" });
});
