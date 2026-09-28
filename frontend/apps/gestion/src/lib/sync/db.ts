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

/** Opération de la file : `pending` jusqu'à la réponse du serveur ; `rejected` gardée, avec sa
 *  raison, pour être montrée (jamais effacée en silence). */
export type QueuedOperation = Operation & {
  seq?: number;
  status: "pending" | "rejected";
  error: Schemas["Error"] | null;
};

type ConfigRow = { id: "config"; value: Config };
type MetaRow = SyncMeta & { id: "sync" };

/** Base d'un appareil enregistré (donc d'un compte, dans l'école de l'adresse) : l'état reçu du
 *  serveur, jamais modifié sur place, et la file des opérations faites ici (les écrans les
 *  ajoutent à l'état reçu, 3.5). Une opération et ce qui l'accompagne (numéro de reçu) s'écrivent
 *  dans une seule transaction. */
export class LocalDb extends Dexie {
  enrollments!: EntityTable<LocalEnrollment, "id">;
  config!: EntityTable<ConfigRow, "id">;
  meta!: EntityTable<MetaRow, "id">;
  outbox!: EntityTable<QueuedOperation, "seq">;

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
  const writeMeta = async (changes: Partial<SyncMeta>) => {
    await db.meta.update("sync", changes);
  };
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
      db.transaction("rw", db.outbox, async () => {
        for (const outcome of outcomes) {
          const operation = db.outbox.where("op_id").equals(outcome.op_id);
          if (outcome.status === "rejected") {
            await operation.modify({ status: "rejected", error: outcome.error });
          } else {
            await operation.delete();
          }
        }
      }),
    wipe: () => db.delete(),
  };
}
