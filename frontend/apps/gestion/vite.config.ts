import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Application Gestion (personnel), servie sur {code}.<domaine>/app — en dev : http://itig.localhost:5173/app/
// L'API est servie sur la même origine grâce au proxy : les cookies de session restent valides
// et le sous-domaine de l'école ({code}.localhost) est transmis tel quel à Django.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const proxy = { target: apiTarget, changeOrigin: false };
// `^/v/` : vérification publique d'un reçu (QR code du reçu), page servie par Django.
const proxies = { "/api": proxy, "/admin": proxy, "/static": proxy, "^/v/": proxy };

const { version } = JSON.parse(readFileSync(new URL("package.json", import.meta.url), "utf8"));

export default defineConfig({
  base: "/app/",
  // Version affichée au pied du menu (celle de `package.json`).
  define: { __APP_VERSION__: JSON.stringify(version) },
  plugins: [
    react(),
    tailwindcss(),
    // Application installable ; fichiers gardés par le service worker pour démarrer sans réseau.
    // Nouvelle version proposée (« Mettre à jour »), jamais imposée (`03` § 5.4). Rien en
    // développement : le service worker n'existe qu'après `make build`.
    VitePWA({
      registerType: "prompt",
      injectRegister: false,
      // Manifeste servi par le serveur (nom et icône de la plateforme, 5.1) : `index.html`.
      manifest: false,
      workbox: {
        globPatterns: ["**/*.{js,css,html,woff2,png,svg}"],
        navigateFallback: "/app/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//, /^\/static\//, /^\/media\//],
        // Notifications sur l'écran (5.5) : réception et clic, `public/push-sw.js`.
        importScripts: ["push-sw.js"],
      },
    }),
  ],
  server: {
    host: process.env.VITE_HOST ?? "localhost",
    port: 5173,
    strictPort: true,
    allowedHosts: [".localhost"],
    proxy: proxies,
  },
  // `vite preview` (application construite, service worker compris) : même proxy.
  preview: {
    host: process.env.VITE_HOST ?? "localhost",
    port: 4173,
    strictPort: true,
    allowedHosts: [".localhost"],
    proxy: proxies,
  },
});
