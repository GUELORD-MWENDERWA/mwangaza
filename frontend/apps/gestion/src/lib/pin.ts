import { browserStore, type DeviceStore, type LocalDevice } from "./device";

/** Code PIN de déverrouillage (B5, 03 § 5.5) : il rouvre l'application sur un appareil mémorisé,
 *  même sans réseau. Vérifié ici contre une empreinte PBKDF2, jamais envoyé au serveur. */
export const PIN_LENGTH = 4;
export const MAX_PIN_FAILURES = 5;
/** Connexion complète (mot de passe) exigée au moins tous les 7 jours sur l'appareil. */
export const FULL_LOGIN_EVERY = 7 * 24 * 3600_000;
// Un PIN de 4 chiffres ne résiste pas à qui lit la base du navigateur (limite connue, 03 § 5.5) :
// assez d'itérations pour ralentir, pas trop pour un vieux téléphone.
const ITERATIONS = 100_000;

export type PinHash = { salt: string; hash: string; iterations: number };

/** `none` : pas de PIN ici ; `signed_out` : « Se déconnecter » ; `expired` : connexion complète
 *  de plus de 7 jours ; `blocked` : 5 codes faux. Sauf `ok`, le mot de passe est exigé. */
export type PinState = "ok" | "none" | "signed_out" | "expired" | "blocked";

export type PinAttempt =
  { outcome: Exclude<PinState, "none"> } | { outcome: "wrong"; left: number };

export async function hashPin(
  pin: string,
  salt: Uint8Array<ArrayBuffer> = crypto.getRandomValues(new Uint8Array(16)),
  iterations = ITERATIONS,
): Promise<PinHash> {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(pin), "PBKDF2", false, [
    "deriveBits",
  ]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    key,
    256,
  );
  return { salt: toBase64(salt), hash: toBase64(new Uint8Array(bits)), iterations };
}

export async function checkPin(pin: string, stored: PinHash): Promise<boolean> {
  const again = await hashPin(pin, fromBase64(stored.salt), stored.iterations);
  return again.hash === stored.hash;
}

/** Autre chose que 4 chiffres, ou facile à deviner : 0000, 7777, 1234, 4321… */
export function weakPin(pin: string): boolean {
  if (!new RegExp(`^\\d{${PIN_LENGTH}}$`).test(pin)) return true;
  const steps = new Set([...pin].slice(1).map((digit, i) => Number(digit) - Number(pin[i])));
  return steps.size === 1 && [0, 1, -1].includes([...steps][0]!);
}

export function pinState(device: LocalDevice, now = Date.now()): PinState {
  if (!device.pin) return "none";
  if (!device.loggedInAt) return "signed_out";
  if (now - device.loggedInAt > FULL_LOGIN_EVERY) return "expired";
  if ((device.pinFailures ?? 0) >= MAX_PIN_FAILURES) return "blocked";
  return "ok";
}

/** Définit ou change le PIN du compte sur cet appareil (Mon compte). */
export async function setPin(user: string, pin: string, store: DeviceStore = browserStore) {
  await store.update(user, { pin: await hashPin(pin), pinFailures: 0 });
}

/** Un essai au déverrouillage ; chaque code faux est compté sur l'appareil. */
export async function tryPin(
  user: string,
  pin: string,
  store: DeviceStore = browserStore,
  now = Date.now(),
): Promise<PinAttempt> {
  const device = await store.get(user);
  const state = device ? pinState(device, now) : "none";
  if (state === "none") return { outcome: "signed_out" };
  if (state !== "ok") return { outcome: state };
  if (await checkPin(pin, device!.pin!)) {
    await store.update(user, { pinFailures: 0, seenAt: now });
    return { outcome: "ok" };
  }
  const failures = (device!.pinFailures ?? 0) + 1;
  await store.update(user, { pinFailures: failures });
  return failures >= MAX_PIN_FAILURES
    ? { outcome: "blocked" }
    : { outcome: "wrong", left: MAX_PIN_FAILURES - failures };
}

/** « Se déconnecter » : plus de déverrouillage par PIN avant la prochaine connexion complète. */
export async function signOutDevice(user: string, store: DeviceStore = browserStore) {
  await store.update(user, { loggedInAt: null });
}

function toBase64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(value: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
}
