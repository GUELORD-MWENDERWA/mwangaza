import { useSyncExternalStore } from "react";

/** Invite d'installation de Chrome / Edge / Android (`beforeinstallprompt`), gardée pour le
 *  bouton « Installer » ; l'iPhone n'en a pas (étapes à l'écran). Commune à la Gestion et au
 *  Portail. */
type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: InstallPromptEvent | null = null;
let justInstalled = false;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

/** À appeler une fois au démarrage : l'invite arrive avant que l'écran « Installer » existe. */
export function listenForInstallPrompt() {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    justInstalled = true;
    notify();
  });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** `install()` ouvre l'invite du navigateur, s'il en a donné une ; sinon `null`. Le résultat dit
 *  si l'utilisateur a accepté. */
export function useInstallPrompt(): (() => Promise<boolean>) | null {
  const event = useSyncExternalStore(subscribe, () => deferred);
  if (!event) return null;
  return async () => {
    await event.prompt();
    const { outcome } = await event.userChoice;
    deferred = null;
    notify();
    return outcome === "accepted";
  };
}

/** L'application vient d'être installée depuis cette page (événement `appinstalled`). */
export function useJustInstalled(): boolean {
  return useSyncExternalStore(subscribe, () => justInstalled);
}

/** Ouvert depuis l'écran d'accueil ou le menu des applications (déjà installé). */
export function isInstalled(): boolean {
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return standalone || window.matchMedia?.("(display-mode: standalone)").matches === true;
}

/** iPhone / iPad : pas d'invite, l'installation se fait à la main depuis Safari. */
export function isIos(): boolean {
  const { userAgent, platform, maxTouchPoints } = navigator;
  return /iPad|iPhone|iPod/.test(userAgent) || (platform === "MacIntel" && maxTouchPoints > 1);
}
