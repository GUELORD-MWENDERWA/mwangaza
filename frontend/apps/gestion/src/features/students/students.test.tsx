import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { apiError, json, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const id = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const UUID_V7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const year = { id: id(1), name: "2026-2027", is_current: true, terms: [] };
const group = {
  id: id(60),
  academic_year: year.id,
  level: id(31),
  track: id(41),
  section: "A",
  name: "3e Électricité A",
  capacity: 45,
  student_count: 42,
  homeroom_teacher: null,
};
const enrollment = (status = "active") => ({
  id: id(80),
  student: id(100),
  academic_year: year.id,
  academic_year_name: "2026-2027",
  class_group: group.id,
  class_group_name: group.name,
  status,
  enrolled_on: "2026-09-07",
  left_on: null,
});
const guardian = {
  id: id(300),
  full_name: "Kahindo Sarah",
  relationship: "mother",
  phone: "+243972145508",
  email: "",
  is_primary: true,
  is_emergency_contact: false,
};
const row = (n: number, names: [string, string, string], status = "active") => ({
  id: id(n),
  matricule: `ITIG-2026-0${n}`,
  last_name: names[0],
  middle_name: names[1],
  first_name: names[2],
  sex: "M",
  birth_date: "2011-03-12",
  family: id(200),
  family_code: "K7M2P9QX",
  enrollment: enrollment(status),
  primary_guardian: guardian,
});
const family = {
  id: id(200),
  code: "K7M2P9QX",
  guardians: [guardian],
  student_count: 1,
  activated_at: null,
  students: [
    {
      id: id(101),
      last_name: "Kambale",
      middle_name: "Muhindo",
      first_name: "Josué",
      class_group_name: group.name,
    },
  ],
};
const detail = (studentId: string) => ({
  ...row(100, ["Bisimwa", "Mugisho", "Arsène"]),
  id: studentId,
  matricule: "ITIG-2026-0801",
  family: { ...family, students: undefined },
  enrollments: [enrollment()],
});

function routes(role: Parameters<typeof me>[0], extra: Routes = {}): Routes {
  const all: Routes = {
    "GET /api/school/": school,
    "GET /api/me/": me(role),
    "GET /api/academic-years/": [year],
    "GET /api/tracks/": [{ id: id(41), name: "Électricité", code: "ELEC" }],
    "GET /api/class-groups/": [group],
    "GET /api/students/": {
      count: 2,
      next: null,
      previous: null,
      results: [
        row(412, ["Kambale", "Muhindo", "Josué"]),
        row(388, ["Kahindo", "Masika", "Grâce"], "transferred"),
      ],
    },
    "GET /api/families/": { count: 1, next: null, previous: null, results: [family] },
    // L'élève est relu après l'inscription, à l'identifiant donné par l'appareil.
    "POST /api/students/": async (request) => {
      const body = (await request.json()) as { id: string };
      all[`GET /api/students/${body.id}/`] = detail(body.id);
      return json(detail(body.id), 201);
    },
    "POST /api/enrollments/": json(enrollment(), 201),
    ...extra,
  };
  return all;
}

const posts = (requests: ReturnType<typeof mockApi>, path: string) =>
  requests.filter((request) => request.method === "POST" && request.path === path);

async function fillIdentity(user: ReturnType<typeof renderApp>["user"]) {
  await user.type(await screen.findByLabelText(/^Nom/), "Bisimwa");
  await user.type(screen.getByLabelText(/^Post-nom/), "Mugisho");
  await user.type(screen.getByLabelText(/^Prénom/), "Arsène");
  await user.click(screen.getByRole("radio", { name: "Masculin" }));
  fireEvent.change(screen.getByLabelText(/^Date de naissance/), {
    target: { value: "2011-03-12" },
  });
  await user.selectOptions(await screen.findByLabelText(/^Classe/), "3e Électricité A");
}

describe("Élèves (D2-D4)", () => {
  it("liste : recherche et filtres envoyés au serveur, tuteur principal, élève parti signalé ; sans students.edit, pas d'inscription", async () => {
    const requests = mockApi(routes("cashier"));
    const { user } = renderApp("/students");

    const table = within(await screen.findByRole("table"));
    expect(table.getByText("KAMBALE MUHINDO Josué")).toBeTruthy();
    expect(table.getAllByText("Kahindo Sarah · +243 97 214 55 08")).toHaveLength(2);
    expect(table.getByText("Transféré")).toBeTruthy();
    expect(await screen.findByText("42 élèves inscrits en 2026-2027 · 1 classe")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Nouvel élève/ })).toBeNull();
    const lists = () => requests.filter((request) => request.path === "/api/students/");
    expect(lists()[0]!.query).toEqual({ status: "active" });

    await user.type(screen.getByRole("searchbox"), "élie kam");
    await user.selectOptions(screen.getByLabelText("Classe"), "3e Électricité A");
    await user.selectOptions(screen.getByLabelText("Statut"), "Statut : tous");
    await waitFor(() =>
      expect(lists().at(-1)!.query).toEqual({ search: "élie kam", class_group: group.id }),
    );

    await user.click(screen.getByRole("button", { name: "Effacer les filtres" }));
    await waitFor(() => expect(lists().at(-1)!.query).toEqual({ status: "active" }));
  });

  it("inscription avec une nouvelle famille : champs exigés, élève puis inscription au même identifiant, matricule et code famille affichés", async () => {
    const requests = mockApi(routes("study_director"));
    const { user } = renderApp("/students/new");

    await user.click(await screen.findByRole("button", { name: "Enregistrer et inscrire" }));
    expect(await screen.findByText("Saisissez le post-nom.")).toBeTruthy();
    expect(screen.getByText("Choisissez la classe.")).toBeTruthy();
    expect(screen.getByText("Choisissez une famille, ou créez une nouvelle famille.")).toBeTruthy();

    await fillIdentity(user);
    expect(screen.getByText("42 / 45 places occupées")).toBeTruthy();
    await user.click(screen.getByRole("radio", { name: "Nouvelle famille" }));
    await user.type(screen.getByLabelText(/^Nom complet/), "Bisimwa Aline");
    await user.selectOptions(screen.getByLabelText(/^Lien/), "mère");
    await user.click(screen.getByRole("button", { name: "Enregistrer et inscrire" }));
    expect(await screen.findByText("Saisissez le téléphone du tuteur principal.")).toBeTruthy();
    await user.type(screen.getByLabelText(/^Téléphone/), "0996148320");
    await user.click(screen.getByRole("button", { name: "Enregistrer et inscrire" }));

    expect(
      await screen.findByText(
        "BISIMWA MUGISHO Arsène est inscrit en 3e Électricité A : matricule ITIG-2026-0801, code famille K7M2P9QX.",
      ),
    ).toBeTruthy();
    const [student] = posts(requests, "/api/students/");
    const [enrolled] = posts(requests, "/api/enrollments/");
    expect(student!.body).toMatchObject({
      last_name: "Bisimwa",
      middle_name: "Mugisho",
      sex: "M",
      birth_date: "2011-03-12",
      allow_duplicate: false,
      guardians: [
        {
          full_name: "Bisimwa Aline",
          relationship: "mother",
          phone: "0996148320",
          is_primary: true,
        },
      ],
    });
    const studentId = (student!.body as { id: string }).id;
    expect(studentId).toMatch(UUID_V7);
    expect(enrolled!.body).toMatchObject({ student: studentId, class_group: group.id });
    expect((enrolled!.body as { id: string }).id).toMatch(UUID_V7);
  });

  it("famille existante et doublon possible : avertissement, puis même envoi confirmé", async () => {
    let first = true;
    const all = routes("head");
    const create = all["POST /api/students/"] as (request: Request) => Promise<Response>;
    all["POST /api/students/"] = async (request) => {
      if (!first) return create(request);
      first = false;
      return apiError("possible_duplicate", 409);
    };
    const requests = mockApi(all);
    const { user } = renderApp("/students/new");

    await fillIdentity(user);
    await user.type(screen.getByLabelText("Rechercher par téléphone ou nom du tuteur"), "0972");
    expect(
      await screen.findByText("1 enfant : KAMBALE MUHINDO Josué, 3e Électricité A"),
    ).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Choisir" }));
    expect(screen.getByText("Sélectionnée")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Enregistrer et inscrire" }));

    await user.click(await screen.findByRole("button", { name: "Inscrire quand même" }));
    await screen.findByText(/est inscrit en 3e Électricité A/);
    const [refused, confirmed] = posts(requests, "/api/students/");
    expect(refused!.body).toMatchObject({ family: family.id, allow_duplicate: false });
    expect(confirmed!.body).toEqual({ ...(refused!.body as object), allow_duplicate: true });
    expect(confirmed!.body).not.toHaveProperty("guardians");
    expect(posts(requests, "/api/enrollments/")).toHaveLength(1);
  });

  it("inscrire demande students.edit : page refusée au caissier", async () => {
    mockApi(routes("cashier"));
    renderApp("/students/new");

    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
  });
});
