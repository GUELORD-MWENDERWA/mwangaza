// QR code d'un reçu (F4) : l'adresse de la page de vérification `/v/{id}` de l'école. Sur un
// appareil mémorisé (3.5.2), suivie de ce que le reçu affiche — `n` numéro, `t` heure en
// secondes, `a` montant, `c` devise, `r` caisse — signé par la clé de l'appareil (`s`, ECDSA
// P-256) : un reçu imprimé hors ligne est vérifiable avant la synchronisation, un reçu modifié
// est reconnu. Serveur : `finance/verification.py` (`Claim`), même texte signé.

type Printed = {
  id: string;
  receipt_number: string;
  paid_at: string;
  received_amount_minor: number;
  received_currency: string;
  cash_register: string;
};

/** Texte signé : `id|n|t|a|c|r`. */
export function claimOf(payment: Printed) {
  const claim = {
    n: payment.receipt_number,
    t: String(Math.floor(Date.parse(payment.paid_at) / 1000)),
    a: String(payment.received_amount_minor),
    c: payment.received_currency,
    r: payment.cash_register,
  };
  return { claim, message: [payment.id, claim.n, claim.t, claim.a, claim.c, claim.r].join("|") };
}

function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** Adresse du QR code ; signée avec `key` (clé privée de l'appareil), sinon l'adresse seule. */
export async function receiptQr(origin: string, payment: Printed, key?: CryptoKey) {
  const url = `${origin}/v/${payment.id}`;
  if (!key) return url;
  const { claim, message } = claimOf(payment);
  const signature = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    key,
    new TextEncoder().encode(message),
  );
  const query = new URLSearchParams({ ...claim, s: base64url(new Uint8Array(signature)) });
  return `${url}?${query}`;
}
