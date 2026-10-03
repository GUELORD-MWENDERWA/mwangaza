// Abonnement de ce navigateur aux notifications sur l'écran (5.5, Web Push). Il faut le service
// worker de l'application (`make build`, aucun en développement) ; sur iPhone, l'application
// installée sur l'écran d'accueil. Chaque adresse d'école a son propre abonnement.
import { api, call } from "@mwangaza/api";

export type PushState = "unsupported" | "denied" | "off" | "on";

function supported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration(import.meta.env.BASE_URL);
  return (await registration?.pushManager.getSubscription()) ?? null;
}

/** Clé publique VAPID (base64url) → octets attendus par `pushManager.subscribe`. */
function keyBytes(key: string): Uint8Array<ArrayBuffer> {
  const base64 = (key + "=".repeat((4 - (key.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

async function register(subscription: PushSubscription): Promise<void> {
  const { endpoint, keys } = subscription.toJSON();
  await call(
    api.POST("/api/notifications/subscribe/", {
      body: {
        endpoint: endpoint ?? "",
        keys: { p256dh: keys?.p256dh ?? "", auth: keys?.auth ?? "" },
      },
    }),
  );
}

/** État sur cet appareil ; un abonnement déjà là est redonné au serveur (il a pu l'oublier :
 *  navigateur repris par un autre compte, abonnement expiré). */
export async function pushState(): Promise<PushState> {
  if (!supported() || !(await navigator.serviceWorker.getRegistration(import.meta.env.BASE_URL))) {
    return "unsupported";
  }
  if (Notification.permission === "denied") return "denied";
  const subscription = await currentSubscription();
  if (!subscription) return "off";
  await register(subscription).catch(() => undefined);
  return "on";
}

export async function enablePush(publicKey: string): Promise<PushState> {
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

/** Plus rien sur l'écran de cet appareil (désactivation, déconnexion d'un ordinateur partagé). */
export async function disablePush(): Promise<void> {
  if (!supported()) return;
  const subscription = await currentSubscription();
  if (!subscription) return;
  await call(
    api.POST("/api/notifications/unsubscribe/", { body: { endpoint: subscription.endpoint } }),
  ).catch(() => undefined);
  await subscription.unsubscribe();
}
