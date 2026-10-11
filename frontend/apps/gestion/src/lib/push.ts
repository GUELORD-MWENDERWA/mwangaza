// Notifications sur l'écran de ce navigateur (5.5, `createPush`). Chaque adresse d'école a son
// service worker, donc son propre abonnement.
import { api, call } from "@mwangaza/api";
import { createPush } from "@mwangaza/ui";

export type { PushState } from "@mwangaza/ui";

export const { pushState, enablePush, disablePush } = createPush({
  base: import.meta.env.BASE_URL,
  subscribe: (body) => call(api.POST("/api/notifications/subscribe/", { body })),
  unsubscribe: (endpoint) =>
    call(api.POST("/api/notifications/unsubscribe/", { body: { endpoint } })),
});
