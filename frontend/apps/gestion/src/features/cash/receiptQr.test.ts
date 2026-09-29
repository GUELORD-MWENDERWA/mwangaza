import { describe, expect, it } from "vitest";

import { receiptQr } from "./receiptQr";

const payment = {
  id: "0192b6c1-7f3a-7b2e-9c1d-3e4f5a6b7c8d",
  receipt_number: "ITIG-P1-26-000184",
  paid_at: "2026-10-05T09:00:00.456Z",
  received_amount_minor: 3000,
  received_currency: "USD",
  cash_register: "C1",
};

describe("QR code du reçu (F4)", () => {
  it("adresse seule sans clé ; sur l'appareil, contenu signé que le serveur vérifie", async () => {
    const origin = "https://itig.mwangaza.school";
    expect(await receiptQr(origin, payment)).toBe(`${origin}/v/${payment.id}`);

    const keys = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, false, [
      "sign",
      "verify",
    ]);
    const url = new URL(await receiptQr(origin, payment, keys.privateKey));
    const { s, ...claim } = Object.fromEntries(url.searchParams);
    const seconds = String(Date.UTC(2026, 9, 5, 9) / 1000);
    expect(claim).toEqual({ n: "ITIG-P1-26-000184", t: seconds, a: "3000", c: "USD", r: "C1" });
    // `finance/verification.py` : r ‖ s en base64url, sur `id|n|t|a|c|r`.
    const bytes = atob(s!.replace(/-/g, "+").replace(/_/g, "/"));
    const signature = Uint8Array.from(bytes, (char) => char.charCodeAt(0));
    const message = `${payment.id}|ITIG-P1-26-000184|${seconds}|3000|USD|C1`;
    const verify = (text: string) =>
      crypto.subtle.verify(
        { name: "ECDSA", hash: "SHA-256" },
        keys.publicKey,
        signature,
        new TextEncoder().encode(text),
      );
    expect(signature).toHaveLength(64);
    expect(await verify(message)).toBe(true);
    expect(await verify(message.replace("|3000|", "|30000|"))).toBe(false);
  });
});
