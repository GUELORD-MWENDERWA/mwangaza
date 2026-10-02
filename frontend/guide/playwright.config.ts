import { defineConfig, devices } from "@playwright/test";

// Guide de la version en PDF (`make guide`, I5) : captures des écrans de chaque rôle sur les
// données de `make demo` (remises à zéro avant et après), puis `guide.html` imprimé en PDF par
// Chromium. Pas dans la CI : lancé à la fin de chaque version. Des serveurs déjà lancés
// (`make dev-local`) sont réutilisés.
const backend = new URL("../../backend", import.meta.url).pathname;
const apiTarget = { VITE_API_TARGET: "http://127.0.0.1:8000" };

export default defineConfig({
  testDir: ".",
  globalSetup: "../e2e/global-setup.ts",
  workers: 1,
  fullyParallel: false,
  reporter: "list",
  timeout: 120_000,
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1.5,
    locale: "fr-FR",
    timezoneId: "Africa/Lubumbashi",
  },
  webServer: [
    {
      command: "uv run python manage.py runserver 8000 --noreload",
      cwd: backend,
      url: "http://127.0.0.1:8000/api/health/",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "./node_modules/.bin/vite --port 5173 --host 127.0.0.1",
      cwd: new URL("../apps/gestion", import.meta.url).pathname,
      env: apiTarget,
      url: "http://127.0.0.1:5173/app/",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "./node_modules/.bin/vite --port 5174 --host 127.0.0.1",
      cwd: new URL("../apps/portail", import.meta.url).pathname,
      env: apiTarget,
      url: "http://127.0.0.1:5174/",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
