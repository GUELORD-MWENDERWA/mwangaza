// Montants en entiers dans la plus petite unité (centimes USD, francs CDF) + devise : saisie,
// somme, découpage, affichage (skill `argent`, formats de la skill `design`). Jamais de nombre à
// virgule : une saisie est lue chiffre par chiffre, les calculs se font sur des entiers.

export type Currency = "USD" | "CDF";

export const CURRENCIES: Currency[] = ["USD", "CDF"];

/** Décimales de la plus petite unité utilisée : centime pour USD, franc pour CDF. */
export const DECIMALS: Record<Currency, number> = { USD: 2, CDF: 0 };

const SYMBOLS: Record<Currency, string> = { USD: "$", CDF: "FC" };
// Espace insécable : un montant ne se coupe jamais en fin de ligne.
const NBSP = " ";
// Au-delà, c'est une erreur de saisie (et on reste loin de la limite des entiers exacts).
const MAX_DIGITS = 13;

export function currencySymbol(currency: Currency): string {
  return SYMBOLS[currency];
}

function group(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

function assertInteger(minor: number) {
  if (!Number.isSafeInteger(minor)) throw new TypeError(`Montant non entier : ${minor}`);
}

/** `12000, "USD"` → `120,00`, `1260000, "CDF"` → `1 260 000` (sans symbole : champ de saisie). */
export function formatAmountValue(minor: number, currency: Currency): string {
  assertInteger(minor);
  const decimals = DECIMALS[currency];
  const digits = String(Math.abs(minor)).padStart(decimals + 1, "0");
  const whole = group(digits.slice(0, digits.length - decimals));
  const sign = minor < 0 ? "−" : "";
  return decimals ? `${sign}${whole},${digits.slice(digits.length - decimals)}` : sign + whole;
}

/** `123456, "USD"` → `1 234,56 $` ; `1260000, "CDF"` → `1 260 000 FC`. */
export function formatAmount(minor: number, currency: Currency): string {
  return `${formatAmountValue(minor, currency)}${NBSP}${SYMBOLS[currency]}`;
}

/** Saisie → plus petite unité : `"150,00"` ou `"150.5"` → `15050` (USD) ; espaces permis
 * entre les milliers. `null` : saisie vide, négative, ou avec plus de décimales que la devise
 * (`"12,5"` en FC). */
export function parseAmount(text: string, currency: Currency): number | null {
  const match = /^(\d+)(?:[.,](\d*))?$/.exec(text.replace(/\s/g, ""));
  if (!match) return null;
  const [, whole, fraction = ""] = match;
  const decimals = DECIMALS[currency];
  if (fraction.length > decimals) return null;
  const digits = (whole + fraction.padEnd(decimals, "0")).replace(/^0+(?=\d)/, "");
  if (digits.length > MAX_DIGITS) return null;
  // Chaîne de chiffres entiers : conversion exacte, sans virgule flottante.
  return Number.parseInt(digits, 10);
}

export function sumAmounts(amounts: number[]): number {
  return amounts.reduce((total, minor) => {
    assertInteger(minor);
    return total + minor;
  }, 0);
}

/** `total` en `parts` montants entiers dont la somme est exactement `total` ; les unités qui
 * restent vont aux premières parts : `100000 FC` en 3 → `33 334, 33 333, 33 333`. */
export function splitEvenly(total: number, parts: number): number[] {
  assertInteger(total);
  if (!Number.isInteger(parts) || parts < 1) return [];
  const base = Math.floor(total / parts);
  const rest = total - base * parts;
  return Array.from({ length: parts }, (_, index) => base + (index < rest ? 1 : 0));
}

/** `percent` % d'un montant, arrondi demi supérieur à l'unité de la devise (réduction E3) ;
 * même calcul que `apps.core.money.percent_of` du serveur. */
export function percentOf(minor: number, percent: number): number {
  assertInteger(minor);
  assertInteger(percent);
  return Number((BigInt(minor) * BigInt(percent) * 2n + 100n) / 200n);
}

/** `total` réparti au prorata de `weights`, en entiers dont la somme est exactement `total` :
 * chaque part arrondie à l'inférieur, puis une unité de plus aux restes les plus grands, à
 * égalité aux premières (l'écart d'arrondi tombe sur les dernières) ; même calcul que
 * `apps.core.money.prorate` du serveur. `5000` sur `[12000, 12000, 12000]` → `1667, 1667, 1666`. */
export function prorate(total: number, weights: number[]): number[] {
  assertInteger(total);
  const base = BigInt(sumAmounts(weights));
  if (base <= 0n || total < 0) throw new RangeError("Répartition impossible");
  const parts = weights.map((weight, index) => {
    const product = BigInt(total) * BigInt(weight);
    return { share: Number(product / base), remainder: product % base, index };
  });
  const shares = parts.map((part) => part.share);
  const rest = total - sumAmounts(shares);
  const largest = [...parts].sort((a, b) =>
    a.remainder === b.remainder ? a.index - b.index : a.remainder > b.remainder ? -1 : 1,
  );
  for (const part of largest.slice(0, rest)) shares[part.index] = shares[part.index]! + 1;
  return shares;
}

/** Taux du serveur (`"2850.000000"`) → `2 850` ; `"2875.500000"` → `2 875,5`. */
export function formatRate(rate: string): string {
  const [whole = "0", fraction = ""] = rate.split(".");
  const kept = fraction.replace(/0+$/, "");
  return kept ? `${group(whole)},${kept}` : group(whole);
}

/** Saisie d'un taux (francs pour 1 dollar) → texte envoyé au serveur (`"2 875,5"` →
 * `"2875.5"`) ; `null` si vide, nul ou avec plus de 6 décimales. */
export function parseRate(text: string): string | null {
  const match = /^(\d{1,8})(?:[.,](\d{0,6}))?$/.exec(text.replace(/\s/g, ""));
  if (!match) return null;
  const whole = match[1]!;
  const fraction = match[2] ?? "";
  if (!/[1-9]/.test(whole + fraction)) return null;
  return fraction ? `${whole}.${fraction}` : whole;
}

/** Rapport d'entiers arrondi au demi supérieur (loin de zéro, comme `ROUND_HALF_UP`). */
function roundedRatio(numerator: bigint, denominator: bigint): bigint {
  const sign = numerator < 0n ? -1n : 1n;
  const size = numerator * sign;
  return sign * ((2n * size + denominator) / (2n * denominator));
}

/** Conversion au taux USD → CDF tel que saisi (décision Q4), comme `Money.convert` du serveur :
 * USD → CDF multiplie, CDF → USD divise ; arrondi demi supérieur à l'unité de la devise cible.
 * Calculée sur des entiers exacts (le taux a au plus 6 décimales). */
export function convert(minor: number, from: Currency, to: Currency, rate: string): number {
  if (from === to) return minor;
  const [whole = "0", fraction = ""] = rate.split(".");
  const scaledRate = BigInt(whole + fraction.padEnd(6, "0").slice(0, 6));
  if (scaledRate <= 0n) throw new RangeError(`taux invalide : ${rate}`);
  const perUnit = 1_000_000n * 100n; // 6 décimales du taux, 100 centimes pour 1 dollar
  const amount = BigInt(minor);
  const converted =
    to === "CDF"
      ? roundedRatio(amount * scaledRate, perUnit)
      : roundedRatio(amount * perUnit, scaledRate);
  return Number(converted);
}
