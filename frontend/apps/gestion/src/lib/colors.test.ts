import { describe, expect, it } from "vitest";

import { INK, WHITE, contrast, nearbyReadable, normalizeColor, textColor } from "./colors";

// Mêmes cas que `backend/apps/schools/tests/test_colors.py` et `test_settings_api.py`.
describe("couleur de l'école", () => {
  it("contraste WCAG", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21);
    expect(contrast("#0E5C6B", INK)).toBeCloseTo(contrast(INK, "#0E5C6B"));
  });

  it("texte blanc ou encre, le plus lisible", () => {
    expect(textColor("#0E5C6B")).toBe(WHITE);
    expect(textColor("#003C6C")).toBe(WHITE);
    expect(textColor("#F2C94C")).toBe(INK);
    expect(textColor("#FF0000")).toBeNull();
  });

  it("teinte voisine proposée comme le serveur", () => {
    expect(nearbyReadable("#FF0000")).toBe("#ED0000");
    expect(nearbyReadable("#0E5C6B")).toBe("#0E5C6B");
    // Calculés par le serveur (`colors.nearby_readable`).
    expect(nearbyReadable("#888888")).toBe("#898989");
    expect(nearbyReadable("#E0457B")).toBe("#E35687");
    expect(nearbyReadable("#FF8800")).toBe("#FF8800");
  });

  it("format", () => {
    expect(normalizeColor(" #abc ")).toBe("#AABBCC");
    expect(normalizeColor("#0e5c6b")).toBe("#0E5C6B");
    expect(normalizeColor("bleu")).toBeNull();
    expect(normalizeColor("#12345")).toBeNull();
  });
});
