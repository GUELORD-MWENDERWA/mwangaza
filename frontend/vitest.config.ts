import { defineConfig } from "vitest/config";

// Tests du front : `*.test.ts(x)` des applications et des paquets.
// Environnement Node pour l'instant ; les tests de composants (navigateur simulé) arrivent en 1.6.
export default defineConfig({
  test: {
    include: ["apps/*/**/*.test.{ts,tsx}", "packages/*/**/*.test.{ts,tsx}"],
    exclude: ["**/node_modules/**", "**/dist/**"],
  },
});
