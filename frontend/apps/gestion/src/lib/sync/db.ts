import type { Schemas } from "@mwangaza/api";
import Dexie, { type EntityTable } from "dexie";

import {
  EMPTY_META,
  type Config,
  type Enrollment,
  type LocalStore,
  type Operation,
  type SyncMeta,
} from "./engine";

export type LocalEnrollment = Enrollment & { gen: number };

/** Opération de la file : `pending` jusqu'à la réponse du serveur ; `sent` appliquée, gardée
 *  jusqu'à la descente suivante, qui apporte l'état du serveur où elle figure (les écrans ne la
 *  perdent jamais de vue entre les deux) ; `rejected` gardée, avec sa raison, pour être montrée
 *  (jamais effacée en silence). */
export type QueuedOperation = Operation & {
  seq?: number;
  status: "pending" | "sent" | "rejected";
  error: Schemas["Error"] | null;
  /** Encaissement : le reçu imprimé, pour l'afficher et le compter jusqu'à la descente (jamais
   *  envoyé : le serveur reçoit `payload`). */
  receipt?: Schemas["PaymentReceipt"];
  /** Ouverture de caisse : la session ouverte ici, montée à la caisse jusqu'à ce que le
   *  serveur l'accepte (elle devient alors la session gardée) ou la refuse (3.5.2). */
  session?: Schemas["CashSession"];
};

type ConfigRow = { id: "config"; value: Config };
type MetaRow = SyncMeta & { id: "sync" };
/** Session de caisse ouverte du compte, gardée à chaque lecture en ligne : la caisse continue
 *  sans réseau (3.5). `readAt` : heure de la lecture ; une lecture plus ancienne (réponse
 *  arrivée en retard, donnée en cache) ne la remplace jamais. */
export type CashRow = { id: "session"; value: Schemas["CurrentCashSession"]; readAt?: number };

/** Base d'un appareil enregistré (donc d'un compte, dans l'école de l'adresse) : l'état reçu du
 *  serveur, jamais modifié sur place, et la file des opérations faites ici (les écrans les
 *  ajoutent à l'état reçu, 3.5). Une opération et ce qui l'accompagne (numéro de reçu) s'écrivent
 *  dans une seule transaction. */
export class LocalDb extends Dexie {
  enrollments!: EntityTable<LocalEnrollment, "id">;
  config!: EntityTable<ConfigRow, "id">;
  meta!: EntityTable<MetaRow, "id">;
  outbox!: EntityTable<QueuedOperation, "seq">;
  cash!: EntityTable<CashRow, "id">;

  constructor(deviceId: string) {
    super(`mwangaza-sync-${deviceId}`);
    this.version(1).stores({
      enrollments: "id, gen",
      config: "id",
      meta: "id",
      // `seq` croissant : l'ordre d'envoi (deux UUID v7 de la même milliseconde ne sont pas
      // ordonnés).
      outbox: "++seq, &op_id, status",
    });
    this.version(2).stores({ cash: "id" });
    this.on("populate", (transaction) => {
      void transaction.table("meta").add({ ...EMPTY_META, id: "sync" });
    });
  }
}

export function dexieStore(db: LocalDb): LocalStore {
  const readMeta = async (): Promise<SyncMeta> => ({
    ...EMPTY_META,
    ...(await db.meta.get("sync")),
  });
  // La séquence des reçus ne recule jamais : un instantané lu avant un encaissement ne remet
  // pas un numéro déjà donné.
  const writeMeta = (changes: Partial<SyncMeta>) =>
    db.transaction("rw", db.meta, async () => {
      const { receiptSeq } = await readMeta();
      await db.meta.update("sync", {
        ...changes,
        ...(changes.receiptSeq !== undefined && {
          receiptSeq: Math.max(receiptSeq, changes.receiptSeq),
        }),
      });
    });

  return {
    meta: readMeta,
    setMeta: writeMeta,
    saveSnapshotPage: (page, meta) =>
      db.transaction("rw", [db.enrollments, db.config, db.meta], async () => {
        await db.enrollments.bulkPut(page.enrollments.map((item) => ({ ...item, gen: page.gen })));
        if (page.config) await db.config.put({ id: "config", value: page.config });
        if (page.last) await db.enrollments.where("gen").notEqual(page.gen).delete();
        await writeMeta(meta);
      }),
    saveChanges: (changes, meta) =>
      db.transaction("rw", [db.enrollments, db.config, db.meta], async () => {
        const { gen } = await readMeta();
        for (const change of changes) {
          if (change.entity_type === "config") {
            if (change.config) await db.config.put({ id: "config", value: change.config });
          } else if (change.operation === "delete" || !change.enrollment) {
            await db.enrollments.delete(change.entity_id);
          } else {
            await db.enrollments.put({ ...change.enrollment, gen });
          }
        }
        await writeMeta(meta);
      }),
    pending: (limit) => db.outbox.where("status").equals("pending").limit(limit).toArray(),
    settle: (outcomes) =>
      db.transaction("rw", [db.outbox, db.cash], async () => {
        for (const outcome of outcomes) {
          const operation = db.outbox.where("op_id").equals(outcome.op_id);
          const opened =
            outcome.status === "rejected" ? undefined : (await operation.first())?.session;
          if (opened) {
            // Caisse ouverte ici, acceptée : c'est maintenant la session du serveur.
            await db.cash
              .where("id")
              .equals("session")
              .modify((row) => {
                row.value = { ...row.value, session: opened };
                row.readAt = Date.now();
              });
          }
          await operation.modify(
            outcome.status === "rejected"
              ? { status: "rejected", error: outcome.error }
              : { status: "sent" },
          );
        }
      }),
    dropSent: async () => {
      await db.outbox.where("status").equals("sent").delete();
    },
    wipe: () => db.delete(),
  };
}
