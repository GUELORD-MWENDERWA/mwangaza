import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const base = me("head");
const withRights = (permissions: ("attendance.view" | "attendance.correct")[]) => ({
  ...base,
  school: {
    ...base.school!,
    permissions,
    modules: [...base.school!.modules, "attendance" as const],
  },
});
const JUSTIFICATION = fakeId(800);

function routes(permissions: ("attendance.view" | "attendance.correct")[]): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": withRights(permissions),
    "GET /api/academic-years/": [{ id: fakeId(30), is_current: true, name: "2026-2027" }],
    "GET /api/class-groups/": [],
    "GET /api/attendance/day/": {
      date: "2026-11-09",
      school_day: true,
      holiday: false,
      enrolled: 42,
      present: 38,
      late: 2,
      absent: 2,
      justified: 1,
      pending: 1,
      rate: 95,
      staff_present: 46,
      staff_total: 52,
      late_after: "07:30",
      parents_notified_at: null,
      alert_after: 3,
      classes: [],
    },
    "GET /api/attendance/absences/": {
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          student_id: fakeId(1),
          name: "SAFARI Patrick",
          matricule: "ITIG-26-0001",
          class_name: "3HT Mécanique",
          state: "absent",
          unjustified: 3,
          parent_on_portal: true,
          justification_id: null,
        },
      ],
    },
    "GET /api/attendance/justifications/": {
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: JUSTIFICATION,
          student_name: "SAFARI Patrick",
          starts_on: "2026-11-09",
          ends_on: "2026-11-09",
          reason: "Malade",
          source: "portal",
          status: "pending",
          has_document: false,
          decided_at: null,
          decided_by_name: "",
          decision_note: "",
          created_at: "2026-11-09T08:00:00Z",
        },
      ],
    },
    "POST /api/attendance/corrections/": { id: fakeId(5) },
    [`POST /api/attendance/justifications/${JUSTIFICATION}/decide/`]: { id: JUSTIFICATION },
  };
}

describe("Suivi des présences", () => {
  it("corrige un absent : le motif est obligatoire et part avec l'élève et le jour", async () => {
    const requests = mockApi(routes(["attendance.view", "attendance.correct"]));
    const { user } = renderApp("/follow");

    await user.click(await screen.findByRole("tab", { name: "Absents à suivre" }));
    await user.click(await screen.findByRole("button", { name: "Corriger" }));
    const dialog = screen.getByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Corriger" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    await user.type(within(dialog).getByLabelText("Motif"), "Présent en classe, carte oubliée");
    await user.click(confirm);

    const sent = requests.find((request) => request.path === "/api/attendance/corrections/");
    expect(sent?.body).toMatchObject({
      student: fakeId(1),
      status: "present",
      reason: "Présent en classe, carte oubliée",
    });
  });

  it("sans le droit de corriger, aucun bouton d'écriture", async () => {
    mockApi(routes(["attendance.view"]));
    const { user } = renderApp("/follow");

    await user.click(await screen.findByRole("tab", { name: "Absents à suivre" }));
    await screen.findByText("SAFARI Patrick");
    expect(screen.queryByRole("button", { name: "Corriger" })).toBeNull();
    await user.click(screen.getByRole("tab", { name: /Justifications/ }));
    await screen.findByText("Malade");
    expect(screen.queryByRole("button", { name: "Accepter" })).toBeNull();
  });

  it("refuse une justification avec une réponse au parent", async () => {
    const requests = mockApi(routes(["attendance.view", "attendance.correct"]));
    const { user } = renderApp("/follow");

    await user.click(await screen.findByRole("tab", { name: /Justifications/ }));
    await user.click(await screen.findByRole("button", { name: "Refuser" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Réponse au parent"), "Certificat exigé");
    await user.click(within(dialog).getByRole("button", { name: "Refuser" }));

    const sent = requests.find(
      (request) => request.path === `/api/attendance/justifications/${JUSTIFICATION}/decide/`,
    );
    expect(sent?.body).toEqual({ accept: false, note: "Certificat exigé" });
  });
});
