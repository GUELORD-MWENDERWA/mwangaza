import { describe, expect, it } from "vitest";

import { amountInWords } from "./index";

describe("amountInWords", () => {
  it("écrit les nombres selon l'orthographe traditionnelle", () => {
    const words = (francs: number) => amountInWords(francs, "CDF");
    expect(words(0)).toBe("Zéro franc congolais");
    expect(words(1)).toBe("Un franc congolais");
    expect(words(21)).toBe("Vingt et un francs congolais");
    expect(words(71)).toBe("Soixante et onze francs congolais");
    expect(words(80)).toBe("Quatre-vingts francs congolais");
    expect(words(91)).toBe("Quatre-vingt-onze francs congolais");
    expect(words(100)).toBe("Cent francs congolais");
    expect(words(200)).toBe("Deux cents francs congolais");
    expect(words(80_000)).toBe("Quatre-vingt mille francs congolais");
    expect(words(285_000)).toBe("Deux cent quatre-vingt-cinq mille francs congolais");
    expect(words(1_000_000)).toBe("Un million de francs congolais");
    expect(words(1_280_001)).toBe("Un million deux cent quatre-vingt mille un francs congolais");
    expect(words(200_000_000)).toBe("Deux cents millions de francs congolais");
  });

  it("ajoute les centimes des dollars", () => {
    expect(amountInWords(15000, "USD")).toBe("Cent cinquante dollars américains");
    expect(amountInWords(15025, "USD")).toBe(
      "Cent cinquante dollars américains et vingt-cinq centimes",
    );
    expect(amountInWords(101, "USD")).toBe("Un dollar américain et un centime");
  });
});
