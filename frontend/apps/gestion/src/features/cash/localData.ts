// Caisse d'un appareil mémorisé (F5, 3.5) : la base de l'appareil lue en direct (chaque
// synchronisation et chaque encaissement mettent l'écran à jour) ; ouverture, encaissement,
// réimpression, crédit utilisé (3.6.2), demande d'annulation (3.8.1), sortie de caisse (FIN.2)
// et clôture (3.8.2) s'écrivent dans la file d'opérations, avec ou sans réseau, puis partent au
// serveur tout de suite s'il y en a un.
import type { Schemas } from "@mwangaza/api";
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";

import { uuidv7 } from "../../lib/ids";
import type { LocalCashOut, LocalDb, LocalEnrollment, QueuedOperation } from "../../lib/sync/db";
import type { Config } from "../../lib/sync/engine";
import { syncNow } from "../../lib/sync/session";
import { queuedEnrollments } from "../students/offline";
import type { Line } from "./allocation";
import { creditUse, offlinePayload } from "./offline";
import type { Receipt } from "./Receipt";

type Live<T> = { data?: T; error?: unknown };

/** Résultat d'une lecture de la base, relu à chaque changement des tables lues. */
export function useLive<T>(db: LocalDb, query: (db: LocalDb) => Promise<T>): Live<T> {
  const [state, setState] = useState<Live<T> & { db?: LocalDb }>({});
  useEffect(() => {
    const subscription = liveQuery(() => query(db)).subscribe({
      next: (data) => setState({ db, data }),
      error: (error: unknown) => setState({ db, error }),
    });
    return () => subscription.unsubscribe();
    // `query` : une fonction du module, la même à chaque rendu.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db]);
  return state.db === db ? state : {};
}

export type LocalCash = {
  enrollments: LocalEnrollment[];
  byId: Map<string, LocalEnrollment>;
  config: Config | null;
  /** Dernière session de caisse lue en ligne. */
  saved: Schemas["CurrentCashSession"] | null;
  /** Opérations de la file, dans l'ordre. */
  queued: QueuedOperation[];
  /** Sorties de caisse faites ici, des sessions pas encore clôturées au serveur (FIN.2). */
  cashOuts: LocalCashOut[];
};

const readState = async (db: LocalDb) => {
  const [enrollments, config, saved, cashOuts] = await Promise.all([
    db.enrollments.toArray(),
    db.config.get("config"),
    db.cash.get("session"),
    db.cashOuts.toArray(),
  ]);
  return {
    enrollments,
    byId: new Map(enrollments.map((item) => [item.id, item])),
    config: config?.value ?? null,
    saved: saved?.value ?? null,
    cashOuts,
  };
};

const readQueue = (db: LocalDb) => db.outbox.orderBy("seq").toArray();

/** L'état reçu du serveur (qui change à la synchronisation) et la file (à chaque encaissement),
 *  lus à part ; les élèves inscrits ici et pas encore descendus s'y ajoutent (HL.1). */
export function useLocalCash(db: LocalDb): Live<LocalCash> {
  const state = useLive(db, readState);
  const queue = useLive(db, readQueue);
  const error = state.error ?? queue.error;
  if (error) return { error };
  if (!state.data || !queue.data) return {};
  return { data: withEnrolledHere(state.data, queue.data) };
}

function withEnrolledHere(known: Omit<LocalCash, "queued">, queued: QueuedOperation[]): LocalCash {
  const added = queuedEnrollments(queued, known.byId);
  if (!added.length) return { ...known, queued };
  const enrollments = [...known.enrollments, ...added];
  const byId = new Map(enrollments.map((item) => [item.id, item]));
  return { ...known, enrollments, byId, queued };
}

/** Session lue en ligne à `readAt` : gardée pour continuer sans réseau, sauf si l'appareil en
 *  sait déjà plus récent (ouverture acceptée entre-temps). */
export async function saveSession(
  db: LocalDb,
  value: Schemas["CurrentCashSession"],
  readAt: number,
) {
  await db.transaction("rw", db.cash, async () => {
    const saved = await db.cash.get("session");
    if ((saved?.readAt ?? 0) <= readAt) await db.cash.put({ id: "session", value, readAt });
  });
}

/** Session de la caisse de l'appareil : celle gardée (lue en ligne, ou ouverture acceptée),
 *  sinon celle ouverte ici et pas encore acceptée ; jamais une session clôturée ici (3.8.2). */
export function deviceSession(
  known: Schemas["CurrentCashSession"],
  queued: QueuedOperation[],
): { session: Schemas["CashSession"] | undefined; opening: QueuedOperation | undefined } {
  const opening = queued.filter((op) => op.type === "cash_session.open").at(-1);
  const refused = opening?.status === "rejected";
  const closed = closedHere(queued);
  const session = [known.session, refused ? undefined : opening?.session].find(
    (item) => item && !closed.has(item.id),
  );
  return { session: session ?? undefined, opening };
}

/** Ouverture de caisse sur l'appareil (M13), avec ou sans réseau : l'opération porte la session
 *  (`op_id` = son `id` : un double appui n'ouvre qu'une fois). Puis envoi aussitôt. */
export async function openOffline(db: LocalDb, session: Schemas["CashSession"]) {
  await db.transaction("rw", db.outbox, async () => {
    if (await db.outbox.where("op_id").equals(session.id).count()) return;
    await db.outbox.add({
      op_id: session.id,
      type: "cash_session.open",
      payload: {
        id: session.id,
        cash_register: session.cash_register.id,
        opened_at: session.opened_at,
      },
      created_at: session.opened_at,
      status: "pending",
      error: null,
      session,
    });
  });
  void syncNow();
}

/** Contenu de l'opération `cash_session.close` (serveur : `OfflineClosingSerializer`). */
export type OfflineClosing = {
  cash_session: string;
  counted: { currency: string; amount_minor: number }[];
  note: string;
  closed_at: string;
};

/** Sessions clôturées sur l'appareil (clôture dans la file, pas refusée) : plus montrées à la
 *  caisse, avant même la réponse du serveur. */
export function closedHere(queued: QueuedOperation[]): Set<string> {
  return new Set(
    queued
      .filter((op) => op.type === "cash_session.close" && op.status !== "rejected")
      .map((op) => (op.payload as OfflineClosing).cash_session),
  );
}

/** Clôture de caisse sur l'appareil (F8), avec ou sans réseau ; une seule par session (double
 *  appui). Le serveur recalcule l'attendu à l'arrivée. Puis envoi aussitôt. */
export async function queueClosing(db: LocalDb, closing: OfflineClosing) {
  await db.transaction("rw", db.outbox, async () => {
    if (closedHere(await db.outbox.toArray()).has(closing.cash_session)) return;
    await db.outbox.add({
      op_id: uuidv7(),
      type: "cash_session.close",
      payload: closing,
      created_at: closing.closed_at,
      status: "pending",
      error: null,
    });
  });
  void syncNow();
}

/** Sortie de caisse d'une session sur l'appareil : `pending` pas encore envoyée, `rejected`
 *  refusée par le serveur (plus déduite), `recorded` enregistrée. */
export type SessionCashOut = { out: Schemas["CashOut"]; sync: "recorded" | "pending" | "rejected" };

export function sessionCashOuts(local: LocalCash, session: string): SessionCashOut[] {
  const ops = new Map(
    local.queued.filter((op) => op.type === "cash_out.create").map((op) => [op.op_id, op]),
  );
  return local.cashOuts
    .filter((row) => row.session === session)
    .map((row) => {
      const status = ops.get(row.id)?.status;
      const sync =
        status === "pending" ? "pending" : status === "rejected" ? "rejected" : "recorded";
      return { out: row.out, sync } as const;
    })
    .sort((a, b) => a.out.paid_at.localeCompare(b.out.paid_at));
}

/** Contenu de l'opération `cash_out.create` (serveur : `OfflineCashOutSerializer`). */
export type OfflineCashOut = {
  id: string;
  expense: string;
  cash_session: string;
  number: string;
  received_by: string;
  paid_at: string;
};

/** Bon de sortie donné par l'appareil : `ITIG-P1-26-S0003` (école, appareil, année scolaire,
 *  « S » et la séquence de l'appareil), celui que le serveur vérifie. */
export function cashOutNumber(school: string, prefix: string, yearStartsOn: string, seq: number) {
  return `${school.toUpperCase()}-${prefix}-${yearStartsOn.slice(2, 4)}-S${String(seq).padStart(4, "0")}`;
}

/** Sortie de caisse sur l'appareil (FIN.2), avec ou sans réseau : bon suivant de l'appareil,
 *  sortie gardée et opération de la file dans une seule transaction. Le même `id` deux fois
 *  (double appui) rend le premier bon. Puis envoi aussitôt. */
export async function recordCashOutOffline(
  db: LocalDb,
  id: string,
  build: (seq: number) => Schemas["CashOut"],
): Promise<Schemas["CashOut"]> {
  const out = await db.transaction("rw", [db.meta, db.outbox, db.cashOuts], async () => {
    const already = await db.cashOuts.get(id);
    if (already) return already.out;
    const seq = ((await db.meta.get("sync"))?.cashOutSeq ?? 0) + 1;
    const made = build(seq);
    const payload: OfflineCashOut = {
      id,
      expense: made.expense,
      cash_session: made.cash_session,
      number: made.number,
      received_by: made.received_by,
      paid_at: made.paid_at,
    };
    await db.meta.update("sync", { cashOutSeq: seq });
    await db.outbox.add({
      op_id: id,
      type: "cash_out.create",
      payload,
      created_at: made.paid_at,
      status: "pending",
      error: null,
    });
    await db.cashOuts.add({ id, session: made.cash_session, out: made });
    return made;
  });
  void syncNow();
  return out;
}

/** Duplicata imprimé sur l'appareil (F6) : noté au journal du serveur par la file. */
export async function queueReprint(db: LocalDb, payment: string, reprintedAt: string) {
  await db.outbox.add({
    op_id: uuidv7(),
    type: "payment.reprint",
    payload: { payment, reprinted_at: reprintedAt },
    created_at: reprintedAt,
    status: "pending",
    error: null,
  });
  void syncNow();
}

/** Demande d'annulation faite sur l'appareil (F7), avec ou sans réseau : le paiement est
 *  « annulation demandée » aussitôt ; la validation, elle, se fait en ligne. */
export async function queueCancellation(db: LocalDb, payment: string, reason: string) {
  const requestedAt = new Date().toISOString();
  await db.outbox.add({
    op_id: uuidv7(),
    type: "cancellation.request",
    payload: { id: uuidv7(), payment, reason, requested_at: requestedAt },
    created_at: requestedAt,
    status: "pending",
    error: null,
  });
  void syncNow();
}

/** Crédit utilisé à la caisse sur l'appareil (3.6.2) : ses parts comptent aussitôt comme payées
 *  (`financeOf`) ; le serveur le répartit à nouveau à l'arrivée, sur ce que l'élève doit alors.
 *  Puis envoi aussitôt. */
export async function queueCreditUse(db: LocalDb, credit: Schemas["StudentCredit"], lines: Line[]) {
  const usedAt = new Date().toISOString();
  await db.outbox.add({
    op_id: uuidv7(),
    type: "credit.use",
    payload: { credit: credit.id },
    created_at: usedAt,
    status: "pending",
    error: null,
    creditUse: creditUse(credit, lines),
  });
  void syncNow();
}

/** Encaissement sur l'appareil : numéro suivant de l'appareil et opération de la file dans une
 *  seule transaction (jamais l'un sans l'autre). Le même `id` deux fois (double appui) rend le
 *  premier reçu. Puis envoi aussitôt, sans attendre. */
export async function recordOffline(
  db: LocalDb,
  id: string,
  build: (seq: number) => Receipt,
): Promise<Receipt> {
  const receipt = await db.transaction("rw", [db.meta, db.outbox], async () => {
    const already = await db.outbox.where("op_id").equals(id).first();
    if (already?.receipt) return already.receipt;
    const seq = ((await db.meta.get("sync"))?.receiptSeq ?? 0) + 1;
    const made = build(seq);
    await db.meta.update("sync", { receiptSeq: seq });
    await db.outbox.add({
      op_id: id,
      type: "payment.create",
      payload: offlinePayload(made),
      created_at: made.paid_at,
      status: "pending",
      error: null,
      receipt: made,
    });
    return made;
  });
  void syncNow();
  return receipt;
}
