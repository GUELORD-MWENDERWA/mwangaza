import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { json, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const year = { id: id(1), name: "2026-2027", is_current: true, terms: [] };
const group = {
  id: id(60),
  academic_year: year.id,
  level: id(31),
  track: id(41),
  section: "A",
  name: "4e Mécanique automobile A",
  capacity: 40,
  student_count: 12,
  homeroom_teacher: null,
};
const IMPORT = id(500);
const analysed = {
  id: IMPORT,
  academic_year: year.id,
  file_name: "liste.xlsx",
  sheet_name: "Feuil1",
  headers: ["NOM", "POSTNOM", "PRENOM", "SEXE", "DATE NAISS.", "CLASSE"],
  mapping: {
    last_name: 0,
    middle_name: 1,
    first_name: 2,
    sex: 3,
    birth_date: 4,
    birth_place: null,
    class_name: 5,
    matricule: null,
    guardian_name: null,
    guardian_phone: null,
  },
  class_mapping: {},
  status: "analysed",
  counts: { rows: 4, ready: 2, warning: 0, error: 2 },
  missing_fields: [],
  classes: [
    { label: "3E ELEC A", class_group: id(61), chosen: false, rows: 3 },
    { label: "4E MEC AUTO A", class_group: null, chosen: false, rows: 1 },
  ],
  importable_count: 2,
  created_count: 0,
  created_at: "2026-09-27T08:00:00Z",
  finished_at: null,
  cancelled_count: 0,
  cancelled_at: null,
  cancelled_by_name: null,
  cancel_reason: "",
};
const done = {
  ...analysed,
  status: "done",
  counts: { rows: 4, ready: 4, warning: 0, error: 0 },
  created_count: 4,
  finished_at: "2026-09-27T08:05:00Z",
};
const values = (last: string, date: string, klass: string) => ({
  last_name: last,
  middle_name: "",
  first_name: "Josué",
  sex: "M",
  birth_date: date,
  birth_place: "",
  class_name: klass,
  matricule: "",
  guardian_name: "",
  guardian_phone: "",
});
const problems = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      line: 4,
      status: "error",
      issues: [{ code: "invalid_date" }],
      values: values("PALUKU", "31/02/2008", "3E ELEC A"),
    },
    {
      line: 5,
      status: "error",
      issues: [{ code: "unknown_class" }],
      values: values("KAVIRA", "05/06/2011", "4E MEC AUTO A"),
    },
  ],
};

function routes(role: Parameters<typeof me>[0]): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me(role),
    "GET /api/academic-years/": [year],
    "GET /api/tracks/": [],
    "GET /api/class-groups/": [group],
    "GET /api/students/": { count: 0, next: null, previous: null, results: [] },
    "GET /api/student-imports/": { count: 0, next: null, previous: null, results: [] },
  };
}

