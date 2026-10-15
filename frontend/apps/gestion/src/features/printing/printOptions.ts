import { useCallback, useState } from "react";

import { useCurrentMe } from "../../lib/queries";

// Choix de la personne qui imprime (8.3.4) : papier, sens, exemplaires par feuille. Le serveur
// les applique ; ils sont gardés sur l'appareil, par personne et par document, avec les autres
// options de l'écran (colonnes…).
export type PrintLayout = {
  paper: "a4" | "a5";
  /** `auto` : le sens habituel du document. */
  orientation: "auto" | "portrait" | "landscape";
  perSheet: 1 | 2 | 3;
};

export const DEFAULT_LAYOUT: PrintLayout = { paper: "a4", orientation: "auto", perSheet: 1 };

/** Paramètres d'adresse du serveur ; le sens `auto` n'est pas envoyé. */
export function layoutQuery(layout: PrintLayout): Record<string, string> {
  return {
    paper: layout.paper,
    ...(layout.orientation === "auto" ? {} : { orientation: layout.orientation }),
    ...(layout.perSheet > 1 ? { per_sheet: String(layout.perSheet) } : {}),
  };
}

function read<T extends object>(key: string, defaults: T): T {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(key) ?? "null");
    if (!stored || typeof stored !== "object") return defaults;
    const merged = { ...defaults };
    // Seules les clés connues, du même type : une ancienne valeur ne casse pas l'écran.
    for (const name of Object.keys(defaults) as (keyof T)[]) {
      const value = (stored as Partial<T>)[name];
      if (typeof value === typeof defaults[name]) merged[name] = value as T[keyof T];
    }
    return merged;
  } catch {
    return defaults;
  }
}

/** Options d'un document (`document` : « class-list », « unpaid »…), retrouvées au retour sur
 *  l'écran. Sans stockage (fenêtre privée), elles valent le temps de la page. */
export function usePrintOptions<T extends object>(document: string, defaults: T) {
  const key = `mwangaza.print.${useCurrentMe().id}.${document}`;
  const [options, setState] = useState<T>(() => read(key, defaults));
  const setOptions = useCallback(
    (change: Partial<T>) =>
      setState((current) => {
        const next = { ...current, ...change };
        try {
          localStorage.setItem(key, JSON.stringify(next));
        } catch {
          // Non gardé : sans conséquence.
        }
        return next;
      }),
    [key],
  );
  return [options, setOptions] as const;
}
