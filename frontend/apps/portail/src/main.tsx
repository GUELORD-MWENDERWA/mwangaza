import "./index.css";

import { setupI18n } from "@mwangaza/i18n";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter } from "react-router";
import { RouterProvider } from "react-router/dom";

import { listenForInstallPrompt } from "./lib/install";
import { PlatformProvider, startPlatform } from "./lib/platform";
import { createQueryClient } from "./lib/queryClient";
import { routes } from "./routes";

setupI18n();
startPlatform();
listenForInstallPrompt();
// Application installable (H6) : service worker seulement après `make build` ; une nouvelle
// version s'installe d'elle-même (rien à synchroniser dans le portail).
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  void navigator.serviceWorker.register("/sw.js", { scope: "/" });
}
const queryClient = createQueryClient();
const router = createBrowserRouter(routes);

const root = document.getElementById("root");
if (!root) throw new Error("#root introuvable");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <PlatformProvider>
        <RouterProvider router={router} />
      </PlatformProvider>
    </QueryClientProvider>
  </StrictMode>,
);
