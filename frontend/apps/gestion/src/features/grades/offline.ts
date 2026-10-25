// Notes sans réseau (8.2.3) : la liste des cours et chaque feuille lue en ligne sont gardées sur
// l'appareil ; un enregistrement hors ligne (ou pendant que des notes attendent d'être envoyées)
// met à jour la feuille gardée et ajoute l'opération `grades.save` à la file, dans une seule
// transaction. À la reconnexion la file part, dans l'ordre ; refusée (date limite, feuille
// validée…), l'opération reste dans la file avec sa raison, montrée sur la feuille.
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";

import { uuidv7 } from "../../lib/ids";
import type { LocalDb, QueuedOperation } from "../../lib/sync/db";
import { isNetworkError, keep, kept } from "../../lib/sync/reads";
import { syncNow } from "../../lib/sync/session";
import type { Sheet } from "./data";
import { applySave, type SaveBody } from "./sheet";

export const GRADING_ID = "grading";
export const sheetId = (course: string, term: string) => `sheet|${course}|${term}`;

/** Garde ce que le serveur vient de donner (`lib/sync/reads.ts`). */
export const remember = (db: LocalDb, id: string, value: unknown, readAt = Date.now()) =>
  keep(db.grades, id, value, readAt);

export const recall = <T>(db: LocalDb, id: string) => kept<T>(db.grades, id);

export { isNetworkError };

const isSheetOp = (op: QueuedOperation, course: string, term: string) =>
  op.type === "grades.save" && op.payload.course === course && op.payload.term === term;

/** Opérations de cette feuille dans la file : en attente ou envoyées pas encore reprises par la
 *  descente (la feuille de l'appareil est la plus à jour), et refusées. */
export async function sheetQueue(db: LocalDb, course: string, term: string) {
  const all = await db.outbox.orderBy("seq").toArray();
  const mine = all.filter((op) => isSheetOp(op, course, term));
  return {
    waiting: mine.filter((op) => op.status !== "rejected"),
    rejected: mine.filter((op) => op.status === "rejected"),
  };
}

/** Enregistrement fait sur l'appareil : feuille gardée mise à jour et opération ajoutée, ensemble.
 *  Rend la feuille telle qu'elle est maintenant. */
export async function saveOffline(
  db: LocalDb,
  { course, term, sheet, body }: { course: string; term: string; sheet: Sheet; body: SaveBody },
): Promise<Sheet> {
  const next = applySave(sheet, body);
  const now = new Date().toISOString();
  await db.transaction("rw", [db.grades, db.outbox], async () => {
    await db.grades.put({ id: sheetId(course, term), value: next, readAt: Date.now() });
    await db.outbox.add({
      op_id: uuidv7(),
      type: "grades.save",
      payload: {
        course,
        term,
        evaluations: body.evaluations,
        removed_evaluations: body.removed_evaluations,
        grades: body.grades,
        reason: body.reason,
      },
      created_at: now,
      status: "pending",
      error: null,
    });
  });
  void syncNow();
  return next;
}

/** Retire de la file les refus déjà lus de cette feuille. */
export async function dismissRejected(db: LocalDb, rejected: QueuedOperation[]) {
  await db.outbox.bulkDelete(rejected.flatMap((op) => (op.seq === undefined ? [] : [op.seq])));
}

export type SheetQueue = Awaited<ReturnType<typeof sheetQueue>>;

/** La file de cette feuille, relue à chaque changement. */
export function useSheetQueue(db: LocalDb | null, course: string, term: string): SheetQueue | null {
  const [state, setState] = useState<SheetQueue | null>(null);
  useEffect(() => {
    if (!db) return;
    const subscription = liveQuery(() => sheetQueue(db, course, term)).subscribe({
      next: setState,
      error: () => setState(null),
    });
    return () => subscription.unsubscribe();
  }, [db, course, term]);
  return db ? state : null;
}
