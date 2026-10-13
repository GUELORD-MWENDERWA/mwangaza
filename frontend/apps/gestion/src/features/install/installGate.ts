import { isInstalled } from "@mwangaza/ui";

// Installation de la Gestion (4.24) : obligatoire pour le personnel, avec une issue de secours.
const DISMISSALS_KEY = "mwangaza.install.dismissals";
const SKIPPED_KEY = "mwangaza.install.skipped";
/** Refus de l'invite du navigateur après lesquels « Continuer dans le navigateur » apparaît. */
export const MAX_DISMISSALS = 2;
/** Sans invite du navigateur au bout de ce délai (Firefox, navigateur sans installation) : issue. */
export const NO_PROMPT_DELAY_MS = 3000;

function read(storage: Storage | undefined, key: string): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null; // Stockage refusé (navigation privée) : on se comporte comme s'il était vide.
  }
}

function write(storage: Storage | undefined, key: string, value: string) {
  try {
    storage?.setItem(key, value);
  } catch {
    // Rien à garder : l'écran reviendra à la prochaine ouverture.
  }
}

/** L'écran « Installe l'application » s'impose : application construite (pas en développement,
 *  pas dans les parcours Playwright), ouverte dans un onglet, et pas d'issue de secours prise
 *  pendant cette session du navigateur. */
export function installRequired(): boolean {
  if (!import.meta.env.PROD || isInstalled()) return false;
  return read(globalThis.sessionStorage, SKIPPED_KEY) !== "1";
}

/** « Continuer dans le navigateur » : jusqu'à la fermeture du navigateur seulement. */
export function skipInstall() {
  write(globalThis.sessionStorage, SKIPPED_KEY, "1");
}

export function dismissals(): number {
  return Number(read(globalThis.localStorage, DISMISSALS_KEY)) || 0;
}

/** Un refus de l'invite : compté sur l'appareil, il ne repart pas à zéro à chaque session. */
export function countDismissal(): number {
  const count = dismissals() + 1;
  write(globalThis.localStorage, DISMISSALS_KEY, String(count));
  return count;
}

/** L'issue de secours est visible : 2 refus, iPhone (installation à la main), ou pas d'invite. */
export function canSkip({
  dismissed,
  ios,
  waited,
}: {
  dismissed: number;
  ios: boolean;
  waited: boolean;
}): boolean {
  return dismissed >= MAX_DISMISSALS || ios || waited;
}
