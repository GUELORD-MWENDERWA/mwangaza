// Règle 7 : aucun texte d'interface écrit dans le code ; tout passe par les traductions.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Écrans de la Gestion et composants partagés (hors tests).
const ROOTS = [
  fileURLToPath(new URL("src", import.meta.url)),
  fileURLToPath(new URL("../../packages/ui/src", import.meta.url)),
];
// Nom de la marque, jamais traduit (`Brand`).
const ALLOWED = new Set(["Mwangaza"]);

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "test" ? [] : sources(path);
    return /\.tsx$/.test(entry.name) && !entry.name.includes(".test.") ? [path] : [];
  });
}

describe("textes d'interface", () => {
  it("aucun texte entre balises ni dans label, placeholder, title, aria-label, alt", () => {
    const found: string[] = [];
    for (const root of ROOTS) {
      for (const file of sources(root)) {
        const code = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, "");
        const texts = [
          // Texte entre deux balises (sans code : ni parenthèse, ni `=`, ni `?`, ni `;`…).
          ...[...code.matchAll(/>([^<>{}();=?:"&|]*\p{L}{2,}[^<>{}();=?:"&|]*)</gu)].map(
            (m) => m[1]!,
          ),
          ...[
            ...code.matchAll(/\b(?:label|placeholder|title|aria-label|alt)="([^"]*\p{L}[^"]*)"/gu),
          ].map((m) => m[1]!),
        ];
        for (const text of texts) {
          if (!ALLOWED.has(text.trim())) found.push(`${relative(root, file)} : ${text.trim()}`);
        }
      }
    }
    expect(found).toEqual([]);
  });
});