describe("importer des élèves (D1)", () => {
  it("n'offre l'import qu'avec le droit students.import", async () => {
    mockApi(routes("study_director"));
    renderApp("/students");
    expect(await screen.findByRole("link", { name: /Nouvel élève/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Importer Excel/ })).toBeNull();
  });

  it("vérifie le fichier, associe une classe à la main, importe et suit la tâche", async () => {
    const all: Routes = {
      ...routes("head"),
      "POST /api/student-imports/": json(analysed, 201),
      [`GET /api/student-imports/${IMPORT}/`]: analysed,
      [`GET /api/student-imports/${IMPORT}/lines/`]: problems,
      [`PATCH /api/student-imports/${IMPORT}/`]: {
        ...analysed,
        class_mapping: { "4E MEC AUTO A": group.id },
        counts: { rows: 4, ready: 3, warning: 0, error: 1 },
        classes: [
          analysed.classes[0],
          { label: "4E MEC AUTO A", class_group: group.id, chosen: true, rows: 1 },
        ],
        importable_count: 3,
      },
      [`POST /api/student-imports/${IMPORT}/confirm/`]: () => {
        all[`GET /api/student-imports/${IMPORT}/`] = {
          ...analysed,
          status: "done",
          counts: { rows: 4, ready: 3, warning: 0, error: 1 },
          created_count: 3,
        };
        return json({ ...analysed, status: "importing", importable_count: 3 }, 202);
      },
    };
    const requests = mockApi(all);
    const { user } = renderApp("/students/import");

    // `FormData` et fichier de Node : le `Request` de Node ne lit pas ceux de jsdom.
    const form = await new Response(new URLSearchParams("a=b")).formData();
    vi.stubGlobal("FormData", form.constructor);
    const blob = await new Response("xlsx").blob();
    const file = Object.assign(blob, { name: "liste.xlsx" }) as unknown as File;
    await user.upload(await screen.findByLabelText("Fichier Excel (.xlsx) ou CSV"), file);
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));

    expect(await screen.findByText("Classe inconnue")).toBeTruthy();
    expect(screen.getByText("Date invalide")).toBeTruthy();
    await user.selectOptions(screen.getByLabelText(/« 4E MEC AUTO A »/), group.id);
    const patch = requests.find((request) => request.method === "PATCH");
    expect(patch?.body).toEqual({ class_mapping: { "4E MEC AUTO A": group.id } });

    await user.click(await screen.findByRole("button", { name: "Importer 3 élèves" }));
    const done = await screen.findByText("3 élèves importés et inscrits.", {}, { timeout: 4000 });
    expect(done).toBeTruthy();
    expect(within(done.closest("section")!).getByText(/1 ligne en erreur/)).toBeTruthy();
  });

  it("retrouve un import fini et l'annule avec un motif, en nommant les élèves gardés", async () => {
    const cancelled = {
      ...done,
      status: "cancelled",
      cancelled_count: 3,
      cancelled_at: "2026-09-28T09:00:00Z",
      cancelled_by_name: "Masika Furaha",
      cancel_reason: "Mauvaise année",
    };
    const all: Routes = {
      ...routes("head"),
      "GET /api/student-imports/": {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: IMPORT,
            file_name: "liste.xlsx",
            academic_year_name: "2026-2027",
            status: "done",
            created_count: 4,
            cancelled_count: 0,
            finished_at: done.finished_at,
            created_by_name: "Masika Furaha",
          },
        ],
      },
      [`GET /api/student-imports/${IMPORT}/`]: done,
      [`GET /api/student-imports/${IMPORT}/cancellation/`]: {
        removable_count: 3,
        kept_count: 1,
        kept: [
          {
            id: id(700),
            matricule: "",
            last_name: "Paluku",
            middle_name: "Sivihwa",
            first_name: "Daniel",
            reasons: ["payment"],
          },
        ],
      },
      [`POST /api/student-imports/${IMPORT}/cancel/`]: () => {
        all[`GET /api/student-imports/${IMPORT}/`] = cancelled;
        return json(cancelled);
      },
    };
    const requests = mockApi(all);
    const { user } = renderApp("/students/import");

    await user.click(await screen.findByRole("link", { name: "liste.xlsx" }));
    await user.click(await screen.findByRole("button", { name: "Annuler cet import" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/3 élèves seront retirés pour de bon/)).toBeTruthy();
    expect(within(dialog).getByRole("link", { name: "PALUKU SIVIHWA Daniel" })).toBeTruthy();
    expect(within(dialog).getByText(/— paiement/)).toBeTruthy();

    // Sans motif, rien n'est envoyé.
    await user.click(within(dialog).getByRole("button", { name: "Annuler l'import" }));
    expect(requests.some((request) => request.path.endsWith("/cancel/"))).toBe(false);
    await user.type(within(dialog).getByLabelText(/Motif/), "Mauvaise année");
    await user.click(within(dialog).getByRole("button", { name: "Annuler l'import" }));

    expect(await screen.findByText(/par Masika Furaha : 3 élèves retirés\./)).toBeTruthy();
    expect(screen.getByText("Motif : Mauvaise année")).toBeTruthy();
    const sent = requests.find((request) => request.path.endsWith("/cancel/"));
    expect(sent?.body).toEqual({ reason: "Mauvaise année" });
    expect(screen.queryByRole("button", { name: "Annuler cet import" })).toBeNull();
  });
});
