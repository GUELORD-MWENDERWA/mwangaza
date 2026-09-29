import { describe, expect, it } from "vitest";

import { me, PERMISSIONS } from "../test/fixtures";
import { MENU_ITEMS, visibleMenu } from "./menu";

const keysOf = (account: ReturnType<typeof me>) =>
  visibleMenu(account).flatMap(({ items }) => items.map((item) => item.key));

describe("menu selon les permissions (04 § 8)", () => {
  it("directeur : tout le menu V1.0 sauf la caisse", () => {
    expect(keysOf(me("head"))).toEqual([
      "dashboard",
      "students",
      "unpaid",
      "fees",
      "cancellations",
      "closings",
      "credits",
      "announcements",
      "parentRequests",
      "schoolSettings",
      "organisation",
      "staff",
      "roles",
      "devices",
      "audit",
    ]);
  });

  it("caissière : élèves, caisse, annulations et son appareil seulement", () => {
    expect(keysOf(me("cashier"))).toEqual(["students", "cash", "cancellations", "devices"]);
  });

  it("promoteur : lecture des finances et du journal", () => {
    expect(keysOf(me("promoter"))).toEqual([
      "dashboard",
      "students",
      "unpaid",
      "closings",
      "credits",
      "devices",
      "audit",
    ]);
  });

  it("enseignant (aucun droit en V1.0) : aucune entrée, aucune section vide", () => {
    expect(visibleMenu(me("teacher"))).toEqual([]);
  });

  it("session support : droits de l'école sauf la caisse", () => {
    const all = [...new Set(Object.values(PERMISSIONS).flat())];
    const support = all.filter(
      (permission) =>
        ![
          "finance.collect_payment",
          "finance.request_cancellation",
          "finance.approve_cancellation",
          "finance.close_register",
        ].includes(permission),
    );
    const account = me("head", {
      school: { code: "alpha", name: "École Alpha (fictive)", roles: [], permissions: support },
    });

    expect(keysOf(account)).not.toContain("cash");
    expect(keysOf(account)).not.toContain("cancellations");
  });

  it("chaque entrée a une adresse unique et au moins un droit", () => {
    const paths = MENU_ITEMS.map((item) => item.path);
    expect(new Set(paths).size).toBe(paths.length);
    for (const item of MENU_ITEMS) expect(item.permissions.length, item.key).toBeGreaterThan(0);
  });
});
