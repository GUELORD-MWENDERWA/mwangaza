// Cours de chaque classe et charges des enseignants (8.1), lus avec le droit `courses.configure`.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Course = Schemas["Course"];
export type OfficialGrid = Schemas["OfficialGrid"];
export type TeachingLoads = Schemas["TeachingLoads"];

export function useCourses(classId: string) {
  return useQuery({
    queryKey: [...keys.courses, classId],
    queryFn: () =>
      call(api.GET("/api/class-groups/{id}/courses/", { params: { path: { id: classId } } })),
    enabled: Boolean(classId),
  });
}

export function useOfficialGrids() {
  return useQuery({
    queryKey: keys.courseTemplates,
    queryFn: () => call(api.GET("/api/course-templates/")),
    staleTime: Infinity,
  });
}

/** Tout le personnel actif avec sa charge de l'année en cours : sert aussi de liste des
 *  enseignants possibles. */
export function useTeachingLoads() {
  return useQuery({
    queryKey: keys.teachingLoads,
    queryFn: () => call(api.GET("/api/teaching-loads/")),
  });
}
