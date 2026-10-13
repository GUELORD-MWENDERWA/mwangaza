import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Console de la plateforme (super-admin, 5.2), servie sur admin.<domaine> — en dev :
// http://admin.localhost:5175/. Toujours en ligne : pas de cache ; son seul service worker,
// `public/push-sw.js`, affiche les alertes du super-admin (S.3.2). L'API et
// l'administration de dépannage sont sur la même origine grâce au proxy (même session) ; l'hôte
// `admin.localhost` arrive tel quel à Django, qui y reconnaît la console.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const proxy = { target: apiTarget, changeOrigin: false };

export default defineConfig({
  base: "/",
  plugins: [react(), tailwindcss()],
  server: {
    host: process.env.VITE_HOST ?? "localhost",
    port: 5175,
    strictPort: true,
    allowedHosts: [".localhost"],
    proxy: { "/api": proxy, "/admin": proxy, "/static": proxy },
  },
});
