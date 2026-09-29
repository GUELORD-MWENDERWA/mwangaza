import { describe, expect, it, vi } from "vitest";

import { attachDevice, type DeviceStore, type LocalDevice } from "./device";
import { checkPin, hashPin, pinState, setPin, signOutDevice, tryPin, weakPin } from "./pin";

const DAY = 24 * 3600_000;
const NOW = Date.parse("2026-10-05T08:00:00Z");

function memoryStore(device: LocalDevice): DeviceStore & { saved: Map<string, LocalDevice> } {
  const saved = new Map([[device.user, device]]);
  return {
    saved,
    get: async (user) => saved.get(user),
    all: async () => [...saved.values()],
    put: async (value) => void saved.set(value.user, value),
    update: async (user, changes) => {
      const current = saved.get(user);
      if (current) saved.set(user, { ...current, ...changes });
    },
    delete: async (user) => void saved.delete(user),
  };
}

const DEVICE: LocalDevice = {
  user: "u1",
  id: "device-1",
  prefix: "P1",
  privateKey: {} as CryptoKey,
  loggedInAt: NOW - DAY,
};

describe("empreinte du PIN", () => {
  it("reconnaît le bon code seulement, avec un sel différent à chaque empreinte", async () => {
    const stored = await hashPin("2580");

    expect(await checkPin("2580", stored)).toBe(true);
    expect(await checkPin("2581", stored)).toBe(false);
    expect((await hashPin("2580")).salt).not.toBe(stored.salt);
    expect(JSON.stringify(stored)).not.toContain("2580");
  });

  it("refuse les codes trop faciles à deviner", () => {
    expect(["0000", "7777", "1234", "6789", "4321", "9876", "123", "12a4"].map(weakPin)).toEqual(
      Array(8).fill(true),
    );
    expect(["2580", "1357", "1235", "0912"].map(weakPin)).toEqual(Array(4).fill(false));
  });
});

describe("déverrouillage (B5)", () => {
  it("5 codes faux : connexion complète exigée, puis le PIN remarche après elle", async () => {
    const store = memoryStore(DEVICE);
    await setPin("u1", "2580", store);

    for (const left of [4, 3, 2, 1]) {
      expect(await tryPin("u1", "1111", store, NOW)).toEqual({ outcome: "wrong", left });
    }
    expect(await tryPin("u1", "1111", store, NOW)).toEqual({ outcome: "blocked" });
    // Même le bon code ne passe plus.
    expect(await tryPin("u1", "2580", store, NOW)).toEqual({ outcome: "blocked" });

    const server = { resume: vi.fn(async () => true), register: vi.fn() };
    const deps = {
      store,
      server,
      wipe: vi.fn(),
      createKeys: vi.fn(),
      userAgent: "",
      now: () => NOW,
    };
    await attachDevice("u1", true, deps);
    expect(await tryPin("u1", "2580", store, NOW)).toEqual({ outcome: "ok" });
    expect(store.saved.get("u1")?.pinFailures).toBe(0);
  });

  it("un bon code remet le compteur à zéro", async () => {
    const store = memoryStore(DEVICE);
    await setPin("u1", "2580", store);
    await tryPin("u1", "1111", store, NOW);

    expect(await tryPin("u1", "2580", store, NOW)).toEqual({ outcome: "ok" });
    expect(await tryPin("u1", "1111", store, NOW)).toEqual({ outcome: "wrong", left: 4 });
  });

  it("refusé après 7 jours sans connexion complète, ou après « Se déconnecter »", async () => {
    const store = memoryStore(DEVICE);
    await setPin("u1", "2580", store);
    const device = () => store.saved.get("u1")!;

    expect(pinState(device(), DEVICE.loggedInAt! + 7 * DAY)).toBe("ok");
    expect(pinState(device(), DEVICE.loggedInAt! + 7 * DAY + 1)).toBe("expired");
    expect(await tryPin("u1", "2580", store, NOW + 7 * DAY)).toEqual({ outcome: "expired" });

    await signOutDevice("u1", store);
    expect(await tryPin("u1", "2580", store, NOW)).toEqual({ outcome: "signed_out" });
    // Le PIN reste défini : il remarchera après la prochaine connexion complète.
    expect(device().pin).toBeDefined();
  });

  it("sans PIN défini sur l'appareil : rien à essayer", () => {
    expect(pinState(DEVICE, NOW)).toBe("none");
  });
});
