// Montant en lettres du reçu (F3), en français (orthographe traditionnelle, comme les documents
// officiels en RDC), calculé sur l'appareil : le reçu s'imprime aussi hors ligne.
import type { Currency } from "./index";

const UNITS = [
  "zéro",
  "un",
  "deux",
  "trois",
  "quatre",
  "cinq",
  "six",
  "sept",
  "huit",
  "neuf",
  "dix",
  "onze",
  "douze",
  "treize",
  "quatorze",
  "quinze",
  "seize",
  "dix-sept",
  "dix-huit",
  "dix-neuf",
];
const TENS = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante"];
const unit = (n: number) => UNITS[n] ?? "";
const NAMES: Record<Currency, [string, string]> = {
  USD: ["dollar américain", "dollars américains"],
  CDF: ["franc congolais", "francs congolais"],
};

// `plural` : rien ne suit (ou « millions ») : « quatre-vingts », « deux cents » ; devant
// « mille », jamais de s.
function below100(n: number, plural: boolean): string {
  if (n < 20) return unit(n);
  const ten = Math.floor(n / 10);
  const one = n % 10;
  if (ten === 7) return one === 1 ? "soixante et onze" : `soixante-${unit(10 + one)}`;
  if (ten === 8)
    return one ? `quatre-vingt-${unit(one)}` : plural ? "quatre-vingts" : "quatre-vingt";
  if (ten === 9) return `quatre-vingt-${unit(10 + one)}`;
  const tens = TENS[ten] ?? "";
  if (!one) return tens;
  return one === 1 ? `${tens} et un` : `${tens}-${unit(one)}`;
}

function below1000(n: number, plural: boolean): string {
  const hundreds = Math.floor(n / 100);
  const rest = n % 100;
  const words: string[] = [];
  if (hundreds === 1) words.push("cent");
  else if (hundreds) words.push(`${unit(hundreds)} ${!rest && plural ? "cents" : "cent"}`);
  if (rest) words.push(below100(rest, plural));
  return words.join(" ");
}

function numberInWords(n: number): string {
  if (n === 0) return unit(0);
  const words: string[] = [];
  let rest = n;
  for (const [value, name] of [
    [1e9, "milliard"],
    [1e6, "million"],
  ] as const) {
    const count = Math.floor(rest / value);
    rest %= value;
    if (count) words.push(`${numberInWords(count)} ${name}${count > 1 ? "s" : ""}`);
  }
  const thousands = Math.floor(rest / 1000);
  rest %= 1000;
  if (thousands) words.push(thousands === 1 ? "mille" : `${below1000(thousands, false)} mille`);
  if (rest) words.push(below1000(rest, true));
  return words.join(" ");
}

/** `15025, "USD"` → « Cent cinquante dollars américains et vingt-cinq centimes » ;
 * `1000000, "CDF"` → « Un million de francs congolais ». */
export function amountInWords(minor: number, currency: Currency): string {
  if (!Number.isSafeInteger(minor) || minor < 0) throw new TypeError(`Montant invalide : ${minor}`);
  const factor = currency === "USD" ? 100 : 1;
  const major = Math.floor(minor / factor);
  const cents = minor % factor;
  const [one, many] = NAMES[currency];
  // « un million de francs », mais « un million deux cents francs ».
  const of = major >= 1e6 && major % 1e6 === 0 ? "de " : "";
  let text = `${numberInWords(major)} ${of}${major > 1 ? many : one}`;
  if (cents) text += ` et ${numberInWords(cents)} ${cents > 1 ? "centimes" : "centime"}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}
