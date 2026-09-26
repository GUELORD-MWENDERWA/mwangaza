import { ApiError } from "@mwangaza/api";
import { setupI18n } from "@mwangaza/i18n";
import { describe, expect, it } from "vitest";

import { errorMessage, fieldMessage } from "./errors";

const { t } = setupI18n("fr");

describe("messages d'erreur (traduits par leur code, jamais le texte du serveur)", () => {
  it("code connu", () => {
    const error = new ApiError(400, "invalid_credentials", "Wrong phone number or password.");
    expect(errorMessage(error, t)).toBe("Numéro de téléphone ou mot de passe incorrect.");
  });

  it("trop d'essais : le temps d'attente en minutes", () => {
    expect(errorMessage(new ApiError(429, "too_many_attempts", "", {}, 600), t)).toBe(
      "Trop d'essais ratés. Réessayez dans 10 minutes.",
    );
    expect(errorMessage(new ApiError(429, "too_many_attempts", "", {}, 30), t)).toBe(
      "Trop d'essais ratés. Réessayez dans 1 minute.",
    );
  });

  it("pas de réseau", () => {
    expect(errorMessage(new ApiError(0, "network", ""), t)).toContain("Pas de connexion");
  });

  it("code inconnu : message général avec le code, pour le support", () => {
    expect(errorMessage(new ApiError(500, "http_500", "boom"), t)).toContain("(http_500)");
    expect(errorMessage(new Error("boom"), t)).toContain("(js)");
  });

  it("erreur d'un champ", () => {
    expect(fieldMessage("password_too_short", t)).toBe("Au moins 10 caractères.");
    expect(fieldMessage("something_new", t)).toBe("Valeur refusée.");
  });
});
