import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const CARD = fakeId(900);
const base = me("head");
const secretary = {
  ...base,
  school: {
    ...base.school!,
    permissions: ["attendance.cards" as const],
    modules: [...base.school!.modules, "attendance" as const],
  },
};
const card = {
  id: CARD,
  number: 303,
  last4: "7F3A",
  issued_at: "2026-11-06T08:00:00Z",
  valid_until: "2027-08-31",
  revoked_at: null,
  revoke_reason: "",
};
const student = (n: number, name: string, withCard: boolean) => ({
  student: fakeId(n),
  name,
  matricule: `ITIG-26-00${n}`,
  class_group: fakeId(40),
  class_name: "3HT Électricité A",
  photo: null,
  needs_reprint: false,
  card: withCard ? card : null,
  last_revoked: null,
});

function routes(): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": secretary,
    "GET /api/academic-years/": [{ id: fakeId(30), is_current: true, name: "2026-2027" }],
    "GET /api/attendance/cards/summary/": {
      students: 2,
      active: 1,
      missing: 1,
      lost_this_year: 0,
      to_reprint: 0,
    },
    "GET /api/attendance/cards/students/": {
      count: 2,
      next: null,
      previous: null,
      results: [student(1, "KAMBALE Josué", true), student(2, "KAVIRA Neema", false)],
    },
    "GET /api/class-groups/": [],
    "POST /api/attendance/cards/print/": {
      issued: 1,
      remaining: 0,
      without_photo: 0,
      url: "/api/attendance/cards/print/x/?output=pdf",
    },
    [`POST /api/attendance/cards/${CARD}/revoke/`]: { ...card, revoked_at: "2026-11-06T09:00:00Z" },
  };
}

describe("Cartes", () => {
  it("émet les cartes manquantes après avoir prévenu que le code n'est plus affiché", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/cards");

    await user.click(await screen.findByRole("button", { name: "Émettre les cartes manquantes" }));
    const dialog = screen.getByRole("dialog");
    within(dialog).getByText(/jamais gardé/);
    await user.click(within(dialog).getByRole("button", { name: "Émettre et imprimer" }));

    const sent = requests.find((request) => request.path === "/api/attendance/cards/print/");
    expect(sent?.body).toMatchObject({ missing: "students", layout: "sheet" });
  });

  it("déclare une carte perdue : seule une carte active a ce bouton", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/cards");

    await screen.findByText("KAVIRA Neema");
    const buttons = screen.getAllByRole("button", { name: "Déclarer perdue" });
    expect(buttons).toHaveLength(1);
    await user.click(buttons[0]!);
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Révoquer la carte" }),
    );

    const sent = requests.find(
      (request) => request.path === `/api/attendance/cards/${CARD}/revoke/`,
    );
    expect(sent?.body).toEqual({ reason: "lost" });
  });
});
