// Répartition d'un paiement sur ce que doit l'élève (F2), comme `finance.services.allocate` du
// serveur : frais de la devise reçue d'abord, puis, avec « Convertir », ceux de l'autre devise au
// taux du paiement ; échéances les plus anciennes d'abord (ordre du serveur). Le caissier ajuste
// en cochant les frais à payer. La répartition affichée est envoyée telle quelle : le serveur la
// vérifie. Servira aussi à la caisse hors ligne (3.5).
import { convert, type Currency } from "@mwangaza/money";

import type { Charge } from "../students/data";

export type Line = { charge: Charge; received: number; amount: number };

/** « Minerval · 2e tranche » ; un frais payé en une fois porte souvent son propre nom. */
export function feeLabel(charge: Charge): string {
  return charge.label === charge.fee_type_name
    ? charge.label
    : `${charge.fee_type_name} · ${charge.label}`;
}

export type Received = { minor: number; currency: Currency };

/** Frais encore dus (actifs, pas soldés), dans l'ordre du serveur. */
export function owedCharges(charges: Charge[]): Charge[] {
  return charges.filter((charge) => charge.state && charge.remaining_minor > 0);
}

/** Plus grande part de la devise reçue dont la conversion ne dépasse pas le reste dû. */
function partFor(charge: Charge, currency: Currency, rate: string | null): number {
  const from = charge.currency as Currency;
  if (from === currency) return charge.remaining_minor;
  if (rate === null) return 0;
  let part = convert(charge.remaining_minor, from, currency, rate);
  while (part > 0 && convert(part, currency, from, rate) > charge.remaining_minor) part -= 1;
  return part;
}

/** Frais qui recevront le paiement : ceux cochés (`only`), sinon ceux de la devise reçue, plus
 * ceux de l'autre devise avec `convertOthers` ; la devise reçue d'abord. */
function candidates(
  charges: Charge[],
  currency: Currency,
  options: { convertOthers?: boolean; only?: ReadonlySet<string> },
): Charge[] {
  const owed = owedCharges(charges).filter(
    (charge) => !options.only || options.only.has(charge.id),
  );
  const same = owed.filter((charge) => charge.currency === currency);
  const others = owed.filter((charge) => charge.currency !== currency);
  return options.only || options.convertOthers ? [...same, ...others] : same;
}

/** Lignes de la répartition ; ce qui reste du montant reçu n'est affecté à rien (surplus). */
export function allocate(
  charges: Charge[],
  received: Received,
  rate: string | null,
  options: { convertOthers?: boolean; only?: ReadonlySet<string> } = {},
): Line[] {
  let left = received.minor;
  const lines: Line[] = [];
  for (const charge of candidates(charges, received.currency, options)) {
    const part = Math.min(left, partFor(charge, received.currency, rate));
    if (part <= 0) continue;
    const amount =
      charge.currency === received.currency
        ? part
        : convert(part, received.currency, charge.currency as Currency, rate!);
    lines.push({ charge, received: part, amount });
    left -= part;
  }
  return lines;
}

/** Montant qui solde tous ces frais dans la devise reçue (« Tout le retard », « Toute l'année »). */
export function payableTotal(
  charges: Charge[],
  currency: Currency,
  rate: string | null,
  convertOthers: boolean,
): number {
  const lines = allocate(charges, { minor: Number.MAX_SAFE_INTEGER, currency }, rate, {
    convertOthers,
  });
  return lines.reduce((total, line) => total + line.received, 0);
}
