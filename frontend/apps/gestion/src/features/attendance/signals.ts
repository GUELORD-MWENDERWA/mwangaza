// Signaux de l'appareil (lot 10, SIG.1) : son, vibration et écran allumé, sans fichier ni
// dépendance (Web Audio, `navigator.vibrate`, Wake Lock). Mêmes sons que les lecteurs de cartes
// (lot 16) : 1 bip aigu = arrivé · 2 notes descendantes = en retard · 2 bips courts = déjà passé ·
// 2 bips longs = refusé. Réglages gardés sur cet appareil seulement (`localStorage`), jamais sur le
// serveur : une tablette de porte a besoin du son, un téléphone de bureau non.

export type Signal = "arrived" | "late" | "already" | "refused" | "saved" | "alert";
export type SignalSettings = { sound: boolean; vibration: boolean; awake: boolean };

const KEY = "mwangaza.signals";
export const DEFAULT_SETTINGS: SignalSettings = { sound: true, vibration: true, awake: true };

/** Notes jouées : fréquence (Hz), durée (s), silence avant (s). */
export const TONES: Record<Signal, { hz: number; length: number; gap: number }[]> = {
  arrived: [{ hz: 1568, length: 0.14, gap: 0 }],
  late: [
    { hz: 988, length: 0.14, gap: 0 },
    { hz: 659, length: 0.2, gap: 0.04 },
  ],
  already: [
    { hz: 784, length: 0.07, gap: 0 },
    { hz: 784, length: 0.07, gap: 0.08 },
  ],
  refused: [
    { hz: 330, length: 0.32, gap: 0 },
    { hz: 330, length: 0.32, gap: 0.1 },
  ],
  saved: [
    { hz: 880, length: 0.06, gap: 0 },
    { hz: 1175, length: 0.1, gap: 0.02 },
  ],
  alert: [
    { hz: 1047, length: 0.16, gap: 0 },
    { hz: 784, length: 0.16, gap: 0.06 },
    { hz: 1047, length: 0.16, gap: 0.06 },
  ],
};

/** Vibration en millisecondes (vibre, pause, vibre…). */
export const VIBRATIONS: Record<Signal, number[]> = {
  arrived: [60],
  late: [60, 60, 60],
  already: [40, 60, 40],
  refused: [300, 100, 300],
  saved: [40],
  alert: [120, 60, 120, 60, 120],
};

export function loadSettings(): SignalSettings {
  try {
    const raw = localStorage.getItem(KEY);
    return raw
      ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<SignalSettings>) }
      : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: SignalSettings) {
  try {
    localStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    // Stockage refusé (fenêtre privée) : réglage valable jusqu'à la fermeture seulement.
  }
}

/** L'appareil vibre-t-il ? (Pas l'iPhone : le réglage est alors caché.) */
export const canVibrate = () => typeof navigator !== "undefined" && "vibrate" in navigator;

let context: AudioContext | null = null;

/** Débloque le son : le navigateur l'exige après un geste de la personne (premier appui). */
export function unlockSound() {
  try {
    const Audio =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Audio) return;
    context ??= new Audio();
    if (context.state === "suspended") void context.resume();
  } catch {
    // Pas de son sur cet appareil : la couleur et la vibration restent.
  }
}

/** Joue le signal selon les réglages de l'appareil. Ne lève jamais d'erreur. */
export function signal(kind: Signal, settings: SignalSettings = loadSettings()) {
  if (settings.vibration && canVibrate()) navigator.vibrate(VIBRATIONS[kind]);
  if (!settings.sound || !context) return;
  try {
    let at = context.currentTime;
    for (const tone of TONES[kind]) {
      at += tone.gap;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = tone.hz;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.4, at + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + tone.length);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(at);
      oscillator.stop(at + tone.length + 0.02);
      at += tone.length;
    }
  } catch {
    // Ignoré : un signal manqué ne bloque jamais le pointage.
  }
}

type Lock = { release: () => Promise<void> };

/** Garde l'écran allumé tant que la page est visible ; rend la fonction qui le relâche. */
export function keepAwake(): () => void {
  let lock: Lock | null = null;
  let stopped = false;
  const wakeLock = (
    navigator as unknown as { wakeLock?: { request: (kind: "screen") => Promise<Lock> } }
  ).wakeLock;
  const ask = () => {
    if (stopped || !wakeLock || document.visibilityState !== "visible") return;
    wakeLock.request("screen").then(
      (got) => (lock = got),
      () => undefined,
    );
  };
  ask();
  document.addEventListener("visibilitychange", ask);
  return () => {
    stopped = true;
    document.removeEventListener("visibilitychange", ask);
    void lock?.release().catch(() => undefined);
  };
}
