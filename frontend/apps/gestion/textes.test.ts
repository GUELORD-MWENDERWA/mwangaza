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
// Nom de départ de la plateforme (`PlatformSettings`) : lu dans ses paramètres, jamais écrit.
const PLATFORM = "Mwangaza";
const FRONTEND = fileURLToPath(new URL("../..", import.meta.url));

function sources(dir: string, pattern = /\.tsx$/): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "test" ? [] : sources(path, pattern);
    return pattern.test(entry.name) && !entry.name.includes(".test.") ? [path] : [];
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
        for (const text of texts) found.push(`${relative(root, file)} : ${text.trim()}`);
      }
    }
    expect(found).toEqual([]);
  });
});

describe("nom de la plateforme", () => {
  it("n'est écrit ni dans les traductions, ni dans les écrans, ni dans les pages et manifestes", () => {
    const files = [
      ...["apps/gestion/src", "apps/portail/src", "packages/ui/src", "packages/i18n/src"].flatMap(
        (dir) => sources(join(FRONTEND, dir), /\.tsx?$/),
      ),
      ...["gestion", "portail"].flatMap((app) => [
        join(FRONTEND, "apps", app, "index.html"),
        join(FRONTEND, "apps", app, "vite.config.ts"),
      ]),
    ];
    const found = files.filter((file) =>
      readFileSync(file, "utf8")
        .replace(/\/\*[\s\S]*?\*\/|\/\/.*$|<!--[\s\S]*?-->/gm, "")
        .includes(PLATFORM),
    );
    expect(found.map((file) => relative(FRONTEND, file))).toEqual([]);
  });
});
