// Console réelle ou démonstration (lot 5, ②bis) : chaque appel à l'API porte `X-Console-Mode`, et
// le serveur ne rend que les données de ce mode. « Réel » par défaut ; le choix est gardé sur cet
// appareil seulement (préférence d'affichage, pas une donnée).
import { api } from "@mwangaza/api";
import { useSyncExternalStore } from "react";

export type ConsoleMode = "live" | "demo";

const KEY = "mwangaza-console-mode";
const listeners = new Set<() => void>();

function stored(): ConsoleMode {
  try {
    return localStorage.getItem(KEY) === "demo" ? "demo" : "live";
  } catch {
    return "live";
  }
}

let current: ConsoleMode = stored();
let started = false;

/** Au démarrage de la console : l'en-tête part avec chaque appel. */
export function startConsoleMode(): void {
  if (started) return;
  started = true;
  api.use({
    onRequest({ request }) {
      request.headers.set("X-Console-Mode", current);
      return request;
    },
  });
}

export function setConsoleMode(mode: ConsoleMode): void {
  current = mode;
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    // Navigation privée : le mode vaut pour cet onglet seulement.
  }
  for (const listener of listeners) listener();
}

export function useConsoleMode(): ConsoleMode {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}
