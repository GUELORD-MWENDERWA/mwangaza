// Aide (AIDE.2) : chaque écran de la table a son article, en français et en anglais.
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { HELP_SCREENS as consoleScreens } from "../console/src/features/shell/helpScreens";
import { HELP_SCREENS as portalScreens } from "../portail/src/features/home/PortalHelp";
import { HELP_SCREENS as gestionScreens } from "./src/features/shell/helpScreens";

const HELP = fileURLToPath(new URL("../../../backend/apps/core/help", import.meta.url));

describe("aide : table écran → article", () => {
  it.each([
    ["gestion", gestionScreens],
    ["portail", portalScreens],
    ["console", consoleScreens],
  ])("chaque écran de %s a son article fr + en", (app, screens) => {
    const keys = [...new Set(Object.values(screens))];
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const lang of ["fr", "en"]) {
        expect(existsSync(`${HELP}/${lang}/${app}/${key}.md`), `${lang}/${app}/${key}`).toBe(true);
      }
    }
  });
});
