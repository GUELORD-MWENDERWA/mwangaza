import { isInstalled } from "@mwangaza/ui";

// L'invite d'installation, « installé ? » et l'iPhone sont communs à la Gestion : `@mwangaza/ui`.
export { isInstalled, listenForInstallPrompt, useInstallPrompt } from "@mwangaza/ui";

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
