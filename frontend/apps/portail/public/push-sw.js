// Notifications sur l'écran (5.5, Web Push), chargé par le service worker de l'application
// (`workbox.importScripts`) : affichées même application fermée. Un clic ramène l'application
// ouverte sur l'écran lié (sans recharger : une saisie en cours n'est pas perdue), sinon l'ouvre.
self.addEventListener("push", (event) => {
  let data;
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const path = data.url || "/notifications";
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title || "", {
        body: data.body || "",
        tag: data.id,
        icon: "/api/platform/icon/?app=portail",
        data: { id: data.id, path },
      }),
      // Application ouverte : la cloche se met à jour tout de suite.
      self.clients
        .matchAll({ type: "window" })
        .then((clients) =>
          clients.forEach((client) => client.postMessage({ type: "notification" })),
        ),
    ]),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const { id, path } = event.notification.data || {};
  const scope = self.registration.scope;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const open = clients.find((client) => client.url.startsWith(scope));
      if (open) {
        open.postMessage({ type: "open", id, path });
        return open.focus();
      }
      return self.clients.openWindow(new URL((path || "/").replace(/^\//, ""), scope).href);
    }),
  );
});
