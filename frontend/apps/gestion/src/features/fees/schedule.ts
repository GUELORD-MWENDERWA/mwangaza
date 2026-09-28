// Tranches proposées par l'éditeur de barème (E2) ; l'utilisateur les modifie avant d'enregistrer.
// Montants entiers découpés par `splitEvenly` : leur somme est toujours le total.
import { splitEvenly } from "@mwangaza/money";

export type Line = { label: string; amount_minor: number | null; due_on: string };

// Jour proposé pour les échéances mensuelles : l'école le change ligne par ligne.
const MONTHLY_DUE_DAY = 10;
const DEFAULT_INSTALLMENTS = 3;

function pad(n: number) {
  return String(n).padStart(2, "0");
}

/** Une ligne par mois de l'année scolaire dont l'échéance tombe entre le début et la fin :
 *  septembre à juin pour une année du 1er septembre au 2 juillet. */
export function monthlyLines(
  total: number | null,
  starts_on: string,
  ends_on: string,
  monthName: (month: number) => string,
): Line[] {
  const dues: string[] = [];
  let [year, month] = starts_on.split("-").map(Number) as [number, number];
  for (;;) {
    const due = `${year}-${pad(month)}-${pad(MONTHLY_DUE_DAY)}`;
    if (due > ends_on) break;
    if (due >= starts_on) dues.push(due);
    [year, month] = month === 12 ? [year + 1, 1] : [year, month + 1];
  }
  const amounts = total ? splitEvenly(total, dues.length) : [];
  return dues.map((due_on, index) => ({
    label: monthName(Number(due_on.slice(5, 7))),
    amount_minor: amounts[index] ?? null,
    due_on,
  }));
}

export function installmentLines(total: number | null, label: (n: number) => string): Line[] {
  const amounts = total ? splitEvenly(total, DEFAULT_INSTALLMENTS) : [];
  return Array.from({ length: DEFAULT_INSTALLMENTS }, (_, index) => ({
    label: label(index + 1),
    amount_minor: amounts[index] ?? null,
    due_on: "",
  }));
}

/** Même découpage, montants répartis de nouveau sur le total (après un changement du total). */
export function spread(lines: Line[], total: number): Line[] {
  const amounts = splitEvenly(total, lines.length);
  return lines.map((line, index) => ({ ...line, amount_minor: amounts[index] ?? null }));
}

/** Échéancier particulier d'un élève (E4) : `count` versements le même jour de chaque mois à
 *  partir de `first` (un 31 devient le dernier jour d'un mois plus court), total découpé. */
export function everyMonth(
  total: number,
  count: number,
  first: string,
  label: (n: number) => string,
): Line[] {
  const [year, month, day] = first.split("-").map(Number) as [number, number, number];
  return splitEvenly(total, count).map((amount_minor, index) => {
    const months = month - 1 + index;
    const y = year + Math.floor(months / 12);
    const m = (months % 12) + 1;
    const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return {
      label: label(index + 1),
      amount_minor,
      due_on: `${y}-${pad(m)}-${pad(Math.min(day, last))}`,
    };
  });
}
