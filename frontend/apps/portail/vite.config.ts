import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Portail familles, servi sur parents.<domaine> — en dev : http://localhost:5174/
// L'API est servie sur la même origine grâce au proxy : les cookies de session restent valides
// et le sous-domaine de l'école ({code}.localhost) est transmis tel quel à Django.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const proxy = { target: apiTarget, changeOrigin: false };

export default defineConfig({
  base: "/",
  plugins: [
    react(),
    tailwindcss(),
    // Installable (H6) ; première visite légère, les suivantes servies depuis le cache. Les
    // données de la famille (compte, enfants, paiements d'un enfant) : réseau d'abord, la
    // dernière réponse sans réseau ; effacées à la déconnexion (`OFFLINE_CACHE`).
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false,
      // Manifeste servi par le serveur (nom et icône de la plateforme, 5.1) : `index.html`.
      manifest: false,
      workbox: {
        globPatterns: ["**/*.{js,css,html,woff2,png,svg}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//, /^\/static\//, /^\/media\//],
        // Notifications sur l'écran (5.5.2) : `public/push-sw.js`, le même que la Gestion.
        importScripts: ["push-sw.js"],
        runtimeCaching: [
          {
            urlPattern:
              /\/api\/portal\/(me|families|children\/[0-9a-f-]+|announcements|calendar|summons)\/$/,
            handler: "NetworkFirst",
            options: { cacheName: "portal-data", networkTimeoutSeconds: 10 },
          },
        ],
      },
    }),
  ],
  server: {
    host: process.env.VITE_HOST ?? "localhost",
    port: 5174,
    strictPort: true,
    allowedHosts: [".localhost"],
    proxy: { "/api": proxy, "/admin": proxy, "/static": proxy },
  },
});
