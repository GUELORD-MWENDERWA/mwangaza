// Notifications sur l'écran de ce téléphone (5.5.2, `createPush`) : un seul abonnement pour le
// portail, qui n'a qu'une adresse, quelles que soient les écoles du parent.
import { api, call } from "@mwangaza/api";
import { createPush } from "@mwangaza/ui";

export type { PushState } from "@mwangaza/ui";

export const { pushState, enablePush, disablePush } = createPush({
  base: import.meta.env.BASE_URL,
  subscribe: (body) => call(api.POST("/api/portal/notifications/subscribe/", { body })),
  unsubscribe: (endpoint) =>
    call(api.POST("/api/portal/notifications/unsubscribe/", { body: { endpoint } })),
});
