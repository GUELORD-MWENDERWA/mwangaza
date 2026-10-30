import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const leaf = (
  n: number,
  kind: string,
  starts: string | null = null,
  ends: string | null = null,
) => ({
  id: id(n),
  kind,
  name: "",
  starts_on: starts,
  ends_on: ends,
});
const semester = (n: number, dates = false) => ({
  ...leaf(n, "semester", dates ? "2026-09-07" : null, dates ? "2026-12-23" : null),
  children: [
    leaf(n + 1, "period", dates ? "2026-09-07" : null, dates ? "2026-11-07" : null),
    leaf(n + 2, "period"),
    leaf(n + 3, "exam"),
  ],
});
const year = {
  id: id(1),
  name: "2026-2027",
  starts_on: "2026-09-01",
  ends_on: "2027-07-02",
  is_current: true,
  status: "open",
  terms: [semester(10, true), semester(20)],
};
const levels = [
  { id: id(31), name: "7e EB", report_title: "", cycle: "basic", order: 0, has_state_exam: false },
  { id: id(32), name: "3e", cycle: "secondary_technical", order: 1 },
];
const tracks = [{ id: id(41), name: "Électricité", code: "ELEC" }];
const teacher = { id: id(51), last_name: "Katembo", middle_name: "Siku", first_name: "Olivier" };
const group = (n: number, level: string, track: string | null, section: string, extra = {}) => ({
  id: id(n),
  academic_year: year.id,
  level,
  track,
  section,
  name: `${level === id(31) ? "7e EB" : "3e Électricité"} ${section}`,
  capacity: 45,
  student_count: 0,
  homeroom_teacher: null,
  ...extra,
});
const classes = [
  group(62, id(32), id(41), "A", { homeroom_teacher: teacher }),
  group(60, id(31), null, "A"),
  group(61, id(31), null, "B", { homeroom_teacher: teacher }),
];

function routes(extra: Routes = {}): Routes {
  return {
    "GET /api/school/": school,
    "GET /api/me/": me("head"),
    "GET /api/academic-years/": [year],
    "GET /api/levels/": levels,
    "GET /api/tracks/": tracks,
    "GET /api/class-groups/": classes,
    "GET /api/class-groups/homeroom-candidates/": [teacher],
    "GET /api/matricule-format/": {
      matricule_format: "ITIG-{AAAA}-{0000}",
      auto_matricule: true,
      example: "ITIG-2026-0001",
    },
    ...extra,
  };
}

const card = async (title: string | RegExp) =>
  within((await screen.findByRole("heading", { name: title })).closest("section")!);

