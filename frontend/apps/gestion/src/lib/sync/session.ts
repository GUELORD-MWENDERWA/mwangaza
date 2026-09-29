import { api, call } from "@mwangaza/api";
import { liveQuery, type Subscription } from "dexie";
import { useSyncExternalStore } from "react";

import { forgetDevice, localDevice } from "../device";
import { dexieStore, LocalDb } from "./db";
import { synchronize, type SyncServer } from "./engine";

export type SyncStatus = {
  /** Appareil mémorisé qui se synchronise ; `null` : travail en ligne seulement (1.6). */
  device: string | null;
  /** Sa base : les écrans qui marchent hors ligne y lisent et y écrivent (caisse, 3.5). */
  db: LocalDb | null;
  /** Son préfixe (`P1`), dans les numéros de reçus qu'il donne. */
  prefix: string | null;
  running: boolean;
  /** Dernier essai échoué (réseau, serveur) : nouvel essai au prochain déclencheur. */
  failed: boolean;
  lastSyncAt: string | null;
  pending: number;
  rejected: number;
  /** Stockage persistant accordé par le navigateur ; `null` tant qu'on ne sait pas. */
  persisted: boolean | null;
};

const IDLE: SyncStatus = {
  device: null,
  db: null,
  prefix: null,
  running: false,
  failed: false,
  lastSyncAt: null,
  pending: 0,
  rejected: 0,
  persisted: null,
};

let status = IDLE;
const listeners = new Set<() => void>();

function setStatus(changes: Partial<SyncStatus>) {
  status = { ...status, ...changes };
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => void listeners.delete(listener);
}

/** État de la synchronisation (indicateur du haut, mise à jour de l'application). */
export function useSyncStatus(): SyncStatus {
  return useSyncExternalStore(
    subscribe,
    () => status,
    () => status,
  );
}

/** Toutes les 60 s en ligne (03 § 5.4). */
const EVERY = 60_000;

const server: SyncServer = {
  snapshot: (after) => call(api.GET("/api/sync/snapshot/", { params: { query: { after } } })),
  pull: (since) => call(api.GET("/api/sync/pull/", { params: { query: { since } } })),
  push: async (operations, receiptSeq) => {
    const body = { operations, receipt_seq: receiptSeq };
    return (await call(api.POST("/api/sync/push/", { body }))).results;
  },
};

type Session = { syncNow: () => Promise<void>; reload: () => void; stop: () => void };
let session: Session | null = null;

/** Coquille ouverte (`AppShell`) : l'appareil mémorisé du compte se synchronise à l'ouverture,
 *  au retour du réseau, toutes les 60 s et à la demande. Rend la fonction qui arrête. */
export function startSync(user: string): () => void {
  const current = openSession(user);
  session = current;
  return () => {
    current.stop();
    if (session === current) session = null;
  };
}

/** « Synchroniser maintenant » ; aussi avant d'installer une nouvelle version. */
export function syncNow(): Promise<void> {
  return session?.syncNow() ?? Promise.resolve();
}

/** Appareil enregistré ou repris après la connexion : la session repart avec lui. */
export function reloadSync() {
  session?.reload();
}

/** Demande au navigateur de ne pas effacer la base de l'appareil quand la place manque. */
export async function requestPersistence() {
  const storage = navigator.storage;
  if (!storage?.persist) return setStatus({ persisted: false });
  setStatus({ persisted: (await storage.persisted()) || (await storage.persist()) });
}

function openSession(user: string): Session {
  let stopped = false;
  let db: LocalDb | null = null;
  let counts: Subscription | null = null;
  let flight: Promise<void> | null = null;
  let again = false;

  function detach() {
    counts?.unsubscribe();
    db?.close();
    db = counts = null;
    setStatus(IDLE);
  }

  async function attach() {
    detach();
    try {
      const device = await localDevice(user);
      if (stopped || !device) return;
      db = new LocalDb(device.id);
      const local = db;
      const { lastSyncAt } = await dexieStore(local).meta();
      setStatus({ device: device.id, db: local, prefix: device.prefix, lastSyncAt });
      counts = liveQuery(() =>
        Promise.all([
          local.outbox.where("status").equals("pending").count(),
          local.outbox.where("status").equals("rejected").count(),
        ]),
      ).subscribe(([pending, rejected]) => setStatus({ pending, rejected }));
      void requestPersistence();
      await syncNow();
    } catch {
      // Pas d'IndexedDB (navigation privée stricte) : travail en ligne seulement.
      detach();
    }
  }

  async function runOnce() {
    const local = db;
    if (!local || !navigator.onLine) return;
    const store = dexieStore(local);
    setStatus({ running: true });
    try {
      const outcome = await synchronize(store, server);
      if (db !== local) return; // session repartie ou arrêtée pendant ce temps
      if (outcome === "revoked") {
        await forgetDevice(user);
        detach();
        return;
      }
      setStatus({ running: false, failed: false, lastSyncAt: (await store.meta()).lastSyncAt });
    } catch {
      if (db === local) setStatus({ running: false, failed: true });
    }
  }

  // Une seule à la fois ; demandée pendant qu'elle tourne : une de plus à la fin.
  function syncNow(): Promise<void> {
    if (flight) {
      again = true;
      return flight;
    }
    flight = (async () => {
      do {
        again = false;
        await runOnce();
      } while (again && !stopped);
    })().finally(() => {
      flight = null;
    });
    return flight;
  }

  const onOnline = () => void syncNow();
  window.addEventListener("online", onOnline);
  const timer = setInterval(onOnline, EVERY);
  void attach();

  return {
    syncNow,
    reload: () => void attach(),
    stop() {
      stopped = true;
      clearInterval(timer);
      window.removeEventListener("online", onOnline);
      detach();
    },
  };
}
