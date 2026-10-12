import { ApiError } from "@mwangaza/api";
import type { TFunction } from "i18next";
import { describe, expect, it } from "vitest";

import { errorMessage } from "./errors";

const t = ((key: string, options?: object) =>
  `${key} ${JSON.stringify(options ?? {})}`) as unknown as TFunction;

describe("message d'une erreur du serveur", () => {
  it("refus métier sans message à l'écran : la phrase du serveur ; panne : le message général", () => {
    const detail = "Un espace de démonstration n'accepte que des numéros fictifs.";
    const refused = new ApiError(400, "demo_space_numbers", detail, {}, null, {
      code: "demo_space_numbers",
      detail,
    });
    expect(errorMessage(refused, t)).toBe(detail);

    const known = new ApiError(409, "already_member", "x", {}, null, { code: "already_member" });
    expect(errorMessage(known, t)).toBe("errors.already_member {}");

    const down = new ApiError(502, "http_502", "Bad Gateway");
    expect(errorMessage(down, t)).toBe('errors.unknown {"code":"http_502"}');
  });
});
