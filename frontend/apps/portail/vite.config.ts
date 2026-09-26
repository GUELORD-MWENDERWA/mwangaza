import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Portail familles, servi sur parents.mwangaza.school — en dev : http://localhost:5174/
// L'API est servie sur la même origine grâce au proxy : les cookies de session restent valides
// et le sous-domaine de l'école ({code}.localhost) est transmis tel quel à Django.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const proxy = { target: apiTarget, changeOrigin: false };

export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    host: process.env.VITE_HOST ?? "localhost",
    port: 5174,
    strictPort: true,
    allowedHosts: [".localhost"],
    proxy: { "/api": proxy, "/admin": proxy, "/static": proxy },
  },
});
