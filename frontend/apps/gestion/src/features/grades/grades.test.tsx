import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, type Routes } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const COURSE = fakeId(1);
const PERIOD = fakeId(2);
const FIRST = fakeId(3);
const SECOND = fakeId(4);
const AMANI = fakeId(5);
const JOSUE = fakeId(6);

const grading = {
  academic_year: fakeId(9),
  terms: [
    {
      id: fakeId(10),
      kind: "semester",
      name: "",
      starts_on: null,
      ends_on: null,
      children: [{ id: PERIOD, kind: "period", name: "", starts_on: null, ends_on: null }],
    },
  ],
  classes: [
    {
      id: fakeId(20),
      name: "3e Électricité A",
      courses: [{ id: COURSE, name: "Électrotechnique", period_max: 20, has_exam: true }],
    },
  ],
};

const sheet = {
  course: grading.classes[0]!.courses[0],
  class_group: "3e Électricité A",
  term: PERIOD,
  maximum: 20,
  evaluations: [
    { id: FIRST, name: "Interrogation 1", max_score: 10 },
    { id: SECOND, name: "Interrogation 2", max_score: 10 },
  ],
  students: [
    {
      enrollment_id: AMANI,
      full_name: "BAHATI AMANI Christian",
      matricule: "",
      status: "active",
      scores: [
        { evaluation_id: FIRST, score: "8.0" },
        { evaluation_id: SECOND, score: "9.0" },
      ],
      total: "17.0",
    },
    {
      enrollment_id: JOSUE,
      full_name: "KAMBALE MUHINDO Josué",
      matricule: "",
      status: "active",
      scores: [{ evaluation_id: FIRST, score: "7.0" }],
      total: null,
    },
  ],
};

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("teacher"),
    "GET /api/grading/": grading,
    [`GET /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: sheet,
    ...extra,
  };
}

describe("saisie des notes", () => {
  it("recalcule la note de la période et n'envoie que les cases changées", async () => {
    const requests = mockApi(
      routes({ [`PUT /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: sheet }),
    );
    const { user } = renderApp("/grades");

    // 8 + 9 sur 10 + 10, ramené sur 20 ; Josué : une case vide.
    await screen.findByText("17");
    expect(screen.getByText("incomplet")).toBeTruthy();
    const box = screen.getByLabelText("Interrogation 2 — KAMBALE MUHINDO Josué");
    await user.type(box, "6,5");
    expect(screen.getByText("13,5")).toBeTruthy();
    expect(screen.getByText("68 %")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(requests.some((r) => r.method === "PUT")).toBe(true));
    const put = requests.find((request) => request.method === "PUT")!;
    expect(put.body).toEqual({
      evaluations: sheet.evaluations,
      removed_evaluations: [],
      grades: [{ enrollment_id: JOSUE, evaluation_id: SECOND, score: "6.5" }],
    });
  });

  it("une note au-dessus du maximum bloque l'envoi", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/grades");

    const box = await screen.findByLabelText("Interrogation 2 — KAMBALE MUHINDO Josué");
    await user.type(box, "12");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    await screen.findByText(/Corrigez les cases en rouge/);
    expect(requests.some((request) => request.method === "PUT")).toBe(false);
  });
});
