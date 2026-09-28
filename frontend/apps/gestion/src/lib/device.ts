import { api, ApiError, call } from "@mwangaza/api";

/** « Se souvenir de cet appareil » (3.3.1) : l'appareil enregistré d'un compte, gardé dans ce
 *  navigateur. La base IndexedDB appartient à l'adresse, donc à l'école ; un poste partagé garde
 *  un appareil par compte. La clé privée, non exportable, signera les reçus émis hors ligne. */
export type LocalDevice = { user: string; id: string; prefix: string; privateKey: CryptoKey };

export interface DeviceStore {
  get(user: string): Promise<LocalDevice | undefined>;
  put(device: LocalDevice): Promise<void>;
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
  { store, server, createKeys, userAgent }: Deps = browserDeps(),
): Promise<void> {
  const local = await store.get(user);
  if (local) {
    if (await server.resume(local.id)) return;
    await store.delete(user);
  }
  if (!remember) return;
  const keys = await createKeys();
  const device = await server.register(deviceLabel(userAgent), keys.publicKey);
  await store.put({ user, id: device.id, prefix: device.prefix, privateKey: keys.privateKey });
}

type Deps = {
  store: DeviceStore;
  server: DeviceServer;
  createKeys: () => Promise<Keys>;
  userAgent: string;
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

async function run<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>) {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = db.transaction(STORE, mode);
      const request = action(transaction.objectStore(STORE));
      transaction.oncomplete = () => resolve(request.result);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally {
    db.close();
  }
}

/** L'appareil mémorisé du compte dans ce navigateur (synchronisation, 3.4). */
export const localDevice = (user: string) => browserStore.get(user);

/** Appareil déconnecté par l'école : oublié ici (sa base est effacée par la synchronisation). */
export const forgetDevice = (user: string) => browserStore.delete(user);

const browserStore: DeviceStore = {
  get: (user) => run<LocalDevice | undefined>("readonly", (store) => store.get(user)),
  put: async (device) => {
    await run("readwrite", (store) => store.put(device));
  },
  delete: async (user) => {
    await run("readwrite", (store) => store.delete(user));
  },
};
