// Alertes sur l'écran de ce navigateur (S.3.2, `createPush`) : usage d'un compte super-admin,
// session support ouverte. Le service worker de la console ne sert qu'à cela
// (`public/push-sw.js`, aucun cache) ; l'abonnement reste après la déconnexion.
import { api, call } from "@mwangaza/api";
import { createPush } from "@mwangaza/ui";

export type { PushState } from "@mwangaza/ui";

const push = createPush({
  base: "/",
  subscribe: (body) => call(api.POST("/api/console/alerts/subscribe/", { body })),
  unsubscribe: (endpoint) =>
    call(api.POST("/api/console/alerts/unsubscribe/", { body: { endpoint } })),
});

export const { enablePush, disablePush } = push;

let worker: Promise<unknown> = Promise.resolve();

/** Au démarrage de la console : installe le service worker des alertes. */
export function startAlerts(): void {
  if (!("serviceWorker" in navigator)) return;
  worker = navigator.serviceWorker.register("/push-sw.js").catch(() => undefined);
}

/** État sur cet appareil, une fois le service worker installé (première visite comprise). */
export async function pushState() {
  await worker;
  return push.pushState();
}
