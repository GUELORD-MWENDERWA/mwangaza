import { describe, expect, it, vi } from "vitest";

import { attachDevice, deviceLabel, type LocalDevice } from "./device";

const EDGE_WINDOWS =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0";

describe("deviceLabel", () => {
  it("names the system and the browser, the most specific first", () => {
    expect(deviceLabel(EDGE_WINDOWS)).toBe("Windows · Edge");
    expect(
      deviceLabel(
        "Mozilla/5.0 (Linux; Android 14; SM-A145F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
      ),
    ).toBe("Android · Chrome");
    expect(
      deviceLabel(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      ),
    ).toBe("iOS · Safari");
    expect(deviceLabel("curl/8.0")).toBe("Web");
  });
});

function setup(local?: LocalDevice, resumed = true) {
  const saved = new Map(local ? [[local.user, local]] : []);
  const store = {
    get: vi.fn(async (user: string) => saved.get(user)),
    all: vi.fn(async () => [...saved.values()]),
    put: vi.fn(async (device: LocalDevice) => void saved.set(device.user, device)),
    update: vi.fn(async (user: string, changes: Partial<LocalDevice>) => {
      const current = saved.get(user);
      if (current) saved.set(user, { ...current, ...changes });
    }),
    delete: vi.fn(async (user: string) => void saved.delete(user)),
  };
  const server = {
    resume: vi.fn(async () => resumed),
    register: vi.fn(async () => ({ id: "new-device", prefix: "P7" })),
  };
  const privateKey = {} as CryptoKey;
  const wipe = vi.fn(async () => {});
  const deps = {
    store,
    server,
    wipe,
    createKeys: async () => ({ privateKey, publicKey: "MFkw…" }),
    userAgent: EDGE_WINDOWS,
    now: () => NOW,
  };
  return { saved, server, deps, privateKey, wipe };
}

const NOW = Date.parse("2026-10-05T08:00:00Z");

const OLD: LocalDevice = {
  user: "u1",
  id: "old-device",
  prefix: "P1",
  privateKey: {} as CryptoKey,
};

describe("attachDevice", () => {
  it("resumes the device already remembered, without a new key, and notes the full login", async () => {
    const { saved, server, deps } = setup(OLD);

    await attachDevice("u1", true, deps);

    expect(server.resume).toHaveBeenCalledWith("old-device");
    expect(server.register).not.toHaveBeenCalled();
    expect(saved.get("u1")).toEqual({ ...OLD, loggedInAt: NOW, pinFailures: 0 });
    expect(deps.wipe).not.toHaveBeenCalled();
  });

  it("forgets a disconnected device and wipes its data, then remembers a new one only if asked", async () => {
    const unticked = setup(OLD, false);
    await attachDevice("u1", false, unticked.deps);
    expect(unticked.saved.size).toBe(0);
    expect(unticked.wipe).toHaveBeenCalledWith("old-device");
    expect(unticked.server.register).not.toHaveBeenCalled();

    const ticked = setup(OLD, false);
    await attachDevice("u1", true, ticked.deps);
    expect(ticked.server.register).toHaveBeenCalledWith("Windows · Edge", "MFkw…");
    expect(ticked.saved.get("u1")).toEqual({
      user: "u1",
      id: "new-device",
      prefix: "P7",
      privateKey: ticked.privateKey,
      loggedInAt: NOW,
      pinFailures: 0,
    });
  });

  it("keeps one device per account on a shared computer", async () => {
    const { saved, server, deps } = setup(OLD);

    await attachDevice("u2", true, deps);

    expect(server.resume).not.toHaveBeenCalled();
    expect([...saved.keys()].sort()).toEqual(["u1", "u2"]);
  });
});
