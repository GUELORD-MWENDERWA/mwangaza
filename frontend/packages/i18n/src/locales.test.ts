import { describe, expect, it } from "vitest";

import { en } from "./locales/en";
import { fr } from "./locales/fr";

type Tree = { [key: string]: string | Tree };

function flatten(tree: Tree, prefix = ""): Record<string, string> {
  return Object.fromEntries(
    Object.entries(tree).flatMap(([key, value]) =>
      typeof value === "string"
        ? [[`${prefix}${key}`, value]]
        : Object.entries(flatten(value, `${prefix}${key}.`)),
    ),
  );
}

const french = flatten(fr);
const english = flatten(en);

describe("traductions", () => {
  it("l'anglais a exactement les clés du français", () => {
    expect(Object.keys(english).sort()).toEqual(Object.keys(french).sort());
  });

  it("aucun texte vide", () => {
    for (const [key, value] of [...Object.entries(french), ...Object.entries(english)]) {
      expect(value.trim(), key).not.toBe("");
    }
  });

  it("mêmes valeurs à insérer et mêmes balises dans les deux langues", () => {
    const marks = (text: string) =>
      [...text.matchAll(/\{\{(\w+)\}\}|<(\/?\w+)>/g)].map((match) => match[0]).sort();
    for (const [key, value] of Object.entries(french)) {
      expect(marks(english[key] ?? ""), key).toEqual(marks(value));
    }
  });
});
