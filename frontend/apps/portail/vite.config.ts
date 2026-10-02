import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Portail familles, servi sur parents.mwangaza.school — en dev : http://localhost:5174/
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
    // données de la famille (compte, enfants) : réseau d'abord, la dernière réponse sans réseau ;
    // effacées à la déconnexion (`OFFLINE_CACHE`).
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false,
      manifest: {
        name: "Mwangaza — Parents",
        short_name: "Mwangaza",
        lang: "fr",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#F3F5F6",
        theme_color: "#2B2724",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,woff2,png,svg}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//, /^\/static\//, /^\/media\//],
        runtimeCaching: [
          {
            urlPattern: /\/api\/portal\/(me|families)\/$/,
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
