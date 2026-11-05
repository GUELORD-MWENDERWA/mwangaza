// Conduite sans réseau (HL.2) : classes, infractions, élèves d'une classe et incidents d'un élève
// lus en ligne restent sur l'appareil (`db.reads`). Une infraction attribuée sans réseau (ou
// pendant que d'autres attendent : l'ordre compte) va dans la file, `incident.record`, avec
// l'identifiant donné ici : rejouée, elle n'est jamais écrite deux fois. Elle est montrée dans
// l'historique de l'élève jusqu'à son envoi ; refusée, elle reste dans la file avec sa raison.
// Annuler un incident et corriger une cote demandent le réseau (décisions rares, au bureau).
import { api, call } from "@mwangaza/api";
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";

import { uuidv7 } from "../../lib/ids";
import type { LocalDb, QueuedOperation } from "../../lib/sync/db";
import { isNetworkError } from "../../lib/sync/reads";
import { syncNow } from "../../lib/sync/session";

export const INCIDENT_OP = "incident.record";

/** Clé d'une lecture gardée : `conduct|classes`, `conduct|students|<classe>`… */
export const conductId = (...parts: string[]) => ["conduct", ...parts].join("|");

export type IncidentBody = {
  enrollment: string;
  rule: string;
  occurred_on: string;
  note: string;
};

/** Infractions de la file : en attente (ou envoyées, pas encore relues) et refusées. */
export async function incidentsQueue(db: LocalDb) {
  const all = await db.outbox.where("status").anyOf("pending", "sent", "rejected").toArray();
  const mine = all.filter((op) => op.type === INCIDENT_OP).sort((a, b) => a.seq! - b.seq!);
  return {
    waiting: mine.filter((op) => op.status !== "rejected"),
    rejected: mine.filter((op) => op.status === "rejected"),
  };
}

export type IncidentsQueue = Awaited<ReturnType<typeof incidentsQueue>>;

export function useIncidentsQueue(db: LocalDb | null): IncidentsQueue | null {
  const [state, setState] = useState<IncidentsQueue | null>(null);
  useEffect(() => {
    if (!db) return;
    const subscription = liveQuery(() => incidentsQueue(db)).subscribe({
      next: setState,
      error: () => setState(null),
    });
    return () => subscription.unsubscribe();
  }, [db]);
  return db ? state : null;
}

async function queueIncident(db: LocalDb, payload: IncidentBody & { id: string }) {
  await db.outbox.add({
    op_id: uuidv7(),
    type: INCIDENT_OP,
    payload,
    created_at: new Date().toISOString(),
    status: "pending",
    error: null,
  });
  void syncNow();
}

/** Attribue l'infraction : au serveur, ou dans la file de l'appareil sans réseau (ou si d'autres
 *  attendent). Le même identifiant sert aux deux : une réponse perdue puis un envoi par la file
 *  n'écrivent qu'un incident. Rend `queued` si elle attend le réseau. */
export async function sendIncident(
  db: LocalDb | null,
  body: IncidentBody,
): Promise<"sent" | "queued"> {
  const payload = { ...body, id: uuidv7() };
  const waiting = db ? (await incidentsQueue(db)).waiting.length : 0;
  if (db && (!navigator.onLine || waiting > 0)) {
    await queueIncident(db, payload);
    return "queued";
  }
  try {
    await call(api.POST("/api/discipline/incidents/", { body: payload }));
    return "sent";
  } catch (error) {
    if (!db || !isNetworkError(error)) throw error;
    await queueIncident(db, payload);
    return "queued";
  }
}

/** Retire de la file les refus déjà lus. */
export async function dismissRejected(db: LocalDb, rejected: QueuedOperation[]) {
  await db.outbox.bulkDelete(rejected.flatMap((op) => (op.seq === undefined ? [] : [op.seq])));
}
