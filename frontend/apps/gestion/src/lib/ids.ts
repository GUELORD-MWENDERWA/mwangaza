// Identifiants donnés par l'appareil (règle 4 de `CLAUDE.md`) : UUID v7 (RFC 9562), triés par
// date de création. Le même identifiant renvoyé après une coupure ne crée pas de doublon.

/** UUID v7 : 48 bits de millisecondes depuis 1970, version, variante, 74 bits aléatoires. */
export function uuidv7(now = Date.now()): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let time = now;
  for (let index = 5; index >= 0; index -= 1) {
    bytes[index] = time % 256;
    time = Math.floor(time / 256);
  }
  bytes[6] = (bytes[6]! & 0x0f) | 0x70;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
