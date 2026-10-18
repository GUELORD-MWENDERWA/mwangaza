// Notes (8.2.1), lues avec `grades.enter` ou `grades.enter_any` : ce que le compte peut noter, et
// la feuille d'un cours dans une période ou des examens.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import type { LocalDb } from "../../lib/sync/db";
import { keys } from "../../lib/queries";
import { useSyncStatus } from "../../lib/sync/session";
import { layoutQuery, type PrintLayout } from "../printing/printOptions";
import { GRADING_ID, isNetworkError, recall, remember, sheetId, sheetQueue } from "./offline";

export type Grading = Schemas["Grading"];
export type GradingClass = Schemas["GradingClass"];
export type GradingCourse = Schemas["GradingCourse"];
export type Sheet = Schemas["Sheet"];
export type TotalsSheet = Schemas["TotalsSheet"];
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

/** Feuilles de notes pas encore validées dans la classe : tant qu'il en reste, le PDF du bulletin
 *  est refusé. Les notes validées changent à chaque validation : toujours relu. */
export function useReportStatus(classId: string) {
  return useQuery({
    queryKey: [...keys.grading, "report-status", classId],
    queryFn: () =>
      call(
        api.GET("/api/class-groups/{id}/report-card-status/", {
          params: { path: { id: classId } },
        }),
      ),
    enabled: Boolean(classId),
    staleTime: 0,
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

/** Fiche de cotes d'un cours (NB.1) : le total de chaque élève, une fois envoyée ; en ligne. */
export function useTotalsSheet(courseId: string, termId: string) {
  return useQuery({
    queryKey: [...keys.gradeSheet, "totals", courseId, termId],
    queryFn: () =>
      call(
        api.GET("/api/courses/{id}/terms/{term}/grades/totals/", {
          params: { path: { id: courseId, term: termId } },
        }),
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

/** Réglages d'impression du bulletin (8.3.5) : notes seules sur le formulaire pré-imprimé, et
 *  calage en mm (chaque imprimante décale un peu). */
export type CardPrint = { gradesOnly: boolean; dx: number; dy: number };
export const DEFAULT_CARD_PRINT: CardPrint = { gradesOnly: false, dx: 0, dy: 0 };

/** Bulletin (8.3.2) d'un élève de la classe, ou de toute la classe sans `enrollmentId` (8.3.5) :
 *  PDF ou son aperçu HTML. */
export function reportCardUrl(
  classId: string,
  enrollmentId: string | null,
  output: "html" | "pdf",
  print: CardPrint = DEFAULT_CARD_PRINT,
) {
  const query = new URLSearchParams({ output });
  if (enrollmentId) query.set("enrollment", enrollmentId);
  if (print.gradesOnly) query.set("mode", "grades_only");
  if (print.dx) query.set("dx", String(print.dx));
  if (print.dy) query.set("dy", String(print.dy));
  return `/api/class-groups/${classId}/report-card/?${query}`;
}

export type SheetKind = "course" | "blank" | "class";

/** Fiche de cotes (8.3.6) d'une classe : d'un cours, vierge, ou tableau de la classe ; PDF ou son
 *  aperçu HTML. `layout` : papier et sens (8.3.4). */
export function gradeSheetUrl(
  classId: string,
  options: {
    kind: SheetKind;
    output: "html" | "pdf";
    layout: PrintLayout;
    course?: string;
    column?: string;
    columns: string[];
    blankColumns: number;
  },
) {
  const query = new URLSearchParams({ kind: options.kind, output: options.output });
  if (options.kind !== "class") query.set("course", options.course ?? "");
  if (options.kind === "class") query.set("column", options.column || "year");
  if (options.kind === "blank") query.set("blank_columns", String(options.blankColumns));
  for (const column of options.columns) query.append("columns", column);
  for (const [key, value] of Object.entries(layoutQuery(options.layout))) query.set(key, value);
  return `/api/class-groups/${classId}/grade-sheet/?${query}`;
}
