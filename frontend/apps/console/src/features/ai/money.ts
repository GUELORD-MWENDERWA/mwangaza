// L'IA compte en micro-dollars entiers (`apps/ai/prices.py`) ; l'écran montre des dollars.
import { formatAmount, parseAmount } from "@mwangaza/money";

const MICRO_PER_CENT = 10_000;

/** Micro-dollars → montant en dollars, arrondi au cent pour l'affichage seulement. */
export function formatMicro(micro: number): string {
  return formatAmount(Math.round(micro / MICRO_PER_CENT), "USD");
}

/** Saisie en dollars (« 50,00 ») → micro-dollars entiers ; `null` si illisible. */
export function parseMicro(text: string): number | null {
  const cents = parseAmount(text, "USD");
  return cents === null ? null : cents * MICRO_PER_CENT;
}

/** Valeur de départ d'un champ en dollars (sans symbole). */
export function microInput(micro: number): string {
  return (micro / 1_000_000).toFixed(2).replace(".", ",");
}
