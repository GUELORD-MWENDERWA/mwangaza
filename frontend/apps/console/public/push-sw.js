// Alertes sur l'écran du super-admin (S.3.2, Web Push) : le seul service worker de la console.
// Il ne garde rien en cache (la console reste toujours en ligne, jamais une vieille version) : il
// affiche l'alerte, console fermée comprise, et un clic ouvre le journal. Même message que la
// Gestion et le Portail (`id`, `title`, `body`, `url`).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data;
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title || "", {
        body: data.body || "",
        tag: data.id,
        icon: "/api/platform/icon/",
        data: { path: data.url || "/journal" },
      }),
      // Console ouverte : le journal se recharge tout de suite.
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
  const { path } = event.notification.data || {};
  const scope = self.registration.scope;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const open = clients.find((client) => client.url.startsWith(scope));
      if (open) {
        open.postMessage({ type: "open", path });
        return open.focus();
      }
      return self.clients.openWindow(new URL((path || "/").replace(/^\//, ""), scope).href);
    }),
  );
});
