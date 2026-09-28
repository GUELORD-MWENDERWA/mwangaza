import { describe, expect, it } from "vitest";

import {
  formatAmount,
  formatAmountValue,
  formatRate,
  parseAmount,
  parseRate,
  percentOf,
  prorate,
  splitEvenly,
  sumAmounts,
} from "./index";

const NBSP = " ";

describe("montants", () => {
  it("affiche dollars et francs au format de l'école", () => {
    expect(formatAmount(123456, "USD")).toBe(`1${NBSP}234,56${NBSP}$`);
    expect(formatAmount(5, "USD")).toBe(`0,05${NBSP}$`);
    expect(formatAmount(1260000, "CDF")).toBe(`1${NBSP}260${NBSP}000${NBSP}FC`);
    expect(formatAmountValue(-3000, "USD")).toBe("−30,00");
  });

  it("lit une saisie sans jamais passer par un nombre à virgule", () => {
    expect(parseAmount("120,00", "USD")).toBe(12000);
    expect(parseAmount("0.29", "USD")).toBe(29);
    expect(parseAmount("1 234,5", "USD")).toBe(123450);
    expect(parseAmount(`1${NBSP}260${NBSP}000`, "CDF")).toBe(1260000);
    // Refusés : trop de décimales pour la devise, négatif, texte, vide, trop long.
    for (const [text, currency] of [
      ["12,345", "USD"],
      ["12,5", "CDF"],
      ["-10", "USD"],
      ["dix", "USD"],
      ["", "USD"],
      ["99999999999999", "CDF"],
    ] as const) {
      expect(parseAmount(text, currency)).toBeNull();
    }
    expect(() => sumAmounts([100, 0.5])).toThrow(TypeError);
  });

  it("découpe un total en parts entières dont la somme est le total", () => {
    expect(splitEvenly(100000, 3)).toEqual([33334, 33333, 33333]);
    expect(sumAmounts(splitEvenly(36001, 10))).toBe(36001);
    expect(splitEvenly(100, 0)).toEqual([]);
  });

  it("calcule une réduction comme le serveur : % arrondi demi supérieur, prorata exact", () => {
    expect(percentOf(12345, 10)).toBe(1235);
    expect(percentOf(36000, 25)).toBe(9000);
    expect(prorate(5000, [12000, 12000, 12000])).toEqual([1667, 1667, 1666]);
    expect(prorate(1000, [10000, 5000, 5000])).toEqual([500, 250, 250]);
    expect(prorate(2, [1, 1, 1])).toEqual([1, 1, 0]);
    expect(() => percentOf(1000, 12.5)).toThrow(TypeError);
  });

  it("lit et affiche le taux tel que saisi (francs pour 1 dollar)", () => {
    expect(parseRate("2 875,5")).toBe("2875.5");
    expect(parseRate("2850")).toBe("2850");
    expect(parseRate("0")).toBeNull();
    expect(parseRate("2850,1234567")).toBeNull();
    expect(formatRate("2850.000000")).toBe(`2${NBSP}850`);
    expect(formatRate("2875.500000")).toBe(`2${NBSP}875,5`);
  });
});
