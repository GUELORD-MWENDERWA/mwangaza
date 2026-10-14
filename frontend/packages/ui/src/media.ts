import { useSyncExternalStore } from "react";

/** Écran d'ordinateur (≥ 1024 px) : mêmes seuils que les maquettes (`styles.css`, « Ordinateur »). */
export const DESKTOP = "(min-width: 1024px)";

/** La requête média est-elle vraie ? Suit les changements de taille de la fenêtre. Sans
 *  `matchMedia` (tests) : faux, la mise en page du téléphone. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia?.(query);
      list?.addEventListener("change", onChange);
      return () => list?.removeEventListener("change", onChange);
    },
    () => window.matchMedia?.(query).matches ?? false,
    () => false,
  );
}
