import { defineConfig, devices } from "@playwright/test";

// Aperçu de tous les écrans (`make apercu`) : chaque écran des trois applications à 390, 820 et
// 1440 px, sur les données de `make demo` (pas remises à zéro : lancer `make demo` avant si
// besoin), avec le contrôle des débordements (`apercu/captures/rapport.json`). Sert à relire le
// design et l'adaptation à chaque taille d'écran ; pas dans la CI. Des serveurs déjà lancés
// (`make dev-local`) sont réutilisés.
const backend = new URL("../../backend", import.meta.url).pathname;
const apiTarget = { VITE_API_TARGET: "http://127.0.0.1:8000" };

export default defineConfig({
  testDir: ".",
  workers: 1,
  fullyParallel: false,
  reporter: "list",
  timeout: 600_000,
  use: {
    ...devices["Desktop Chrome"],
    deviceScaleFactor: 1,
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
    {
      command: "./node_modules/.bin/vite --port 5175 --host 127.0.0.1",
      cwd: new URL("../apps/console", import.meta.url).pathname,
      env: apiTarget,
      url: "http://127.0.0.1:5175/",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
