import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const CLASS = "01a14955-0000-7000-8000-000000000001";
const NEXT_1RE = "01a14955-0000-7000-8000-000000000002";
const NEXT_2E = "01a14955-0000-7000-8000-000000000003";
const year = { id: "y1", name: "2026-2027", starts_on: "2026-09-01" };
const following = { id: "y2", name: "2027-2028", starts_on: "2027-09-01" };

function row(enrollment: string, name: string, extra: Record<string, unknown>) {
  return {
    enrollment,
    student: `s-${enrollment}`,
    full_name: name,
    matricule: "",
    decision: "pass",
    percent: "61.5",
    proposal: "next_level",
    proposed_class: NEXT_2E,
    place: null,
    enrolled_class: null,
    on_portal: true,
    ...extra,
  };
}

const passage = {
  class_name: "1re ELEC A",
  year,
  following,
  proclaimed_on: "2027-06-25",
  targets: [
    { id: NEXT_1RE, name: "1re ELEC A" },
    { id: NEXT_2E, name: "2e ELEC A" },
  ],
  counts: { students: 3, offered: 1, yes: 1 },
  students: [
    row("e-amani", "Amani X", {}),
    row("e-josue", "Josue X", {
      decision: "repeat",
      proposal: "same_level",
      proposed_class: NEXT_1RE,
      place: {
        class_group: NEXT_1RE,
        class_name: "1re ELEC A",
        status: "offered",
        answer: "yes",
        answered_at: "2027-07-12T08:00:00Z",
      },
    }),
    row("e-kavira", "Kavira X", { decision: "resit", proposal: "waiting", proposed_class: null }),
  ],
};

describe("passage de classe (8.4.5)", () => {
  it("propose la place choisie, puis inscrit seulement une place déjà proposée", async () => {
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/promotion/": {
        year,
        following,
        classes: [{ id: CLASS, name: "1re ELEC A", proclaimed_on: "2027-06-25", counts: {} }],
      },
      [`GET /api/class-groups/${CLASS}/promotion/`]: passage,
      [`POST /api/class-groups/${CLASS}/promotion/offer/`]: passage,
      [`POST /api/class-groups/${CLASS}/promotion/enroll/`]: passage,
    });
    const { user } = renderApp("/promotion");
    const posted = (tail: string) =>
      requests.find((request) => request.method === "POST" && request.path.endsWith(tail))?.body;

    // En repêchage : pas de place, rien à choisir.
    expect(await screen.findByLabelText("Choisir Amani X")).toBeTruthy();
    expect(screen.queryByLabelText("Choisir Kavira X")).toBeNull();

    await user.click(screen.getByLabelText("Choisir Amani X"));
    expect(screen.getByRole("button", { name: "Inscrire en 2027-2028 (0)" })).toHaveProperty(
      "disabled",
      true,
    );
    await user.click(screen.getByRole("button", { name: "Proposer la place (1)" }));
    expect(posted("offer/")).toEqual({ places: [{ enrollment: "e-amani", class_group: NEXT_2E }] });

    // Choix remis à zéro une fois la proposition enregistrée.
    await screen.findByRole("button", { name: "Proposer la place (0)" });
    await user.click(screen.getByLabelText("Choisir Josue X"));
    await user.click(screen.getByRole("button", { name: "Inscrire en 2027-2028 (1)" }));
    expect(posted("enroll/")).toEqual({ enrollments: ["e-josue"] });
  });

  it("n'apparaît pas dans le menu d'une école sans le module des notes", async () => {
    const head = me("head");
    mockApi({
      "GET /api/school/": school,
      "GET /api/me/": { ...head, school: { ...head.school!, modules: ["students", "finance"] } },
    });
    renderApp("/");
    expect(await screen.findByRole("link", { name: /Élèves/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Passage de classe/ })).toBeNull();
  });
});
