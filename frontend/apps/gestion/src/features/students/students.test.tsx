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
  birth_place: "Goma",
  nationality: "Congolaise",
  origin_province: "Nord-Kivu",
  origin_territory: "",
  address: { commune: "Goma", quartier: "Himbi", avenue: "", number: "" },
  photo: null,
  photo_consent: false,
  previous_school: "",
  family: { ...family, students: undefined },
  enrollments: [enrollment()],
  created_at: "2026-09-07T08:55:00Z",
});
const STUDENT = id(100);
const history = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: id(901),
      created_at: "2026-09-20T09:15:00Z",
      action: "students.student_updated",
      domain: "students",
      actor: { id: id(5), last_name: "Masika", middle_name: "", first_name: "Furaha" },
      by_support: false,
      entity_type: "students.student",
      entity_id: STUDENT,
      entity_label: "BISIMWA MUGISHO Arsène",
      role_code: null,
      before: { first_name: "Arsen" },
      after: { first_name: "Arsène" },
    },
    {
      id: id(900),
      created_at: "2026-09-07T08:55:00Z",
      action: "students.enrolled",
      domain: "students",
      actor: { id: id(5), last_name: "Masika", middle_name: "", first_name: "Furaha" },
      by_support: false,
      entity_type: "students.enrollment",
      entity_id: id(80),
      entity_label: "",
      role_code: null,
      before: null,
      after: { school_year: "2026-2027", class: group.name, status: "active" },
    },
  ],
};
// Fiche de l'élève `STUDENT` : sa famille (avec un frère) et son historique.
const card: Routes = {
  [`GET /api/students/${STUDENT}/`]: detail(STUDENT),
  [`GET /api/students/${STUDENT}/history/`]: history,
  [`GET /api/families/${family.id}/`]: {
    ...family,
    student_count: 2,
    students: [
      { ...family.students[0], matricule: "ITIG-2025-0287" },
      { ...family.students[0], id: STUDENT, last_name: "Bisimwa", matricule: "ITIG-2026-0801" },
    ],
  },
};

