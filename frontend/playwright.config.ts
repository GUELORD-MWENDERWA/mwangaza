import { defineConfig, devices } from "@playwright/test";

// Parcours réels dans Chromium : Django (données de `make demo`, remises à zéro au début), la
// Gestion (Vite), aux adresses des écoles ({code}.localhost), le portail des parents (localhost)
// et la console (admin.localhost).
// `make test-e2e` ; en CI, un job à part. Sur la machine, des serveurs déjà lancés
// (`make dev-local`) sont réutilisés.
const backend = new URL("../backend", import.meta.url).pathname;

export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/global-setup.ts",
  // Comptes de démonstration partagés, et un code de double authentification ne sert qu'une
  // fois : un parcours après l'autre.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  timeout: 60_000,
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    locale: "fr-FR",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    // Adresses en 127.0.0.1 : Django n'écoute pas en IPv6 (`localhost` = `::1` d'abord).
    {
      command: "uv run python manage.py runserver 8000 --noreload",
      cwd: backend,
      url: "http://127.0.0.1:8000/api/health/",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Sans `pnpm exec` : pnpm lancerait Vite hors du groupe de processus que Playwright arrête
      // à la fin, qui attendrait alors sans fin.
      // En IPv4, comme Django : sur la CI, `localhost` désigne d'abord `::1`.
      command: "./node_modules/.bin/vite --port 5173 --host 127.0.0.1",
      cwd: new URL("apps/gestion", import.meta.url).pathname,
      env: { VITE_API_TARGET: "http://127.0.0.1:8000" },
      url: "http://127.0.0.1:5173/app/",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Portail des parents (parcours « école neuve » : le parent voit son reçu).
      command: "./node_modules/.bin/vite --port 5174 --host 127.0.0.1",
      cwd: new URL("apps/portail", import.meta.url).pathname,
      env: { VITE_API_TARGET: "http://127.0.0.1:8000" },
      url: "http://127.0.0.1:5174/",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Console de la plateforme (super-admin), à admin.localhost.
      command: "./node_modules/.bin/vite --port 5175 --host 127.0.0.1",
      cwd: new URL("apps/console", import.meta.url).pathname,
      env: { VITE_API_TARGET: "http://127.0.0.1:8000" },
      url: "http://127.0.0.1:5175/",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
