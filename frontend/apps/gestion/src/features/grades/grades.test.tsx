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
      is_homeroom: false,
      courses: [
        { id: COURSE, name: "Électrotechnique", period_max: 20, has_exam: true, teaches: true },
      ],
    },
  ],
};

const sheet = {
  course: grading.classes[0]!.courses[0],
  class_group: "3e Électricité A",
  term: PERIOD,
  maximum: 20,
  entry: "detailed",
  status: "draft",
  reopened: false,
  due_on: null,
  submitted_at: null,
  submitted_by: "",
  validated_at: null,
  validated_by: "",
  returned: null,
  history: [],
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
      reason: "",
    });
  });

  it("une feuille envoyée demande un motif avant d'enregistrer", async () => {
    const sent = { ...sheet, status: "submitted", submitted_at: "2026-11-02T08:00:00Z" };
    const requests = mockApi(
      routes({
        [`GET /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: sent,
        [`PUT /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: sent,
      }),
    );
    const { user } = renderApp("/grades");

    await user.type(await screen.findByLabelText("Interrogation 2 — KAMBALE MUHINDO Josué"), "6");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    // Pas d'envoi sans motif ; avec le motif, il part avec les cases.
    await user.click(await screen.findByRole("button", { name: "Enregistrer" }));
    await screen.findByText(/Donnez un motif/);
    expect(requests.some((request) => request.method === "PUT")).toBe(false);
    await user.type(screen.getByRole("textbox", { name: /Motif/ }), "Erreur de copie");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(requests.some((r) => r.method === "PUT")).toBe(true));
    expect(requests.find((r) => r.method === "PUT")!.body).toMatchObject({
      reason: "Erreur de copie",
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

  it("sans devoirs : une seule colonne « Total » au maximum de la période", async () => {
    const totals = {
      ...sheet,
      entry: "totals",
      evaluations: [],
      students: sheet.students.map((row) => ({ ...row, scores: [], total: null })),
    };
    const requests = mockApi(
      routes({
        [`GET /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: totals,
        [`PUT /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: totals,
      }),
    );
    const { user } = renderApp("/grades");

    const box = await screen.findByLabelText("Total — KAMBALE MUHINDO Josué");
    expect(screen.queryByRole("button", { name: /Ajouter une évaluation/ })).toBeNull();
    await user.type(box, "15,5");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(requests.some((r) => r.method === "PUT")).toBe(true));
    const put = requests.find((request) => request.method === "PUT")!.body as {
      evaluations: { id: string; name: string; max_score: number }[];
      grades: { evaluation_id: string; score: string }[];
    };
    // Une évaluation « Total » à 20, créée côté appareil, et la note rattachée à elle.
    expect(put.evaluations).toHaveLength(1);
    expect(put.evaluations[0]).toMatchObject({ name: "Total", max_score: 20 });
    expect(put.grades).toEqual([
      { enrollment_id: JOSUE, evaluation_id: put.evaluations[0]!.id, score: "15.5" },
    ]);
  });

  it("envoie et signe la fiche seulement après confirmation", async () => {
    const complete = {
      ...sheet,
      students: [{ ...sheet.students[0]!, total: "17.0" }],
    };
    const requests = mockApi(
      routes({
        [`GET /api/courses/${COURSE}/terms/${PERIOD}/grades/`]: complete,
        [`POST /api/courses/${COURSE}/terms/${PERIOD}/grades/submit/`]: {
          ...complete,
          status: "submitted",
        },
      }),
    );
    const { user } = renderApp("/grades");

    await user.click(await screen.findByRole("button", { name: "Envoyer et signer" }));
    expect(requests.some((request) => request.method === "POST")).toBe(false);
    await screen.findByText(/Vous certifiez ces notes/);
    const buttons = screen.getAllByRole("button", { name: "Envoyer et signer" });
    await user.click(buttons.at(-1)!);
    await screen.findByText(/le directeur des études et le titulaire sont avertis/);
    expect(requests.filter((request) => request.method === "POST")).toHaveLength(1);
  });
});

describe("fiche de cotes", () => {
  const totals = {
    course: grading.classes[0]!.courses[0],
    class_group: "3e Électricité A",
    term: PERIOD,
    term_label: "1re période",
    maximum: 20,
    status: "submitted",
    reopened: false,
    due_on: null,
    submitted_at: "2026-11-04T08:12:00Z",
    submitted_by: "Kasereka Mumbere",
    validated_at: null,
    validated_by: "",
    returned: null,
    history: [],
    students: [
      { ...sheet.students[0]!, scores: undefined, total: "17.0" },
      { ...sheet.students[1]!, scores: undefined, total: "8.5" },
    ],
  };
  const url = `/grade-sheets/totals?course=${COURSE}&term=${PERIOD}`;
  const api = `/api/courses/${COURSE}/terms/${PERIOD}/grades`;

  it("le directeur des études lit les totaux et renvoie avec remarques", async () => {
    const requests = mockApi({
      ...routes({ "GET /api/me/": me("study_director") }),
      [`GET ${api}/totals/`]: totals,
      [`POST ${api}/reopen/`]: { ...totals, status: "draft", students: [] },
    });
    const { user } = renderApp(url);

    await screen.findByText(/Envoyée et signée par Kasereka Mumbere/);
    expect(screen.getByText("85 %")).toBeTruthy();
    expect(screen.getByText("1 élève")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Renvoyer avec remarques" }));
    await user.click(screen.getByRole("button", { name: "Renvoyer" }));
    await screen.findByText(/Écrivez vos remarques/);
    await user.type(screen.getByRole("textbox", { name: /Remarques/ }), "TP manquant");
    await user.click(screen.getByRole("button", { name: "Renvoyer" }));
    await screen.findByText(/Fiche renvoyée à l'enseignant/);
    expect(requests.find((request) => request.method === "POST")!.body).toEqual({
      reason: "TP manquant",
    });
  });

  it("le titulaire la lit sans pouvoir la valider", async () => {
    mockApi({ ...routes(), [`GET ${api}/totals/`]: totals });
    renderApp(url);

    await screen.findByText(/Envoyée et signée par Kasereka Mumbere/);
    expect(screen.queryByRole("button", { name: "Valider" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Renvoyer avec remarques" })).toBeNull();
  });
});
