// Élèves et familles (D2-D4) : `students.view` pour lire, `students.edit` pour inscrire et
// modifier. Les années, options et classes (filtres, inscription) se lisent aussi avec
// `students.view`.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import type { Permission } from "../../lib/permissions";
import { keys } from "../../lib/queries";

export type StudentRow = Schemas["StudentList"];
export type Student = Schemas["Student"];
export type Family = Schemas["FamilyDetail"];
export type Guardian = Schemas["Guardian"];
export type HistoryEntry = Schemas["StudentHistory"];
export type Relationship = Schemas["RelationshipEnum"];
export type StudentStatus = "active" | "left" | "not_enrolled";
export type Charge = Schemas["StudentCharge"];
export type Discount = Schemas["Discount"];
export type DiscountReason = Schemas["ReasonCodeEnum"];

export const DISCOUNT_REASONS: DiscountReason[] = [
  "staff_child",
  "sibling",
  "scholarship",
  "waiver",
  "other",
];

/** Droits qui montrent les frais dus d'un élève (comme `CHARGES_READ` du serveur). */
export const CHARGES_READ: Permission[] = [
  "finance.collect_payment",
  "finance.grant_discount",
  "finance.configure_fees",
  "finance.view_reports",
];

export const RELATIONSHIPS: Relationship[] = [
  "father",
  "mother",
  "guardian",
  "grandparent",
  "sibling",
  "other",
];

export type StudentQuery = {
  search?: string;
  academic_year?: string;
  class_group?: string;
  track?: string;
  status?: StudentStatus;
};