describe("Organisation scolaire (C1-C3)", () => {
  it("année en cours et découpage aux noms traduits ; dates à compléter signalées", async () => {
    mockApi(routes());
    renderApp("/organisation");

    expect(
      ((await screen.findByLabelText("Année")) as HTMLSelectElement).selectedOptions[0]!.text,
    ).toBe("Année : 2026-2027 (en cours)");
    const terms = await card("Découpage");
    const rows = terms.getAllByRole("row").map((row) => row.textContent);
    expect(rows).toEqual([
      "PériodeDébutFin",
      "Semestre 107/09/202623/12/2026",
      "1re période07/09/202607/11/2026",
      "2e période——",
      "Examens du 1er semestre——",
      "Semestre 2——",
      "3e période——",
      "4e période——",
      "Examens du 2e semestre——",
    ]);
    expect(terms.getByText("Dates à compléter.")).toBeTruthy();
    expect((await card("Année 2026-2027")).getByText("En cours")).toBeTruthy();
  });

  it("modifier le découpage : un seul envoi ; refus sous la ligne", async () => {
    const all = routes({
      "PUT /api/academic-years/00000000-0000-7000-8000-000000000001/terms/": apiError(
        "invalid",
        400,
        { fields: { "terms.1.ends_on": [{ code: "outside_year", detail: "Outside." }] } },
      ),
    });
    const requests = mockApi(all);
    const { user } = renderApp("/organisation");

    const terms = await card("Découpage");
    await user.click(terms.getByRole("button", { name: "Modifier les dates" }));
    await user.type(terms.getByLabelText("Nom | 2e période"), "P2");
    await user.type(terms.getByLabelText("Fin | Semestre 2"), "2027-08-01");
    await user.click(terms.getAllByRole("button", { name: "Ajouter des examens" })[1]!);
    await user.click(terms.getByRole("button", { name: "Retirer Examens du 1er semestre" }));
    await user.click(terms.getByRole("button", { name: "Enregistrer le découpage" }));

    expect(await terms.findByText("Date en dehors de l'année scolaire.")).toBeTruthy();
    const body = requests.find((r) => r.method === "PUT")!.body as {
      terms: { name: string; ends_on: string | null; children: { id?: string; kind: string }[] }[];
    };
    expect(body.terms[0]!.children.map((child) => child.id)).toEqual([id(11), id(12)]);
    expect(body.terms[0]!.children[1]).toMatchObject({ name: "P2" });
    expect(body.terms[1]!.ends_on).toBe("2027-08-01");
    expect(body.terms[1]!.children.map((child) => [child.kind, child.id])).toEqual([
      ["period", id(21)],
      ["period", id(22)],
      ["exam", id(23)],
      ["exam", undefined],
    ]);
  });

  it("nouvelle année depuis un modèle, avec les classes de l'année en cours", async () => {
    const created = { ...year, id: id(2), name: "2027-2028", is_current: false, terms: [] };
    const all = routes({ "POST /api/academic-years/": created });
    const requests = mockApi(all);
    const { user } = renderApp("/organisation");

    await user.click(await screen.findByRole("button", { name: "Nouvelle année" }));
    const dialog = within(await screen.findByRole("dialog"));
    await user.type(dialog.getByLabelText(/Début/), "2027-09-06");
    await user.type(dialog.getByLabelText(/Fin/), "2027-07-01");
    await user.click(dialog.getByRole("button", { name: "Créer l'année" }));
    expect(await dialog.findByText("La fin doit venir après le début.")).toBeTruthy();

    await user.clear(dialog.getByLabelText(/Fin/));
    await user.type(dialog.getByLabelText(/Fin/), "2028-07-01");
    await user.selectOptions(dialog.getByLabelText("Modèle de découpage"), "trimesters");
    // Barèmes repris avec les classes (droit `finance.configure_fees` du directeur) : décoché.
    await user.click(dialog.getByRole("checkbox", { name: /Reprendre aussi les barèmes/ }));
    all["GET /api/academic-years/"] = [year, created];
    await user.click(dialog.getByRole("button", { name: "Créer l'année" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({
      name: "",
      starts_on: "2027-09-06",
      ends_on: "2028-07-01",
      template: "trimesters",
      copy_classes_from: year.id,
      copy_fees: false,
    });
    expect(await screen.findByRole("heading", { name: "Année 2027-2028" })).toBeTruthy();
  });

  it("supprimer une année : confirmation, refus du serveur traduit", async () => {
    const other = { ...year, id: id(2), name: "2025-2026", is_current: false };
    mockApi(
      routes({
        "GET /api/academic-years/": [year, other],
        "DELETE /api/academic-years/00000000-0000-7000-8000-000000000002/": apiError(
          "year_in_use",
          409,
        ),
      }),
    );
    const { user } = renderApp("/organisation");

    await user.selectOptions(await screen.findByLabelText("Année"), other.id);
    const card2025 = await card("Année 2025-2026");
    expect(card2025.queryByText("En cours")).toBeNull();
    await user.click(card2025.getByRole("button", { name: "Supprimer l'année" }));
    const dialog = within(await screen.findByRole("dialog"));
    await user.click(dialog.getByRole("button", { name: "Supprimer l'année" }));

    expect(
      await dialog.findByText("Cette année a des classes : supprimez-les d'abord."),
    ).toBeTruthy();
  });

  it("niveaux : ajout, ordre, suppression refusée ; code d'option en majuscules", async () => {
    const all = routes({
      "POST /api/levels/": { id: id(33), name: "8e EB", cycle: "basic", order: 2 },
      "POST /api/levels/reorder/": [...levels].reverse(),
      "POST /api/tracks/": { id: id(42), name: "Électronique", code: "ELO" },
      "DELETE /api/levels/00000000-0000-7000-8000-000000000031/": apiError("level_in_use", 409),
    });
    const requests = mockApi(all);
    const { user } = renderApp("/organisation");

    await user.click(await screen.findByRole("tab", { name: "Niveaux et options" }));
    const levelsCard = await card("Niveaux");
    await user.type(levelsCard.getByLabelText(/^Niveau/), "8e EB");
    await user.selectOptions(levelsCard.getByLabelText("Cycle"), "basic");
    await user.click(levelsCard.getByRole("button", { name: "Ajouter un niveau" }));
    await user.click(levelsCard.getByRole("button", { name: "Descendre 7e EB" }));
    await user.click(levelsCard.getByRole("button", { name: "Supprimer 7e EB" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Supprimer" }),
    );
    expect(await screen.findByText("Ce niveau est utilisé par des classes.")).toBeTruthy();
    await user.keyboard("{Escape}");

    const tracksCard = await card("Options");
    await user.type(tracksCard.getByLabelText(/^Option/), "Électronique");
    await user.type(tracksCard.getByLabelText(/^Code/), "é!");
    await user.click(tracksCard.getByRole("button", { name: "Ajouter une option" }));
    expect(await tracksCard.findByText("1 à 10 lettres majuscules ou chiffres.")).toBeTruthy();
    await user.clear(tracksCard.getByLabelText(/^Code/));
    await user.type(tracksCard.getByLabelText(/^Code/), "elo");
    await user.click(tracksCard.getByRole("button", { name: "Ajouter une option" }));

    await waitFor(() =>
      expect(requests.some((r) => r.path === "/api/tracks/" && r.method === "POST")).toBe(true),
    );
    const sent = (path: string) =>
      requests.find((r) => r.method === "POST" && r.path === path)?.body;
    expect(sent("/api/levels/")).toEqual({
      name: "8e EB",
      report_title: "",
      cycle: "basic",
      has_state_exam: false,
    });
    expect(sent("/api/levels/reorder/")).toEqual({ ids: [id(32), id(31)] });
    expect(sent("/api/tracks/")).toEqual({ name: "Électronique", code: "ELO" });
  });

  it("classes groupées par option et niveau ; titulaires", async () => {
    mockApi(routes());
    const { user } = renderApp("/organisation");

    await user.click(await screen.findByRole("tab", { name: "Classes" }));
    const classesCard = await card("Classes 2026-2027");
    expect(classesCard.getByText("3 classes")).toBeTruthy();
    const rows = classesCard
      .getAllByRole("row")
      .slice(1)
      .map((row) => row.textContent);
    expect(rows).toEqual([
      "Éducation de base7e EBAB0 / 901 sans titulaire",
      "Électricité3eA0 / 45Olivier Siku Katembo",
    ]);
  });

  it("classe : création, titulaire, suppression refusée si elle a des élèves", async () => {
    const all = routes({
      "POST /api/class-groups/": group(63, id(32), id(41), "B"),
      "PATCH /api/class-groups/00000000-0000-7000-8000-000000000060/": group(60, id(31), null, "A"),
      "DELETE /api/class-groups/00000000-0000-7000-8000-000000000060/": apiError(
        "class_in_use",
        409,
      ),
    });
    const requests = mockApi(all);
    const { user } = renderApp("/organisation");

    await user.click(await screen.findByRole("tab", { name: "Classes" }));
    const classesCard = await card("Classes 2026-2027");
    await user.click(classesCard.getByRole("button", { name: "Ajouter une classe" }));
    let dialog = within(await screen.findByRole("dialog"));
    await user.selectOptions(dialog.getByLabelText(/Niveau/), id(32));
    await user.selectOptions(dialog.getByLabelText("Option"), id(41));
    await user.type(dialog.getByLabelText("Section"), "b");
    await user.type(dialog.getByLabelText("Capacité"), "0");
    await user.click(dialog.getByRole("button", { name: "Ajouter" }));
    expect(await dialog.findByText("Un nombre entre 1 et 1000.")).toBeTruthy();
    await user.clear(dialog.getByLabelText("Capacité"));
    await user.type(dialog.getByLabelText("Capacité"), "40");
    await user.click(dialog.getByRole("button", { name: "Ajouter" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({
      level: id(32),
      track: id(41),
      section: "b",
      capacity: 40,
      homeroom_teacher: null,
      co_homeroom_teacher: null,
      academic_year: year.id,
    });

    await user.click(classesCard.getByRole("button", { name: "Ouvrir la classe 7e EB A" }));
    dialog = within(await screen.findByRole("dialog"));
    await user.selectOptions(dialog.getByLabelText("Titulaire"), teacher.id);
    await user.click(dialog.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(requests.some((r) => r.method === "PATCH")).toBe(true));
    expect(requests.find((r) => r.method === "PATCH")?.body).toMatchObject({
      homeroom_teacher: teacher.id,
    });

    await user.click(classesCard.getByRole("button", { name: "Ouvrir la classe 7e EB A" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "Supprimer la classe",
      }),
    );
    const confirm = within(await screen.findByRole("dialog"));
    await user.click(confirm.getByRole("button", { name: "Supprimer" }));
    expect(
      await confirm.findByText("Cette classe a des élèves : elle ne peut pas être supprimée."),
    ).toBeTruthy();
  });

  it("matricule : l'école choisit de ne plus en attribuer, le format ne se règle plus", async () => {
    const requests = mockApi(
      routes({
        "PATCH /api/matricule-format/": {
          matricule_format: "ITIG-{AAAA}-{0000}",
          auto_matricule: false,
          example: "ITIG-2026-0001",
        },
      }),
    );
    const { user } = renderApp("/organisation");

    await user.click(await screen.findByRole("tab", { name: "Matricule" }));
    const matricule = await card("Format du matricule");
    await user.click(
      matricule.getByRole("switch", { name: /Attribuer un matricule automatiquement/ }),
    );

    expect(await matricule.findByText(/Aucun matricule n'est créé/)).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({ auto_matricule: false });
    expect((matricule.getByLabelText("Modèle") as HTMLInputElement).disabled).toBe(true);
    expect(matricule.queryByText("ITIG-2026-0001")).toBeNull();
  });

  it("matricule : aperçu calculé par le serveur pendant la saisie, refus sous le champ", async () => {
    const all = routes({
      "POST /api/matricule-format/preview/": (request: Request) =>
        request.json().then((body: { matricule_format: string }) =>
          body.matricule_format.includes("{A")
            ? { matricule_format: body.matricule_format, example: "LV/26/001" }
            : apiError("invalid", 400, {
                fields: {
                  matricule_format: [{ code: "matricule_year_missing", detail: "Year." }],
                },
              }),
        ),
      "PATCH /api/matricule-format/": {
        matricule_format: "LV/{AA}/{000}",
        auto_matricule: true,
        example: "LV/26/001",
      },
    });
    const requests = mockApi(all);
    const { user } = renderApp("/organisation");

    await user.click(await screen.findByRole("tab", { name: "Matricule" }));
    const matricule = await card("Format du matricule");
    expect(matricule.getByText("ITIG-2026-0001")).toBeTruthy();
    const input = matricule.getByLabelText("Modèle");
    await user.clear(input);
    await user.type(input, "LV/{{000}");
    expect(await matricule.findByText(/Ajoutez l'année/, {}, { timeout: 2000 })).toBeTruthy();
    await user.clear(input);
    await user.type(input, "LV/{{AA}/{{000}");
    expect(await matricule.findByText("LV/26/001", {}, { timeout: 2000 })).toBeTruthy();
    await user.click(matricule.getByRole("button", { name: "Enregistrer" }));

    expect(await matricule.findByText("Format enregistré.")).toBeTruthy();
    expect(requests.find((r) => r.method === "PATCH")?.body).toEqual({
      matricule_format: "LV/{AA}/{000}",
    });
  });

  it("aucune année : proposée depuis un modèle", async () => {
    mockApi(routes({ "GET /api/academic-years/": [] }));
    renderApp("/organisation");

    expect(await screen.findByText(/Aucune année scolaire/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nouvelle année" })).toBeTruthy();
  });

  it("directeur des études : oui ; caissier : page refusée", async () => {
    mockApi(routes({ "GET /api/me/": me("study_director") }));
    renderApp("/organisation");
    expect(await screen.findByRole("heading", { name: "Organisation scolaire" })).toBeTruthy();
  });

  it("caissier : page refusée, rien n'est lu", async () => {
    const requests = mockApi(routes({ "GET /api/me/": me("cashier") }));
    renderApp("/organisation");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
    expect(requests.some((r) => r.path === "/api/academic-years/")).toBe(false);
  });
});
