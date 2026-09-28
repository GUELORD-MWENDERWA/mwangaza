import { ApiError, type Schemas } from "@mwangaza/api";

// Synchronisation hors ligne (03 § 5, 3.4) : envoyer la file d'opérations de l'appareil, puis
// descendre l'état du serveur (instantané la première fois, ensuite les changements). Écrit sur
// des interfaces (`LocalStore`, `SyncServer`) : la base Dexie et l'API sont dans `db.ts` et
// `session.ts`.

export type Enrollment = Schemas["SyncEnrollment"];
export type Config = Schemas["SyncConfig"];
export type Change = Schemas["Change"];
export type Outcome = Schemas["Outcome"];

/** Opération faite sur l'appareil (ex. `payment.create`, 3.5), envoyée telle quelle. */
export type Operation = {
  op_id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

/** Instantané commencé : repris à la page suivante après une coupure. */
export type SnapshotProgress = { gen: number; cursor: number; after: string };

export type SyncMeta = {
  /** `since` du prochain `pull` ; `null` : aucun instantané complet. */
  cursor: number | null;
  snapshot: SnapshotProgress | null;
  /** Génération de l'instantané en service : un nouvel instantané retire les autres à la fin. */
  gen: number;
  /** Dernier numéro de reçu donné par l'appareil (3.5). */
  receiptSeq: number;
  lastSyncAt: string | null;
};

export const EMPTY_META: SyncMeta = {
  cursor: null,
  snapshot: null,
  gen: 0,
  receiptSeq: 0,
  lastSyncAt: null,
};

export interface LocalStore {
  meta(): Promise<SyncMeta>;
  setMeta(changes: Partial<SyncMeta>): Promise<void>;
  /** Une page d'instantané et l'avancement, ensemble ; la dernière (`last`) retire les
   *  inscriptions des générations précédentes. */
  saveSnapshotPage(
    page: { gen: number; enrollments: Enrollment[]; config: Config | null; last: boolean },
    meta: Partial<SyncMeta>,
  ): Promise<void>;
  /** Changements descendus et nouveau curseur, ensemble. */
  saveChanges(changes: Change[], meta: Partial<SyncMeta>): Promise<void>;
  /** Opérations pas encore envoyées, les plus anciennes d'abord. */
  pending(limit: number): Promise<Operation[]>;
  /** Réponse du serveur : appliquées (ou déjà appliquées) retirées de la file, refusées gardées
   *  avec leur raison pour être montrées. */
  settle(outcomes: Outcome[]): Promise<void>;
  /** Appareil déconnecté par l'école : tout effacer. */
  wipe(): Promise<void>;
}

export interface SyncServer {
  snapshot(after?: string): Promise<Schemas["Snapshot"]>;
  pull(since: number): Promise<Schemas["Pull"]>;
  push(operations: Operation[], receiptSeq: number): Promise<Outcome[]>;
}

/** Nombre d'opérations par envoi (limite du serveur). */
const BATCH = 100;

/** Une synchronisation : envoyer, puis descendre. Une erreur (réseau, serveur) laisse tout en
 *  place pour le prochain essai ; `revoked` : l'appareil a été déconnecté, ses données effacées. */
export async function synchronize(
  store: LocalStore,
  server: SyncServer,
  now = () => new Date(),
): Promise<"done" | "revoked"> {
  try {
    await pushPending(store, server);
    const meta = await store.meta();
    if (meta.snapshot || meta.cursor === null || !(await pullChanges(store, server, meta))) {
      await takeSnapshot(store, server, meta);
    }
    await store.setMeta({ lastSyncAt: now().toISOString() });
    return "done";
  } catch (error) {
    if (isError(error, "device_revoked")) {
      await store.wipe();
      return "revoked";
    }
    throw error;
  }
}

async function pushPending(store: LocalStore, server: SyncServer) {
  for (;;) {
    const operations = await store.pending(BATCH);
    if (operations.length === 0) return;
    const { receiptSeq } = await store.meta();
    await store.settle(
      await server.push(
        operations.map(({ op_id, type, payload, created_at }) => ({
          op_id,
          type,
          payload,
          created_at,
        })),
        receiptSeq,
      ),
    );
    if (operations.length < BATCH) return;
  }
}

/** Instantané par pages, repris où il s'est arrêté. Le curseur est celui de la première page :
 *  `pull` renverra ce qui a changé pendant le chargement des suivantes. */
async function takeSnapshot(store: LocalStore, server: SyncServer, meta: SyncMeta) {
  let progress = meta.snapshot;
  for (;;) {
    const page = await server.snapshot(progress?.after);
    const gen = progress?.gen ?? meta.gen + 1;
    const cursor = progress?.cursor ?? page.cursor ?? 0;
    // Appareil réinstallé : ne pas redonner un numéro de reçu que le serveur connaît déjà.
    const receipt = page.device
      ? { receiptSeq: Math.max(meta.receiptSeq, page.device.last_receipt_seq) }
      : {};
    const last = page.next === null;
    progress = last ? null : { gen, cursor, after: page.next! };
    await store.saveSnapshotPage(
      { gen, enrollments: page.enrollments, config: page.config, last },
      last ? { ...receipt, gen, cursor, snapshot: null } : { ...receipt, snapshot: progress },
    );
    if (last) return;
  }
}

/** Changements depuis le curseur ; `false` : le serveur demande un nouvel instantané (base
 *  restaurée). */
async function pullChanges(store: LocalStore, server: SyncServer, meta: SyncMeta) {
  let since = meta.cursor!;
  for (;;) {
    let page: Schemas["Pull"];
    try {
      page = await server.pull(since);
    } catch (error) {
      if (isError(error, "snapshot_required")) return false;
      throw error;
    }
    await store.saveChanges(page.changes, { cursor: page.cursor });
    if (!page.has_more) return true;
    since = page.cursor;
  }
}

function isError(error: unknown, code: string) {
  return error instanceof ApiError && error.code === code;
}
