// Conduite (8.5.1a) : liste des infractions, seuils des cotes, classes et élèves à choisir,
// incidents d'un élève. Lus avec `discipline.record` (ou `discipline.configure`) ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Rule = Schemas["Rule"];
export type ScaleRow = Schemas["ScaleRow"];
export type StudentIncidents = Schemas["StudentIncidents"];
export type Incident = Schemas["Incident"];

export function useRules(all = false) {
  return useQuery({
    queryKey: [...keys.conduct, "rules", all],
    queryFn: () => call(api.GET("/api/discipline/rules/", { params: { query: { all } } })),
  });
}

export function useScale() {
  return useQuery({
    queryKey: [...keys.conduct, "scale"],
    queryFn: () => call(api.GET("/api/discipline/scale/")),
  });
}

export function useConductClasses() {
  return useQuery({
    queryKey: [...keys.conduct, "classes"],
    queryFn: () => call(api.GET("/api/discipline/classes/")),
  });
}

export function useClassStudents(classId: string) {
  return useQuery({
    queryKey: [...keys.conduct, "students", classId],
    queryFn: () =>
      call(
        api.GET("/api/discipline/classes/{id}/students/", { params: { path: { id: classId } } }),
      ),
    enabled: Boolean(classId),
  });
}

export function useStudentIncidents(enrollmentId: string) {
  return useQuery({
    queryKey: [...keys.conduct, "incidents", enrollmentId],
    queryFn: () =>
      call(
        api.GET("/api/discipline/enrollments/{id}/", { params: { path: { id: enrollmentId } } }),
      ),
    enabled: Boolean(enrollmentId),
  });
}
