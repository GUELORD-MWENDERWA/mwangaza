// Feuille de notes (8.2.1) : une note a au plus une décimale, de 0 au maximum de son évaluation ;
// la note de la période est la somme des notes ramenée au maximum de la période (règle de trois),
// au dixième le plus proche, la moitié vers le haut — même règle que le serveur
// (`academics/grades.py`, `period_score`). Calculs en dixièmes entiers : aucun arrondi flottant.

/** Note tapée (« 7,5 », « 7.5 », « 8 ») → dixièmes ; `null` : case vide ; `undefined` : refusée
 *  (pas un nombre, plus d'une décimale, au-dessus du maximum). */
export function parseTenths(text: string, max: number): number | null | undefined {
  const value = text.trim().replace(",", ".");
  if (value === "") return null;
  const match = /^(\d{1,4})(?:\.(\d))?$/.exec(value);
  if (!match) return undefined;
  const tenths = Number(match[1]) * 10 + Number(match[2] ?? 0);
  return tenths > max * 10 ? undefined : tenths;
}

/** Note du serveur (« 7.5 », « 18.0 ») → dixièmes. */
export function serverTenths(score: string): number {
  return Math.round(Number(score) * 10);
}

/** Dixièmes → valeur envoyée au serveur (« 7.5 »). */
export function toScore(tenths: number): string {
  return `${Math.floor(tenths / 10)}.${tenths % 10}`;
}

/** Note de la période en dixièmes ; `null` sans évaluation ou tant qu'une case est vide. */
export function periodTenths(
  scores: (number | null)[],
  maxima: number[],
  maximum: number,
): number | null {
  if (maxima.length === 0 || scores.some((score) => score === null)) return null;
  const total = (scores as number[]).reduce((sum, score) => sum + score, 0);
  const outOf = maxima.reduce((sum, max) => sum + max, 0);
  // total × maximum / outOf, au dixième, la moitié vers le haut, en entiers.
  return Math.floor((2 * total * maximum + outOf) / (2 * outOf));
}

/** Pourcentage entier d'une note de la période. */
export function percent(tenths: number, maximum: number): number {
  return Math.floor((20 * tenths + maximum) / (2 * maximum));
}
