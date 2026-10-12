import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId as id, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const student = {
  id: id(70),
  last_name: "Kasereka",
  middle_name: "Muhindo",
  first_name: "Jean",
  matricule: "ITIG-2026-0042",
  enrollment: { class_group_name: "3e Électricité A" },
};
const summons = {
  id: id(400),
  student: { id: id(71), full_name: "AMANI Furaha Grâce", matricule: "ITIG-2026-0007" },
  class_name: "4e Électronique A",
  reason: "Absences répétées.",
  meeting_at: "2026-10-20T08:00:00Z",
  meet_with: "Directeur de discipline",
  seen_at: "2026-10-13T17:02:00Z",
  cancelled_at: null,
  issued_by: null,
  created_at: "2026-10-12T09:00:00Z",
};

describe("Convocations", () => {
  it("un élève choisi, un jour, une heure : convocation envoyée, lettre à imprimer", async () => {
    const requests = mockApi({
      "GET /api/me/": me("study_director"),
      "GET /api/school/": school,
      "GET /api/summons/": { count: 1, next: null, previous: null, results: [summons] },
      "GET /api/students/": { count: 1, next: null, previous: null, results: [student] },
      "POST /api/summons/": {
        ...summons,
        id: id(401),
        student: { id: student.id, full_name: "KASEREKA Muhindo Jean", matricule: "" },
        seen_at: null,
      },
    });
    const { user } = renderApp("/summons");

    expect(await screen.findByText("AMANI Furaha Grâce")).toBeTruthy();
    expect(screen.getByText("Vue par le parent")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Convoquer les parents" }));
    expect(await screen.findByText("Choisissez un élève.")).toBeTruthy();

    await user.type(screen.getByLabelText("Élève"), "kase");
    await user.click(await screen.findByRole("button", { name: /KASEREKA MUHINDO Jean/ }));
    await user.type(screen.getByLabelText("Jour"), "2026-10-22");
    await user.type(screen.getByLabelText("Heure"), "10:00");
    await user.type(screen.getByLabelText("Personne à voir"), "Préfet des études");
    await user.type(screen.getByLabelText("Motif"), "Résultats de la période.");
    await user.click(screen.getByRole("button", { name: "Convoquer les parents" }));

    expect(await screen.findByText(/Convocation enregistrée pour KASEREKA/)).toBeTruthy();
    const [sent] = requests.filter((r) => r.method === "POST");
    expect(sent!.body).toEqual({
      student: student.id,
      meet_with: "Préfet des études",
      reason: "Résultats de la période.",
      meeting_at: new Date("2026-10-22T10:00").toISOString(),
    });
    await waitFor(() =>
      expect(
        screen.getAllByRole("link", { name: "Lettre à imprimer (PDF)" })[0]!.getAttribute("href"),
      ).toBe(`/api/summons/${id(401)}/letter/`),
    );
  });
});
