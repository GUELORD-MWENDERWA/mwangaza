import { api, ApiError, call } from "@mwangaza/api";

import type { PinHash } from "./pin";
import type { Me, School } from "./queries";

/** « Se souvenir de cet appareil » (3.3.1) : l'appareil enregistré d'un compte, gardé dans ce
 *  navigateur. La base IndexedDB appartient à l'adresse, donc à l'école ; un poste partagé garde
 *  un appareil par compte. La clé privée, non exportable, signera les reçus émis hors ligne. */
export type LocalDevice = {
  user: string;
  id: string;
  prefix: string;
  privateKey: CryptoKey;
  /** Dernière connexion complète (mot de passe) ici ; effacée par « Se déconnecter » (B5). */
  loggedInAt?: number | null;
  /** Code PIN de déverrouillage, propre à cet appareil (3.7.1). */
  pin?: PinHash;
  pinFailures?: number;
  /** Compte et école lus en ligne : l'application démarre sans réseau avec eux. */
  me?: Me;
  school?: School;
  /** Dernière ouverture : le compte proposé en premier au déverrouillage. */
  seenAt?: number;
};

export interface DeviceStore {
  get(user: string): Promise<LocalDevice | undefined>;
  all(): Promise<LocalDevice[]>;
  put(device: LocalDevice): Promise<void>;
  /** Modifie l'appareil du compte, s'il y en a un, dans une seule transaction. */
  update(user: string, changes: Partial<LocalDevice>): Promise<void>;
  delete(user: string): Promise<void>;
}

export interface DeviceServer {
  /** `false` : appareil déconnecté ou inconnu du serveur. */
  resume(id: string): Promise<boolean>;
  register(label: string, publicKey: string): Promise<{ id: string; prefix: string }>;
}

type Keys = { privateKey: CryptoKey; publicKey: string };

/** Après la connexion : l'appareil déjà enregistré reprend la session ; sinon, si la case est
 *  cochée, un nouvel appareil est enregistré. Un appareil déconnecté est oublié ici. */
export async function attachDevice(
  user: string,
  remember: boolean,
  { store, server, createKeys, userAgent, now }: Deps = browserDeps(),
): Promise<void> {
  // Connexion complète : le PIN remarche (5 codes faux, 7 jours, déconnexion).
  const loggedIn = { loggedInAt: now(), pinFailures: 0 };
  const local = await store.get(user);
  if (local) {
    if (await server.resume(local.id)) return store.update(user, loggedIn);
    await store.delete(user);
  }
  if (!remember) return;
  const keys = await createKeys();
  const device = await server.register(deviceLabel(userAgent), keys.publicKey);
  await store.put({
    user,
    id: device.id,
    prefix: device.prefix,
    privateKey: keys.privateKey,
    ...loggedIn,
  });
}

type Deps = {
  store: DeviceStore;
  server: DeviceServer;
  createKeys: () => Promise<Keys>;
  userAgent: string;
  now: () => number;
};

/** Nom proposé pour l'appareil : système et navigateur (« Windows · Edge »). */
export function deviceLabel(userAgent: string): string {
  const system = SYSTEMS.find(([pattern]) => pattern.test(userAgent))?.[1];
  const browser = BROWSERS.find(([pattern]) => pattern.test(userAgent))?.[1];
  return [system, browser].filter(Boolean).join(" · ") || "Web";
}

// Dans cet ordre : Edge et Opera se disent aussi Chrome, Chrome se dit aussi Safari, Android
// se dit aussi Linux.
const SYSTEMS: [RegExp, string][] = [
  [/Windows/, "Windows"],
  [/Android/, "Android"],
  [/iPhone|iPad/, "iOS"],
  [/CrOS/, "ChromeOS"],
  [/Mac OS X/, "macOS"],
  [/Linux/, "Linux"],
];
const BROWSERS: [RegExp, string][] = [
  [/Edg\//, "Edge"],
  [/OPR\//, "Opera"],
  [/Firefox\//, "Firefox"],
  [/Chrome\//, "Chrome"],
  [/Safari\//, "Safari"],
];

const REMEMBER_KEY = "mwangaza.rememberDevice";

/** Choix de la case, gardé le temps des étapes de la connexion. */
export function setRememberDevice(remember: boolean) {
  try {
    sessionStorage.setItem(REMEMBER_KEY, remember ? "1" : "0");
  } catch {
    // Stockage refusé : la case vaut « non ».
  }
}

export function takeRememberDevice(): boolean {
  try {
    const value = sessionStorage.getItem(REMEMBER_KEY);
    sessionStorage.removeItem(REMEMBER_KEY);
    return value === "1";
  } catch {
    return false;
  }
}

function browserDeps(): Deps {
  return {
    store: browserStore,
    server: {
      async resume(id) {
        try {
          await call(api.POST("/api/me/devices/{id}/resume/", { params: { path: { id } } }));
          return true;
        } catch (error) {
          if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
            return false;
          }
          throw error;
        }
      },
      register: (label, publicKey) =>
        call(api.POST("/api/me/devices/", { body: { label, public_key: publicKey } })),
    },
    createKeys: async () => {
      const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, false, [
        "sign",
        "verify",
      ]);
      const spki = new Uint8Array(await crypto.subtle.exportKey("spki", pair.publicKey));
      return { privateKey: pair.privateKey, publicKey: btoa(String.fromCharCode(...spki)) };
    },
    userAgent: navigator.userAgent,
    now: Date.now,
  };
}

const DB_NAME = "mwangaza-device";
const STORE = "devices";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "user" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function run<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T> | void,
) {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = db.transaction(STORE, mode);
      const request = action(transaction.objectStore(STORE));
      transaction.oncomplete = () => resolve(request?.result as T);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally {
    db.close();
  }
}

/** L'appareil mémorisé du compte dans ce navigateur (synchronisation, 3.4). */
export const localDevice = (user: string) => browserStore.get(user);

/** Les comptes mémorisés dans ce navigateur (déverrouillage sans réseau, 3.7.1). */
export const allDevices = () => browserStore.all();

/** Compte et école lus en ligne, gardés sur l'appareil du compte pour démarrer sans réseau. */
export async function keepForOfflineStart(me: Me, school: School) {
  if (me.support || !me.school) return;
  await browserStore.update(me.id, { me, school, seenAt: Date.now() });
}

/** Appareil déconnecté par l'école : oublié ici (sa base est effacée par la synchronisation). */
export const forgetDevice = (user: string) => browserStore.delete(user);

export const browserStore: DeviceStore = {
  get: (user) => run<LocalDevice | undefined>("readonly", (store) => store.get(user)),
  all: () => run<LocalDevice[]>("readonly", (store) => store.getAll()),
  put: async (device) => {
    await run("readwrite", (store) => store.put(device));
  },
  update: async (user, changes) => {
    await run("readwrite", (store) => {
      const request = store.get(user);
      request.onsuccess = () => {
        if (request.result) store.put({ ...request.result, ...changes });
      };
    });
  },
  delete: async (user) => {
    await run("readwrite", (store) => store.delete(user));
  },
};
