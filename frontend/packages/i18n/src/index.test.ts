// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import { changeLanguage, setupI18n } from "./index";

describe("langue envoyée au serveur", () => {
  it("français par défaut, puis la langue choisie, même avec un navigateur en anglais", async () => {
    expect(navigator.language).toMatch(/^en/);

    setupI18n();
    expect(document.cookie).toContain("django_language=fr");

    await changeLanguage("en");
    expect(document.cookie).toContain("django_language=en");
    expect(document.documentElement.lang).toBe("en");
  });
});
