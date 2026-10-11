// Abonnement de ce navigateur aux notifications sur l'écran (5.5, Web Push), commun à la Gestion
// et au Portail. Il faut le service worker de l'application (`make build`, aucun en
// développement) ; sur iPhone, l'application installée sur l'écran d'accueil.

export type PushState = "unsupported" | "denied" | "off" | "on";

/** Abonnement tel que le serveur l'attend (`PushSubscription.toJSON()`). */
export type PushKeys = { endpoint: string; keys: { p256dh: string; auth: string } };

function supported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** Clé publique VAPID (base64url) → octets attendus par `pushManager.subscribe`. */
function keyBytes(key: string): Uint8Array<ArrayBuffer> {
  const base64 = (key + "=".repeat((4 - (key.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

/** `base` : adresse du service worker de l'application (`import.meta.env.BASE_URL`) ;
 *  `subscribe` et `unsubscribe` : ses appels au serveur. */
export function createPush(server: {
  base: string;
  subscribe: (subscription: PushKeys) => Promise<unknown>;
  unsubscribe: (endpoint: string) => Promise<unknown>;
}) {
  async function currentSubscription(): Promise<PushSubscription | null> {
    const registration = await navigator.serviceWorker.getRegistration(server.base);
    return (await registration?.pushManager.getSubscription()) ?? null;
  }

  async function register(subscription: PushSubscription): Promise<void> {
    const { endpoint, keys } = subscription.toJSON();
    await server.subscribe({
      endpoint: endpoint ?? "",
      keys: { p256dh: keys?.p256dh ?? "", auth: keys?.auth ?? "" },
    });
  }

  /** État sur cet appareil ; un abonnement déjà là est redonné au serveur (il a pu l'oublier :
   *  navigateur repris par un autre compte, abonnement expiré). */
  async function pushState(): Promise<PushState> {
    if (!supported() || !(await navigator.serviceWorker.getRegistration(server.base))) {
      return "unsupported";
    }
    if (Notification.permission === "denied") return "denied";
    const subscription = await currentSubscription();
    if (!subscription) return "off";
    await register(subscription).catch(() => undefined);
    return "on";
  }

  async function enablePush(publicKey: string): Promise<PushState> {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return permission === "denied" ? "denied" : "off";
    const registration = await navigator.serviceWorker.ready;
    const subscription =
      (await registration.pushManager.getSubscription()) ??
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(publicKey),
      }));
    await register(subscription);
    return "on";
  }

  /** Plus rien sur l'écran de cet appareil (désactivation, déconnexion d'un appareil partagé). */
  async function disablePush(): Promise<void> {
    if (!supported()) return;
    const subscription = await currentSubscription();
    if (!subscription) return;
    await server.unsubscribe(subscription.endpoint).catch(() => undefined);
    await subscription.unsubscribe();
  }

  return { pushState, enablePush, disablePush };
}
