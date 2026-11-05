import { defineConfig, devices } from "@playwright/test";

// Aperçu de tous les écrans (`make apercu`) : chaque écran des trois applications à 390, 820 et
// 1440 px, sur les données de `make demo` (pas remises à zéro : lancer `make demo` avant si
// besoin), avec le contrôle des débordements (`apercu/captures/rapport.json`). Sert à relire le
// design et l'adaptation à chaque taille d'écran ; pas dans la CI. Ses serveurs sont toujours
// lancés à neuf, sur des ports à lui (`adresses.ts`) : jamais un ancien serveur et son vieux code.
// Une action bloquée échoue en 15 s au lieu d'attendre la fin du test.
const backend = new URL("../../backend", import.meta.url).pathname;
const apiTarget = { VITE_API_TARGET: "http://127.0.0.1:8010" };

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
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  webServer: [
    {
      command: "uv run python manage.py runserver 8010 --noreload",
      cwd: backend,
      url: "http://127.0.0.1:8010/api/health/",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "./node_modules/.bin/vite --port 5183 --strictPort --host 127.0.0.1",
      cwd: new URL("../apps/gestion", import.meta.url).pathname,
      env: apiTarget,
      url: "http://127.0.0.1:5183/app/",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "./node_modules/.bin/vite --port 5184 --strictPort --host 127.0.0.1",
      cwd: new URL("../apps/portail", import.meta.url).pathname,
      env: apiTarget,
      url: "http://127.0.0.1:5184/",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "./node_modules/.bin/vite --port 5185 --strictPort --host 127.0.0.1",
      cwd: new URL("../apps/console", import.meta.url).pathname,
      env: apiTarget,
      url: "http://127.0.0.1:5185/",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
