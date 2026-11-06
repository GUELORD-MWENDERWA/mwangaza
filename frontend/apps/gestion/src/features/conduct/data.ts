// Conduite (8.5.1a) : liste des infractions, seuils des cotes, classes et élèves à choisir,
// incidents d'un élève. Lus avec `discipline.record` (ou `discipline.configure`). Ce que l'écran
// d'attribution lit en ligne reste sur l'appareil, lisible sans réseau (HL.2, `offline.ts`).
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";
import { readOrKept } from "../../lib/sync/reads";
import { useSyncStatus } from "../../lib/sync/session";
import { conductId } from "./offline";

export type Rule = Schemas["Rule"];
export type ScaleRow = Schemas["ScaleRow"];
export type StudentIncidents = Schemas["StudentIncidents"];
export type Incident = Schemas["Incident"];
export type TermConduct = StudentIncidents["totals"][number];

/** Lecture en ligne gardée sur l'appareil ; sans réponse du serveur, la copie gardée. */
function useKept<T>(id: string, read: () => Promise<T>) {
  const { db } = useSyncStatus();
  return async () => (await readOrKept(db?.reads ?? null, id, read)).value;
}

export function useRules(all = false) {
  const read = () => call(api.GET("/api/discipline/rules/", { params: { query: { all } } }));
  const kept = useKept(conductId("rules"), read);
  return useQuery({
    queryKey: [...keys.conduct, "rules", all],
    // Seule la liste en usage sert sans réseau (attribuer) ; le barème complet, en ligne.
    queryFn: all ? read : kept,
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
    queryFn: useKept(conductId("classes"), () => call(api.GET("/api/discipline/classes/"))),
  });
}

/** Élèves d'une classe : sans réseau, seulement une classe déjà ouverte en ligne ici. */
export function useClassStudents(classId: string) {
  return useQuery({
    queryKey: [...keys.conduct, "students", classId],
    queryFn: useKept(conductId("students", classId), () =>
      call(
        api.GET("/api/discipline/classes/{id}/students/", { params: { path: { id: classId } } }),
      ),
    ),
    enabled: Boolean(classId),
  });
}

export function useStudentIncidents(enrollmentId: string) {
  return useQuery({
    queryKey: [...keys.conduct, "incidents", enrollmentId],
    queryFn: useKept(conductId("incidents", enrollmentId), () =>
      call(
        api.GET("/api/discipline/enrollments/{id}/", { params: { path: { id: enrollmentId } } }),
      ),
    ),
    enabled: Boolean(enrollmentId),
  });
}
