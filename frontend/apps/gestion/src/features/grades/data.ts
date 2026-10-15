// Notes (8.2.1), lues avec `grades.enter` ou `grades.enter_any` : ce que le compte peut noter, et
// la feuille d'un cours dans une période ou des examens.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import type { LocalDb } from "../../lib/sync/db";
import { keys } from "../../lib/queries";
import { useSyncStatus } from "../../lib/sync/session";
import { GRADING_ID, isNetworkError, recall, remember, sheetId, sheetQueue } from "./offline";

export type Grading = Schemas["Grading"];
export type GradingClass = Schemas["GradingClass"];
export type GradingCourse = Schemas["GradingCourse"];
export type Sheet = Schemas["Sheet"];
export type Validation = Schemas["Validation"];

/** Lecture en ligne, gardée sur l'appareil (8.2.3) ; sans réponse du serveur, la copie gardée. */
async function readOrRecall<T>(
  db: LocalDb | null,
  id: string,
  read: () => Promise<T>,
  prefer: () => Promise<boolean> = async () => false,
): Promise<T> {
  if (db && (await prefer())) {
    const local = await recall<T>(db, id);
    if (local) return local.value;
  }
  const startedAt = Date.now();
  try {
    const value = await read();
    if (db) void remember(db, id, value, startedAt).catch(() => undefined);
    return value;
  } catch (error) {
    const local = db && isNetworkError(error) ? await recall<T>(db, id) : undefined;
    if (local) return local.value;
    throw error;
  }
}

export function useGrading() {
  const { db } = useSyncStatus();
  return useQuery({
    queryKey: keys.grading,
    queryFn: () => readOrRecall(db, GRADING_ID, () => call(api.GET("/api/grading/"))),
  });
}

export function useSheet(courseId: string, termId: string) {
  const { db } = useSyncStatus();
  return useQuery({
    queryKey: [...keys.gradeSheet, courseId, termId],
    queryFn: () =>
      readOrRecall(
        db,
        sheetId(courseId, termId),
        () =>
          call(
            api.GET("/api/courses/{id}/terms/{term}/grades/", {
              params: { path: { id: courseId, term: termId } },
            }),
          ),
        // Notes saisies ici pas encore reprises par le serveur : la copie de l'appareil est la
        // plus à jour.
        async () => (await sheetQueue(db!, courseId, termId)).waiting.length > 0,
      ),
    enabled: Boolean(courseId && termId),
  });
}

/** Feuilles envoyées à valider et dates limites (droit `grades.validate`). */
export function useValidation() {
  return useQuery({
    queryKey: keys.gradeValidation,
    queryFn: () => call(api.GET("/api/grading/validation/")),
  });
}
