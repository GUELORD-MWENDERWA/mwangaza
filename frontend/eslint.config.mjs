// ESLint (configuration plate) pour tout le front : applications et paquets.
// La mise en forme est laissée à Prettier (eslint-config-prettier coupe les règles de style).
import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import { defineConfig, globalIgnores } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig([
  // `schema.d.ts` : généré par `make api` (openapi-typescript).
  globalIgnores([
    "**/dist/",
    "**/coverage/",
    "test-results/",
    "playwright-report/",
    "packages/api/src/schema.d.ts",
  ]),
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    extends: [reactHooks.configs.flat.recommended],
    languageOptions: { globals: globals.browser },
  },
  {
    // Fichiers lus par Node : configurations de Vite, Vitest, ESLint, Playwright ; `e2e/` et `guide/`.
    files: [
      "**/*.config.{ts,mjs,js}",
      "**/*.config.test.ts",
      "e2e/**",
      "guide/**",
      "vitest.setup.ts",
    ],
    languageOptions: { globals: globals.node },
  },
  {
    // Ajouts au service worker des applications (`workbox.importScripts`) : notifications (5.5).
    files: ["apps/*/public/**/*.js"],
    languageOptions: { globals: globals.serviceworker },
  },
  prettier,
]);
