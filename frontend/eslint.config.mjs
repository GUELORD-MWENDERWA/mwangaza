// ESLint (configuration plate) pour tout le front : applications et paquets.
// La mise en forme est laissée à Prettier (eslint-config-prettier coupe les règles de style).
import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import { defineConfig, globalIgnores } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig([
  globalIgnores(["**/dist/", "**/coverage/"]),
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    extends: [reactHooks.configs.flat.recommended],
    languageOptions: { globals: globals.browser },
  },
  {
    // Fichiers lus par Node : configurations de Vite, Vitest, ESLint.
    files: ["**/*.config.{ts,mjs,js}", "**/*.config.test.ts"],
    languageOptions: { globals: globals.node },
  },
  prettier,
]);