const charge = (n: number, label: string, due_on: string, extra = {}) => {
  const row = {
    id: id(700 + n),
    enrollment: id(80),
    fee_type: id(500),
    fee_type_name: "Minerval",
    fee_category: "tuition",
    label,
    amount_minor: 12000,
    currency: "USD",
    due_on,
    source: "rule",
    status: "active",
    discount_minor: 0,
    paid_minor: 0,
    state: "upcoming",
    ...extra,
  };
  return { ...row, remaining_minor: row.amount_minor - row.discount_minor };
};
const charges = [
  charge(1, "1re tranche", "2026-10-15"),
  charge(2, "2e tranche", "2027-01-15"),
  charge(3, "3e tranche", "2027-04-15"),
  charge(4, "Fonctionnement", "2026-10-15", {
    fee_type: id(501),
    fee_type_name: "Fonctionnement",
    fee_category: "operating",
    amount_minor: 2500,
  }),
];

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
    "GET /api/discounts/": [],
    "GET /api/student-charges/balance/": {
      situation: "up_to_date",
      next_due_on: "2026-10-15",
      currencies: [
        {
          currency: "USD",
          total_minor: 38500,
          paid_minor: 0,
          remaining_minor: 38500,
          overdue_minor: 0,
          next_due_minor: 14500,
        },
      ],
    },
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
      return apiError("possible_duplicate", 409, {
        body: { duplicates: [{ ...row(412, ["Kambale", "Muhindo", "Josué"]) }] },
      });
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

    const existing = await screen.findByRole("link", {
      name: "Ouvrir la fiche de KAMBALE MUHINDO Josué (ITIG-2026-0412)",
    });
    expect(existing.getAttribute("href")).toBe(`/students/${id(412)}`);
    await user.click(screen.getByRole("button", { name: "Inscrire quand même" }));
    await screen.findByText(/est inscrit en 3e Électricité A/);
    const [refused, confirmed] = posts(requests, "/api/students/");
    expect(refused!.body).toMatchObject({ family: family.id, allow_duplicate: false });
    expect(confirmed!.body).toEqual({ ...(refused!.body as object), allow_duplicate: true });
    expect(confirmed!.body).not.toHaveProperty("guardians");
    expect(posts(requests, "/api/enrollments/")).toHaveLength(1);
  });

  it("inscrire et modifier demandent students.edit : pages refusées au caissier", async () => {
    mockApi(routes("cashier", card));
    const { router } = renderApp("/students/new");
    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();

    await router.navigate(`/students/${STUDENT}/edit`);
    expect(await screen.findByText("Vous n'avez pas accès à cette page")).toBeTruthy();
    expect(screen.queryByLabelText(/^Nom/)).toBeNull();
  });

  it("fiche en lecture seule sans students.edit : identité, famille avec frère, historique et parcours", async () => {
    mockApi(routes("cashier", card));
    const { user } = renderApp(`/students/${STUDENT}`);

    expect(await screen.findByRole("heading", { name: "BISIMWA MUGISHO Arsène" })).toBeTruthy();
    expect(screen.getByText("Consentement du parent : non")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Modifier/ })).toBeNull();
    expect(screen.queryByText("Ajouter une photo")).toBeNull();

    await user.click(screen.getByRole("tab", { name: "Famille" }));
    expect(await screen.findByText("KAMBALE MUHINDO Josué")).toBeTruthy();
    expect(screen.getByText("Tuteur principal")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Lier à une autre famille" })).toBeNull();

    await user.click(screen.getByRole("tab", { name: "Historique" }));
    expect(await screen.findByText("Élève modifié")).toBeTruthy();
    expect(screen.getByText("Arsen")).toBeTruthy();
    expect(screen.getByText(/Élève inscrit/)).toBeTruthy();
    await user.click(screen.getByRole("radio", { name: "Scolarité" }));
    expect(screen.queryByText("Élève modifié")).toBeNull();
    expect(within(screen.getByRole("table")).getByText("2026-2027")).toBeTruthy();
  });

  it("départ depuis la fiche : motif et date envoyés sur l'inscription de l'année", async () => {
    const requests = mockApi(
      routes("head", { ...card, [`PATCH /api/enrollments/${id(80)}/`]: enrollment("transferred") }),
    );
    const { user } = renderApp(`/students/${STUDENT}`);

    await user.click(await screen.findByRole("button", { name: "Enregistrer un départ" }));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText(/^Motif/), "Transféré");
    fireEvent.change(within(dialog).getByLabelText(/^Date du départ/), {
      target: { value: "2026-11-03" },
    });
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer un départ" }));

    await waitFor(() =>
      expect(requests.find((request) => request.method === "PATCH")?.body).toEqual({
        status: "transferred",
        left_on: "2026-11-03",
      }),
    );
  });

  it("échéancier particulier : sans la tranche déjà payée en partie, proposition mensuelle au total exact, rien d'envoyé si la somme ou le motif manque", async () => {
    const paid = [
      charge(1, "1re tranche", "2026-10-15", { paid_minor: 5000 }),
      ...charges.slice(1),
    ];
    const requests = mockApi(
      routes("head", {
        ...card,
        "GET /api/student-charges/": paid,
        "POST /api/student-charges/reschedule/": charges,
      }),
    );
    const { user } = renderApp(`/students/${STUDENT}/finances`);
    await user.click(await screen.findByRole("link", { name: "Échéancier particulier" }));

    fireEvent.change(await screen.findByLabelText("Nombre de versements"), {
      target: { value: "6" },
    });
    fireEvent.change(screen.getByLabelText("Premier versement"), {
      target: { value: "2026-11-15" },
    });
    screen.getByText("✓ égal au reste à réorganiser");
    const last = screen.getByLabelText<HTMLInputElement>("Montant du versement 6");
    expect(last.value).toBe("40,00");
    await user.clear(last);
    await user.type(last, "39,99");
    await user.click(screen.getByRole("button", { name: "Enregistrer l'échéancier" }));
    screen.getByText("La somme des versements doit égaler le reste à réorganiser.");
    await user.clear(last);
    await user.type(last, "40");
    await user.click(screen.getByRole("button", { name: "Enregistrer l'échéancier" }));
    await screen.findByText("Ce champ est obligatoire.");
    expect(posts(requests, "/api/student-charges/reschedule/")).toHaveLength(0);

    await user.type(screen.getByLabelText(/^Motif/), "Arrangement avec le père");
    await user.click(screen.getByLabelText(/Engagement signé/));
    await user.click(screen.getByRole("button", { name: "Enregistrer l'échéancier" }));
    await waitFor(() =>
      expect(posts(requests, "/api/student-charges/reschedule/")).toHaveLength(1),
    );
    const [sent] = posts(requests, "/api/student-charges/reschedule/");
    expect(sent!.body).toEqual({
      enrollment: id(80),
      fee_type: id(500),
      reason: "Arrangement avec le père",
      parent_signed: true,
      installments: ["11-15", "12-15", "01-15", "02-15", "03-15", "04-15"].map((day, index) => ({
        label: `Versement ${index + 1}`,
        amount_minor: 4000,
        due_on: `${index < 2 ? 2026 : 2027}-${day}`,
      })),
    });
    await screen.findByText("Échéancier enregistré : Minerval en 6 versements.");
  });

  it("frais dus visibles au caissier, sans échéancier particulier", async () => {
    mockApi(routes("cashier", { ...card, "GET /api/student-charges/": charges }));
    renderApp(`/students/${STUDENT}/finances`);
    await screen.findByText("Minerval · 2e tranche");
    expect(screen.queryByRole("link", { name: "Échéancier particulier" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Ajouter une réduction" })).toBeNull();
  });

  it("réduction : effet calculé comme le serveur, envoi en entiers, rien sans motif", async () => {
    const requests = mockApi(
      routes("head", {
        ...card,
        "GET /api/student-charges/": charges,
        "POST /api/discounts/": json({}, 201),
      }),
    );
    const { user } = renderApp(`/students/${STUDENT}/finances`);
    await user.click(await screen.findByRole("button", { name: "Ajouter une réduction" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Bourse" }));

    // 25 % du minerval (3 × 120,00 $) : 30,00 $ par tranche.
    await user.type(within(dialog).getByLabelText("Valeur"), "25");
    expect(within(dialog).getAllByText("− 30,00 $")).toHaveLength(3);
    within(dialog).getByText("270,00 $");
    await user.click(within(dialog).getByRole("button", { name: "Accorder la réduction" }));
    await within(dialog).findByText("Ce champ est obligatoire.");

    // 50,00 $ au prorata : l'écart d'arrondi sur la dernière tranche.
    await user.click(within(dialog).getByRole("radio", { name: "Montant" }));
    await user.clear(within(dialog).getByLabelText("Valeur"));
    await user.type(within(dialog).getByLabelText("Valeur"), "50");
    expect(within(dialog).getAllByText("− 16,67 $")).toHaveLength(2);
    within(dialog).getByText("− 16,66 $");
    expect(posts(requests, "/api/discounts/")).toHaveLength(0);

    await user.type(within(dialog).getByLabelText(/^Motif/), "Bourse de la paroisse");
    await user.click(within(dialog).getByRole("button", { name: "Accorder la réduction" }));
    await waitFor(() => expect(posts(requests, "/api/discounts/")).toHaveLength(1));
    expect(posts(requests, "/api/discounts/")[0]!.body).toEqual({
      enrollment: id(80),
      fee_type: id(500),
      kind: "amount",
      amount_minor: 5000,
      reason_code: "scholarship",
      reason: "Bourse de la paroisse",
    });
    await screen.findByText("Réduction accordée : ce que doit l'élève est à jour.");
  });

  it("lier l'élève à une autre famille : recherche, choix, puis envoi de la famille seule", async () => {
    const other = { ...family, id: id(201), code: "P4TR8KWE", students: [] };
    const requests = mockApi(
      routes("head", {
        ...card,
        "GET /api/families/": { count: 2, next: null, previous: null, results: [family, other] },
        [`PATCH /api/students/${STUDENT}/`]: detail(STUDENT),
      }),
    );
    const { user } = renderApp(`/students/${STUDENT}/family`);

    await user.click(await screen.findByRole("button", { name: "Lier à une autre famille" }));
    await user.type(screen.getByRole("searchbox"), "Kahindo");
    await user.click(await screen.findByRole("button", { name: "Choisir" }));
    await user.click(screen.getByRole("button", { name: "Lier à cette famille" }));

    await waitFor(() =>
      expect(requests.find((request) => request.method === "PATCH")?.body).toEqual({
        family: other.id,
        allow_duplicate: false,
      }),
    );
  });

  it("Ctrl K : cherche un élève dans l'en-tête et ouvre sa fiche avec Entrée", async () => {
    const requests = mockApi(
      routes("cashier", { ...card, [`GET /api/students/${id(412)}/`]: detail(id(412)) }),
    );
    const { user } = renderApp("/");

    await screen.findByRole("button", { name: "Rechercher un élève" });
    await user.keyboard("{Control>}k{/Control}");
    await user.type(await screen.findByRole("searchbox"), "kam");
    expect(await screen.findByText("3e Électricité A · ITIG-2026-0412")).toBeTruthy();
    expect(requests.at(-1)!.query).toEqual({ search: "kam" });
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("heading", { name: "BISIMWA MUGISHO Arsène" })).toBeTruthy();
    expect(screen.queryByRole("searchbox")).toBeNull();
  });

  it("fiche d'inscription depuis la fiche élève : format et code famille dans l'aperçu et le PDF", async () => {
    mockApi(routes("cashier", card));
    const { user } = renderApp(`/students/${STUDENT}`);

    await user.click(await screen.findByRole("link", { name: "Fiche d'inscription" }));
    const pdf = await screen.findByRole("link", { name: "PDF" });
    expect(pdf.getAttribute("href")).toBe(
      `/api/enrollments/${id(80)}/form/?output=pdf&paper=a4&family_code=true&fees=true`,
    );
    await user.click(screen.getByRole("radio", { name: "A5" }));
    await user.click(screen.getByLabelText("Inclure le code famille"));
    expect(screen.getByTitle("Aperçu de la fiche d'inscription").getAttribute("src")).toBe(
      `/api/enrollments/${id(80)}/form/?output=html&paper=a5&family_code=false&fees=true`,
    );
  });

  it("liste de classe : classe venue de la liste, colonnes, colonnes vides et ordre dans l'Excel", async () => {
    mockApi(routes("cashier"));
    const { user } = renderApp(`/students/class-list?class=${group.id}`);

    const excel = await screen.findByRole("link", { name: "Excel" });
    await user.click(screen.getByLabelText("Sexe et date de naissance"));
    await user.click(screen.getByLabelText("Téléphone du tuteur principal"));
    await user.click(screen.getByRole("radio", { name: "Matricule" }));
    expect(excel.getAttribute("href")).toBe(
      `/api/enrollments/class-list/?class_group=${group.id}&output=xlsx&blank_columns=2&order=matricule&columns=matricule&columns=guardian_phone`,
    );
  });
});
