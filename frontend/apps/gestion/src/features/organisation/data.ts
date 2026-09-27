// Données de l'organisation scolaire (C1-C3), lues avec le droit `classes.manage`. Listes de
// configuration : sans pagination (des dizaines de lignes).
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Year = Schemas["AcademicYear"];
export type Term = Schemas["Term"];
export type Level = Schemas["Level"];
export type Track = Schemas["Track"];
export type ClassGroup = Schemas["ClassGroup"];
export type Person = Schemas["Person"];
export type Cycle = Schemas["CycleEnum"];
export type Template = Schemas["TemplateEnum"];

export const CYCLES: Cycle[] = [
  "primary",
  "basic",
  "secondary_general",
  "secondary_technical",
  "higher",
  "vocational",
];
export const TEMPLATES: Template[] = ["secondary", "trimesters", "empty"];

export function useYears() {
  return useQuery({
    queryKey: keys.years,
    queryFn: () => call(api.GET("/api/academic-years/")),
  });
}

export function useLevels() {
  return useQuery({ queryKey: keys.levels, queryFn: () => call(api.GET("/api/levels/")) });
}

export function useTracks() {
  return useQuery({ queryKey: keys.tracks, queryFn: () => call(api.GET("/api/tracks/")) });
}

export function useClasses(year: string) {
  return useQuery({
    queryKey: [...keys.classes, year],
    queryFn: () =>
      call(api.GET("/api/class-groups/", { params: { query: { academic_year: year } } })),
  });
}

export function useHomeroomCandidates() {
  return useQuery({
    queryKey: keys.homeroomCandidates,
    queryFn: () => call(api.GET("/api/class-groups/homeroom-candidates/")),
  });
}

/** Après un changement : relire ce qui en dépend (les classes affichent niveaux et options). */
export function useRefresh() {
  const queryClient = useQueryClient();
  return (...queryKeys: (readonly string[])[]) =>
    Promise.all(queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}
