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
      "staffNews",
      "calendar",
      "announcements",
      "summons",
      "parentRequests",
      "schoolSettings",
      "organisation",
      "staff",
      "roles",
      "devices",
      "audit",
    ]);
  });

  it("caissière : élèves, caisse, annulations, son appareil ; annonces et calendrier lus par tous", () => {
    expect(keysOf(me("cashier"))).toEqual([
      "students",
      "cash",
      "cancellations",
      "staffNews",
      "calendar",
      "devices",
    ]);
  });

  it("promoteur : lecture des finances et du journal", () => {
    expect(keysOf(me("promoter"))).toEqual([
      "dashboard",
      "students",
      "unpaid",
      "closings",
      "credits",
      "staffNews",
      "calendar",
      "devices",
      "audit",
    ]);
  });

  it("enseignant (aucun droit) : seulement ce que tout le personnel lit (5.7)", () => {
    expect(keysOf(me("teacher"))).toEqual(["staffNews", "calendar"]);
    expect(visibleMenu(me("teacher")).map(({ section }) => section)).toEqual(["communication"]);
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

  it("chaque entrée a une adresse unique ; sans droit : seulement ce que tout le personnel lit", () => {
    const paths = MENU_ITEMS.map((item) => item.path);
    expect(new Set(paths).size).toBe(paths.length);
    const open = MENU_ITEMS.filter((item) => item.permissions.length === 0);
    expect(open.map((item) => item.key)).toEqual(["staffNews", "calendar"]);
  });
});