export function useStudents(query: StudentQuery, page: number) {
  return useQuery({
    queryKey: [...keys.students, query, page],
    queryFn: () =>
      call(
        api.GET("/api/students/", {
          params: { query: { ...query, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Familles d'un tuteur (nom ou téléphone) ou d'un code : les premières suffisent. */
export function useFamilySearch(search: string) {
  return useQuery({
    queryKey: [...keys.families, search],
    queryFn: () => call(api.GET("/api/families/", { params: { query: { search } } })),
    enabled: search.length >= 2,
  });
}

export function useStudent(id: string) {
  return useQuery({
    queryKey: [...keys.students, "detail", id],
    queryFn: () => call(api.GET("/api/students/{id}/", { params: { path: { id } } })),
  });
}

export function useFamily(id: string | undefined) {
  return useQuery({
    queryKey: [...keys.families, "detail", id],
    queryFn: () => call(api.GET("/api/families/{id}/", { params: { path: { id: id! } } })),
    enabled: Boolean(id),
  });
}

/** Journal de l'élève, de ses inscriptions et de sa famille, le plus récent d'abord. */
export function useStudentHistory(id: string, page: number) {
  return useQuery({
    queryKey: [...keys.students, "history", id, page],
    queryFn: () =>
      call(
        api.GET("/api/students/{id}/history/", {
          params: { path: { id }, query: page > 1 ? { page } : {} },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Envoie la photo (déjà réduite par `shrinkPhoto`) ; renvoie la fiche à jour. */
export function uploadPhoto(id: string, photo: File) {
  const body = new FormData();
  body.append("photo", photo);
  return call(
    api.POST("/api/students/{id}/photo/", {
      params: { path: { id } },
      body: body as unknown as { photo: string },
    }),
  );
}

/** Âge en années révolues à la date du jour (`AAAA-MM-JJ`). */
export function age(birthDate: string, today = new Date()): number {
  const [year = 0, month = 1, day = 1] = birthDate.split("-").map(Number);
  const thisMonth = today.getMonth() + 1;
  const before = thisMonth < month || (thisMonth === month && today.getDate() < day);
  return today.getFullYear() - year - (before ? 1 : 0);
}

/** Recherche rapide (`Ctrl K`) : les premiers élèves trouvés, à partir de 2 caractères. */
export function useStudentSearch(search: string) {
  return useQuery({
    queryKey: [...keys.students, "search", search],
    queryFn: () => call(api.GET("/api/students/", { params: { query: { search } } })),
    enabled: search.length >= 2,
  });
}

// Import d'une liste d'élèves (D1) : `students.import`.

export type StudentImport = Schemas["StudentImport"];
export type ImportLine = Schemas["ImportLine"];
export type ImportField = keyof Schemas["ImportMapping"];

export const IMPORT_FIELDS: ImportField[] = [
  "last_name",
  "middle_name",
  "first_name",
  "sex",
  "birth_date",
  "birth_place",
  "class_name",
  "matricule",
  "guardian_name",
  "guardian_phone",
];

/** L'import, relu toutes les 1,5 s tant que la tâche de fond tourne. */
export function useStudentImport(id: string | undefined) {
  return useQuery({
    queryKey: [...keys.studentImports, id],
    queryFn: () => call(api.GET("/api/student-imports/{id}/", { params: { path: { id: id! } } })),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data?.status === "importing" ? 1500 : false),
  });
}

export function useImportLines(id: string, problems: boolean, page: number) {
  return useQuery({
    queryKey: [...keys.studentImports, id, "lines", problems, page],
    queryFn: () =>
      call(
        api.GET("/api/student-imports/{id}/lines/", {
          params: { path: { id }, query: { problems, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function uploadImport(file: File, academicYear: string) {
  const body = new FormData();
  body.append("file", file);
  if (academicYear) body.append("academic_year", academicYear);
  return call(
    api.POST("/api/student-imports/", {
      body: body as unknown as { file: string; academic_year?: string },
    }),
  );
}

export function updateImport(id: string, body: Schemas["PatchedStudentImportUpdateRequest"]) {
  return call(api.PATCH("/api/student-imports/{id}/", { params: { path: { id } }, body }));
}

export function confirmImport(id: string) {
  return call(api.POST("/api/student-imports/{id}/confirm/", { params: { path: { id } } }));
}

export const importTemplateUrl = "/api/student-imports/template/";
export const importReportUrl = (id: string) => `/api/student-imports/${id}/report/`;

// Impressions (D5, M11) : aperçu HTML dans la page, PDF que le navigateur ouvre ou enregistre.
export type Paper = "a4" | "a5";
export type ClassListColumn = "matricule" | "sex_birth" | "guardian_phone";
export type ClassListOrder = "name" | "matricule";

export function registrationFormUrl(
  enrollmentId: string,
  options: { output: "html" | "pdf"; paper: Paper; familyCode: boolean },
) {
  const query = new URLSearchParams({
    output: options.output,
    paper: options.paper,
    family_code: String(options.familyCode),
  });
  return `/api/enrollments/${enrollmentId}/form/?${query}`;
}

export function classListUrl(
  classGroup: string,
  options: {
    output: "html" | "pdf" | "xlsx";
    columns: ClassListColumn[];
    blankColumns: number;
    order: ClassListOrder;
  },
) {
  const query = new URLSearchParams({
    class_group: classGroup,
    output: options.output,
    blank_columns: String(options.blankColumns),
    order: options.order,
  });
  for (const column of options.columns) query.append("columns", column);
  return `/api/enrollments/class-list/?${query}`;
}

/** Frais dus d'une inscription, par date limite (sous `keys.students` : un changement de classe
 *  les rafraîchit). */
export function useCharges(enrollment: string | undefined) {
  return useQuery({
    queryKey: [...keys.students, "charges", enrollment],
    queryFn: () =>
      call(api.GET("/api/student-charges/", { params: { query: { enrollment: enrollment! } } })),
    enabled: Boolean(enrollment),
  });
}

/** Réductions d'une inscription, retirées comprises (E3). */
export function useDiscounts(enrollment: string | undefined) {
  return useQuery({
    queryKey: [...keys.students, "discounts", enrollment],
    queryFn: () =>
      call(api.GET("/api/discounts/", { params: { query: { enrollment: enrollment! } } })),
    enabled: Boolean(enrollment),
  });
}
