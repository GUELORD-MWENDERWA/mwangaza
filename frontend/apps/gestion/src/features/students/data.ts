// Élèves et familles (D2-D4) : `students.view` pour lire, `students.edit` pour inscrire. Les
// années, options et classes (filtres, inscription) se lisent aussi avec `students.view`.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type StudentRow = Schemas["StudentList"];
export type Family = Schemas["FamilyDetail"];
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
