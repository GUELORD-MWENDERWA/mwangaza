// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import { changeLanguage, setPlatformName, setupI18n } from "./index";

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

describe("nom de la plateforme", () => {
  it("vient de ses paramètres, dans chaque langue, sans être écrit dans les textes", async () => {
    setupI18n("fr");
    setPlatformName("Lumière");
    expect(i18next.t("roles.support")).toBe("Support Lumière");

    await changeLanguage("en");
    expect(i18next.t("roles.support")).toBe("Lumière support");
  });
});
