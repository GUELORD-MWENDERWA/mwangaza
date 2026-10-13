import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { InstallGate } from "./InstallGate";
import { canSkip, installRequired, MAX_DISMISSALS } from "./installGate";

function openedAs(standalone: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: standalone && query.includes("standalone"),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  openedAs(false);
});
afterEach(() => vi.unstubAllEnvs());

it("l'écran s'impose dans un onglet de l'application construite, pas en développement ni installée (4.24)", () => {
  expect(installRequired()).toBe(false); // développement et parcours Playwright
  vi.stubEnv("PROD", true);
  expect(installRequired()).toBe(true);
  openedAs(true); // ouverte depuis l'icône
  expect(installRequired()).toBe(false);
});

it("issue de secours : après 2 refus, sur iPhone ou sans invite du navigateur, pas avant", () => {
  const base = { dismissed: 0, ios: false, waited: false };
  expect(canSkip(base)).toBe(false);
  expect(canSkip({ ...base, dismissed: MAX_DISMISSALS - 1 })).toBe(false);
  expect(canSkip({ ...base, dismissed: MAX_DISMISSALS })).toBe(true);
  expect(canSkip({ ...base, ios: true })).toBe(true);
  expect(canSkip({ ...base, waited: true })).toBe(true);
});

it("l'issue de secours ouvre l'application pour la session seulement", async () => {
  vi.stubEnv("PROD", true);
  localStorage.setItem("mwangaza.install.dismissals", String(MAX_DISMISSALS));
  const first = render(
    <InstallGate>
      <p>Connexion</p>
    </InstallGate>,
  );
  expect(screen.queryByText("Connexion")).toBeNull();

  await userEvent.click(screen.getByRole("button", { name: /Continuer dans le navigateur/ }));
  expect(screen.getByText("Connexion")).toBeTruthy();

  // Même session : pas de nouvel écran ; nouvelle session du navigateur : il revient.
  first.unmount();
  const second = render(
    <InstallGate>
      <p>Connexion</p>
    </InstallGate>,
  );
  expect(screen.getByText("Connexion")).toBeTruthy();
  second.unmount();
  sessionStorage.clear();
  render(
    <InstallGate>
      <p>Connexion</p>
    </InstallGate>,
  );
  expect(screen.queryByText("Connexion")).toBeNull();
});
