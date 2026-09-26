import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Application Gestion (personnel), servie sur {code}.mwangaza.school/app — en dev : http://itig.localhost:5173/app/
// L'API est servie sur la même origine grâce au proxy : les cookies de session restent valides
// et le sous-domaine de l'école ({code}.localhost) est transmis tel quel à Django.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const proxy = { target: apiTarget, changeOrigin: false };

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    host: process.env.VITE_HOST ?? "localhost",
    port: 5173,
    strictPort: true,
    allowedHosts: [".localhost"],
    proxy: { "/api": proxy, "/admin": proxy, "/static": proxy },
  },
});
