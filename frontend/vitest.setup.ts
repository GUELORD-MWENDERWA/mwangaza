// Tests d'écrans : textes en français (langue par défaut), rien ne reste d'un test à l'autre.
import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { changeLanguage, setPlatformName, setupI18n } from "./packages/i18n/src";

setupI18n("fr");
// Nom de la plateforme dans les textes (`{{platform}}`), d'habitude lu sur le serveur.
setPlatformName("Mwangaza");

// Écrans lancés en parallèle (4 cœurs, comme la CI) : un écran met parfois plus d'une seconde à
// paraître. Une vraie absence échoue toujours, seulement un peu plus tard.
configure({ asyncUtilTimeout: 3000 });

// Ce que jsdom n'a pas et qu'utilisent les composants Radix (case à cocher, menus).
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
Element.prototype.scrollIntoView ??= () => {};
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};

afterEach(async () => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  localStorage.clear();
  for (const part of document.cookie.split("; ").filter(Boolean)) {
    document.cookie = `${part.split("=")[0]}=; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  }
  await changeLanguage("fr");
});
