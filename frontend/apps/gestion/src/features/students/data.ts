// Élèves et familles (D2-D4) : `students.view` pour lire, `students.edit` pour inscrire et
// modifier. Les années, options et classes (filtres, inscription) se lisent aussi avec
// `students.view`.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type StudentRow = Schemas["StudentList"];
export type Student = Schemas["Student"];
export type Family = Schemas["FamilyDetail"];
export type Guardian = Schemas["Guardian"];
export type HistoryEntry = Schemas["StudentHistory"];
export type Relationship = Schemas["RelationshipEnum"];
export type StudentStatus = "active" | "left" | "not_enrolled";

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
