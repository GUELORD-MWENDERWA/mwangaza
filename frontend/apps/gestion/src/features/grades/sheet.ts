import type { Sheet } from "./data";

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

/** Ce qu'un enregistrement change dans la feuille (corps de `PUT …/grades/`). */
export type SaveBody = {
  evaluations: { id: string; name: string; max_score: number }[];
  removed_evaluations: string[];
  grades: { enrollment_id: string; evaluation_id: string; score: string | null }[];
  reason: string;
};

/** La feuille après `body`, comme le serveur la rendrait : sert à la montrer sur l'appareil tant
 *  que l'enregistrement fait hors ligne n'est pas parti (8.2.3). */
export function applySave(sheet: Sheet, body: SaveBody): Sheet {
  const evaluations = body.evaluations.filter(
    (item) => !body.removed_evaluations.includes(item.id),
  );
  const changes = new Map(
    body.grades.map((g) => [`${g.enrollment_id}|${g.evaluation_id}`, g.score]),
  );
  const students = sheet.students.map((row) => {
    const scores = new Map(row.scores.map((cell) => [cell.evaluation_id, cell.score]));
    for (const item of evaluations) {
      const key = `${row.enrollment_id}|${item.id}`;
      if (!changes.has(key)) continue;
      const score = changes.get(key);
      if (score === null || score === undefined) scores.delete(item.id);
      else scores.set(item.id, score);
    }
    const kept = evaluations.filter((item) => scores.has(item.id));
    const total = periodTenths(
      evaluations.map((item) => (scores.has(item.id) ? serverTenths(scores.get(item.id)!) : null)),
      evaluations.map((item) => item.max_score),
      sheet.maximum,
    );
    return {
      ...row,
      scores: kept.map((item) => ({ evaluation_id: item.id, score: scores.get(item.id)! })),
      total: total === null ? null : (total / 10).toFixed(1),
    };
  });
  return { ...sheet, evaluations, students };
}
