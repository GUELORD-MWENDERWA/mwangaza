// Réductions (E3) : part de chaque frais dû actif, calculée comme le serveur
// (`finance.services.discount_shares`) pour montrer l'effet d'une réduction avant de l'accorder.
import { percentOf, prorate, sumAmounts } from "@mwangaza/money";

import type { Charge, Discount } from "./data";

export type DiscountRule = Pick<
  Discount,
  "fee_type" | "kind" | "percent" | "amount_minor" | "currency" | "revoked_at"
>;

const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** Frais dus actifs par type de frais et devise, dans l'ordre des échéances. */
export function chargesByFee(charges: Charge[]): Charge[][] {
  const groups = new Map<string, Charge[]>();
  for (const charge of charges) {
    if (charge.status !== "active") continue;
    const key = `${charge.fee_type} ${charge.currency}`;
    groups.set(key, [...(groups.get(key) ?? []), charge]);
  }
  return [...groups.values()].map((group) =>
    group.sort(
      (a, b) => compare(a.due_on, b.due_on) || compare(a.label, b.label) || compare(a.id, b.id),
    ),
  );
}

/** Par type de frais (et devise), les réductions qui s'y appliquent s'additionnent — % du total
 *  arrondi demi supérieur, montant dans la même devise —, plafonnées au total, puis se
 *  répartissent au prorata des échéances. Renvoie la part de chaque frais dû actif. */
export function discountShares(charges: Charge[], discounts: DiscountRule[]): Map<string, number> {
  const live = discounts.filter((discount) => !discount.revoked_at);
  const shares = new Map<string, number>();
  for (const group of chargesByFee(charges)) {
    const { fee_type, currency } = group[0]!;
    const weights = group.map((charge) => charge.amount_minor);
    const total = sumAmounts(weights);
    let reduction = 0;
    for (const discount of live) {
      if (discount.fee_type !== null && discount.fee_type !== fee_type) continue;
      if (discount.kind === "percent") reduction += percentOf(total, discount.percent ?? 0);
      else if (discount.currency === currency) reduction += discount.amount_minor ?? 0;
    }
    prorate(Math.min(reduction, total), weights).forEach((share, index) =>
      shares.set(group[index]!.id, share),
    );
  }
  return shares;
}
