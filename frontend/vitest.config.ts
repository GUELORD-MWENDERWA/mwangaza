import { defineConfig } from "vitest/config";

// Appareil en UTC : sur une machine de Goma (UTC+2), une heure affichée dans le fuseau de
// l'appareil au lieu de celui de l'école passerait inaperçue.
process.env.TZ = "UTC";

// Tests du front : `*.test.ts` (logique, Node) et `*.test.tsx` (écrans, navigateur simulé jsdom
// avec Testing Library). Parcours réels avec le serveur : Playwright (`e2e/`, `make test-e2e`).
export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify("test") },
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
    projects: [
      {
        extends: true,
        test: {
          name: "logique",
          environment: "node",
          include: ["apps/*/**/*.test.ts", "packages/*/**/*.test.ts"],
        },
      },
      {
        extends: true,
        test: {
          name: "écrans",
          environment: "jsdom",
          include: ["apps/*/**/*.test.tsx", "packages/*/**/*.test.tsx"],
          setupFiles: ["./vitest.setup.ts"],
        },
      },
    ],
  },
});
