import { describe, expect, it } from "vitest";

import { parseTenths, percent, periodTenths, serverTenths, toScore } from "./sheet";

describe("feuille de notes", () => {
  it("lit une note à une décimale, jamais au-dessus du maximum", () => {
    expect(parseTenths("7,5", 10)).toBe(75);
    expect(parseTenths(" 8 ", 10)).toBe(80);
    expect(parseTenths("", 10)).toBeNull();
    expect(parseTenths("10.5", 10)).toBeUndefined();
    expect(parseTenths("7,25", 10)).toBeUndefined();
    expect(parseTenths("-1", 10)).toBeUndefined();
    expect(toScore(75)).toBe("7.5");
    expect(serverTenths("18.0")).toBe(180);
  });

  it("ramène la somme au maximum de la période, au dixième, comme le serveur", () => {
    expect(periodTenths([80, 90, 140], [10, 10, 20], 20)).toBe(155);
    expect(periodTenths([100], [30], 20)).toBe(67);
    // La moitié vers le haut : 1 / 80 × 20 = 0,25.
    expect(periodTenths([10], [80], 20)).toBe(3);
    expect(periodTenths([80, null], [10, 10], 20)).toBeNull();
    expect(periodTenths([], [], 20)).toBeNull();
    expect(percent(155, 20)).toBe(78);
    expect(percent(90, 20)).toBe(45);
  });
});
