// Clôture de caisse (F8, 3.8.2) calculée sur l'appareil, avec ou sans réseau : mêmes règles que
// le serveur (`finance.services.closing_summary`) ; montants en entiers, devises jamais
// additionnées. Le serveur recalcule l'attendu à l'arrivée de la clôture.
import type { Schemas } from "@mwangaza/api";
import { CURRENCIES, type Currency } from "@mwangaza/money";

import type { SessionCashOut } from "./localData";
import type { SessionPayment } from "./offline";

export type ClosingData = Omit<Schemas["CashClosingSummary"], "session" | "closing">;

/** Montant compté par devise, `null` tant qu'il n'est pas saisi. */
export type Counted = Partial<Record<string, number | null>>;

/** Résumé de la session d'après ses paiements et ses sorties de caisse sur l'appareil : attendu
 *  = reçu (pas annulé, pas refusé) − sorti (pas refusé) ; par type de frais dans la devise
 *  reçue, le trop-perçu (crédit de l'élève) à part. Les sorties faites ailleurs pendant la même
 *  session ne sont pas connues ici : le serveur les compte à l'arrivée de la clôture. */
export function closingOnDevice(
  rows: SessionPayment[],
  enabled: string[],
  cashOuts: SessionCashOut[] = [],
): ClosingData {
  const outs = cashOuts.filter((row) => row.sync !== "rejected").map((row) => row.out);
  const kept = rows.filter((row) => row.sync !== "rejected").map((row) => row.payment);
  const counting = kept.filter((payment) => !payment.cancelled);
  const total = (items: typeof kept, currency: Currency) => {
    const mine = items.filter((payment) => payment.received_currency === currency);
    const amount_minor = mine.reduce((sum, payment) => sum + payment.received_amount_minor, 0);
    return { currency, amount_minor, count: mine.length };
  };
  const used = (items: typeof kept) =>
    CURRENCIES.filter((c) => items.some((payment) => payment.received_currency === c));

  const fees = new Map<string, ClosingData["fee_types"][number]>();
  for (const payment of counting) {
    const currency = payment.received_currency;
    for (const line of payment.allocations) {
      const key = `${line.fee_type_name}\u0000${currency}`;
      const row = fees.get(key) ?? { fee_type: line.fee_type_name, currency, amount_minor: 0 };
      row.amount_minor += line.received_minor;
      fees.set(key, row);
    }
  }
  const feeTypes = [...fees.values()].sort((a, b) => a.fee_type!.localeCompare(b.fee_type!));
  const currencies = CURRENCIES.filter(
    (c) => enabled.includes(c) || used(counting).includes(c) || outs.some((o) => o.currency === c),
  ).map((c) => {
    const { amount_minor, count } = total(counting, c);
    const mine = outs.filter((out) => out.currency === c);
    const paidOut = mine.reduce((sum, out) => sum + out.amount_minor, 0);
    return {
      currency: c,
      received_minor: amount_minor,
      paid_out_minor: paidOut,
      expected_minor: amount_minor - paidOut,
      count,
      cash_outs_count: mine.length,
    };
  });
  for (const { currency, received_minor } of currencies) {
    const allocated = feeTypes
      .filter((row) => row.currency === currency)
      .reduce((sum, row) => sum + row.amount_minor, 0);
    if (received_minor > allocated)
      feeTypes.push({ fee_type: null, currency, amount_minor: received_minor - allocated });
  }
  const receipts = [...kept]
    .sort((a, b) => a.paid_at.localeCompare(b.paid_at))
    .map((payment) => payment.receipt_number);
  const cancelled = kept.filter((payment) => payment.cancelled);
  return {
    currencies,
    fee_types: feeTypes,
    payments_count: kept.length,
    first_receipt: receipts[0] ?? null,
    last_receipt: receipts.at(-1) ?? null,
    cancelled: used(cancelled).map((c) => total(cancelled, c)),
    cancellations_pending: counting.filter((payment) => payment.cancellation_pending).length,
    cash_outs: outs.map((out) => ({
      id: out.id,
      number: out.number,
      expense_number: out.expense_number,
      beneficiary: out.beneficiary,
      received_by: out.received_by,
      amount_minor: out.amount_minor,
      currency: out.currency,
      paid_at: out.paid_at,
    })),
  };
}

/** Écart par devise (compté − attendu), `null` tant que le compté manque. */
export function differences(data: ClosingData, counted: Counted) {
  return data.currencies.map(({ currency, expected_minor }) => {
    const got = counted[currency];
    return {
      currency,
      expected_minor,
      counted_minor: got ?? null,
      difference_minor: got == null ? null : got - expected_minor,
    };
  });
}
