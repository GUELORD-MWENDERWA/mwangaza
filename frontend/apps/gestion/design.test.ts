// Système de design (skill `design`) : tailles de texte de l'échelle et couleurs des jetons seulement.
// Une taille `text-[.87rem]` ou une couleur `bg-[#…]` écrite dans le code, c'est le design qui dérive
// écran après écran : ajouter le jeton au thème (`packages/ui/src/styles.css`) et l'utiliser.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND = fileURLToPath(new URL("../..", import.meta.url));
const ROOTS = ["apps/gestion/src", "apps/portail/src", "apps/console/src", "packages/ui/src"].map(
  (dir) => join(FRONTEND, dir),
);
const RULES: [string, RegExp][] = [
  ["taille de texte hors échelle (text-xs … text-3xl)", /\btext-\[\d*\.?\d+(?:rem|px|em)\]/g],
  ["couleur hors jetons", /-\[(?:#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|oklch\()[^\]]*\]/g],
];

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "test" ? [] : sources(path);
    return /\.tsx?$/.test(entry.name) && !entry.name.includes(".test.") ? [path] : [];
  });
}

describe("système de design", () => {
  it("aucune taille de texte ni couleur écrite en dur dans les classes", () => {
    const found: string[] = [];
    for (const root of ROOTS) {
      for (const file of sources(root)) {
        const code = readFileSync(file, "utf8");
        for (const [rule, pattern] of RULES) {
          for (const match of code.matchAll(pattern))
            found.push(`${relative(FRONTEND, file)} : ${match[0]} (${rule})`);
        }
      }
    }
    expect(found).toEqual([]);
  });
});
