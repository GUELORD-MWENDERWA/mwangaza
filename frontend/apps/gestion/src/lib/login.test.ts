import { describe, expect, it } from "vitest";

import { safeNext, stepPath } from "./login";

describe("connexion en étapes", () => {
  it("page de chaque étape, avec la page demandée au départ", () => {
    expect(stepPath("password", "/")).toBe("/login");
    expect(stepPath("totp", "/account")).toBe("/login/code?next=%2Faccount");
    expect(stepPath("new_password", "/")).toBe("/login/new-password");
    expect(stepPath("totp_setup", "/support")).toBe("/login/two-factor?next=%2Fsupport");
    expect(stepPath("done", "/account")).toBe("/account");
  });

  it("retour après la connexion : seulement une page de l'application", () => {
    expect(safeNext("/account?tab=2")).toBe("/account?tab=2");
    expect(safeNext(null)).toBe("/");
    expect(safeNext("https://autre.example/")).toBe("/");
    expect(safeNext("//autre.example/")).toBe("/");
    expect(safeNext("/login/code")).toBe("/");
  });
});
