import { useSyncExternalStore } from "react";

/** Invite d'installation de Chrome / Android (`beforeinstallprompt`), gardée pour le bouton
 *  « Installer » ; l'iPhone n'en a pas (3 étapes à l'écran). */
type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: InstallPromptEvent | null = null;
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
    notify();
  });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** `install()` ouvre l'invite du navigateur, s'il en a donné une ; sinon `null`. */
export function useInstallPrompt(): (() => Promise<void>) | null {
  const event = useSyncExternalStore(subscribe, () => deferred);
  if (!event) return null;
  return async () => {
    await event.prompt();
    await event.userChoice;
    deferred = null;
    notify();
  };
}

/** Ouvert depuis l'écran d'accueil du téléphone (déjà installé). */
export function isInstalled(): boolean {
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return standalone || window.matchMedia?.("(display-mode: standalone)").matches === true;
}

const LATER_KEY = "mwangaza.portal.installLater";
export const LATER_DAYS = 7;

/** « Plus tard » : le bandeau de l'accueil revient après 7 jours. */
export function installLater(now = Date.now()) {
  try {
    localStorage.setItem(LATER_KEY, String(now));
  } catch {
    // Stockage refusé (navigation privée) : le bandeau reviendra à la prochaine visite.
  }
}

/** Proposer l'installation : pas déjà installé, et pas de « Plus tard » depuis moins de 7 jours. */
export function shouldOfferInstall(now = Date.now()): boolean {
  if (isInstalled()) return false;
  try {
    const later = Number(localStorage.getItem(LATER_KEY));
    return !later || now - later >= LATER_DAYS * 24 * 60 * 60 * 1000;
  } catch {
    return true;
  }
}
