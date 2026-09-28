import { ApiError } from "@mwangaza/api";
import { describe, expect, it, vi, type Mock } from "vitest";

import {
  EMPTY_META,
  synchronize,
  type Change,
  type Config,
  type Enrollment,
  type LocalStore,
  type Operation,
  type Outcome,
  type SyncMeta,
  type SyncServer,
} from "./engine";

const config = { school: { code: "itig" } } as unknown as Config;
const enrollment = (id: string, status = "active") => ({ id, status }) as unknown as Enrollment;
const operation = (index: number): Operation => ({
  op_id: `op-${String(index).padStart(3, "0")}`,
  type: "payment.create",
  payload: { amount: index },
  created_at: "2026-09-29T08:00:00Z",
});

type Queued = Operation & { status: "pending" | "rejected"; error: Outcome["error"] };

/** Base de l'appareil en mémoire, avec les règles de `dexieStore`. */
function memoryStore(meta: Partial<SyncMeta> = {}, queued: Operation[] = []) {
  const state = {
    meta: { ...EMPTY_META, ...meta },
    enrollments: new Map<string, Enrollment & { gen: number }>(),
    config: null as Config | null,
    outbox: queued.map((op): Queued => ({ ...op, status: "pending", error: null })),
    wiped: false,
  };
  const store: LocalStore = {
    meta: async () => ({ ...state.meta }),
    setMeta: async (changes) => void Object.assign(state.meta, changes),
    saveSnapshotPage: async (page, changes) => {
      for (const item of page.enrollments)
        state.enrollments.set(item.id, { ...item, gen: page.gen });
      if (page.config) state.config = page.config;
      if (page.last) {
        for (const [id, item] of state.enrollments) {
          if (item.gen !== page.gen) state.enrollments.delete(id);
        }
      }
      Object.assign(state.meta, changes);
    },
    saveChanges: async (changes, meta) => {
      for (const change of changes) {
        if (change.entity_type === "config") state.config = change.config;
        else if (change.operation === "delete" || !change.enrollment) {
          state.enrollments.delete(change.entity_id);
        } else
          state.enrollments.set(change.entity_id, { ...change.enrollment, gen: state.meta.gen });
      }
      Object.assign(state.meta, meta);
    },
    pending: async (limit) => state.outbox.filter((op) => op.status === "pending").slice(0, limit),
    settle: async (outcomes) => {
      for (const outcome of outcomes) {
        const index = state.outbox.findIndex((op) => op.op_id === outcome.op_id);
        if (outcome.status === "rejected") {
          state.outbox[index] = {
            ...state.outbox[index]!,
            status: "rejected",
            error: outcome.error,
          };
        } else state.outbox.splice(index, 1);
      }
    },
    wipe: async () => {
      state.wiped = true;
      state.enrollments.clear();
      state.outbox = [];
    },
  };
  return { store, state };
}

type Page = Awaited<ReturnType<SyncServer["snapshot"]>>;
const page = (items: Enrollment[], next: string | null, first = false): Page => ({
  cursor: first ? 40 : null,
  device: first ? { id: "d1", prefix: "P1", last_receipt_seq: 184 } : null,
  config: first ? config : null,
  enrollments: items,
  next,
});

type FakeServer = { [K in keyof SyncServer]: Mock<SyncServer[K]> };

function server(overrides: Partial<FakeServer> = {}): FakeServer {
  return {
    snapshot: vi.fn<SyncServer["snapshot"]>(async (after) =>
      after
        ? page([enrollment("e3")], null)
        : page([enrollment("e1"), enrollment("e2")], "e2", true),
    ),
    pull: vi.fn<SyncServer["pull"]>(async (since) => ({
      changes: [],
      cursor: since,
      has_more: false,
    })),
    push: vi.fn<SyncServer["push"]>(async (operations) =>
      operations.map((op) => ({ op_id: op.op_id, status: "applied", result: {}, error: null })),
    ),
    ...overrides,
  };
}

const NOW = () => new Date("2026-09-29T09:30:00Z");

describe("instantané", () => {
  it("premier chargement : toutes les pages, curseur de la première, séquence des reçus reprise", async () => {
    const { store, state } = memoryStore({ receiptSeq: 3 });
    const remote = server();

    expect(await synchronize(store, remote, NOW)).toBe("done");

    expect(remote.snapshot.mock.calls).toEqual([[undefined], ["e2"]]);
    expect([...state.enrollments.keys()]).toEqual(["e1", "e2", "e3"]);
    expect(state.config).toBe(config);
    // Réinstallé : le serveur connaît déjà le reçu 184, l'appareil ne redonne pas ce numéro.
    expect(state.meta).toMatchObject({ cursor: 40, snapshot: null, receiptSeq: 184, gen: 1 });
    expect(state.meta.lastSyncAt).toBe("2026-09-29T09:30:00.000Z");

    await synchronize(store, remote, NOW);
    expect(remote.snapshot).toHaveBeenCalledTimes(2);
    expect(remote.pull).toHaveBeenCalledWith(40);
  });

  it("coupure au milieu : reprise à la page suivante, anciennes données lisibles jusqu'à la fin", async () => {
    const { store, state } = memoryStore({ cursor: 900, gen: 1 });
    state.enrollments.set("old", { ...enrollment("old"), gen: 1 });
    const remote = server({
      pull: vi.fn<SyncServer["pull"]>(async () => {
        throw new ApiError(409, "snapshot_required", "Out of date.");
      }),
    });
    remote.snapshot.mockImplementationOnce(async () =>
      page([enrollment("e1"), enrollment("e2")], "e2", true),
    );
    remote.snapshot.mockImplementationOnce(async () => {
      throw new ApiError(0, "network", "No response.");
    });

    await expect(synchronize(store, remote, NOW)).rejects.toThrow(ApiError);
    expect([...state.enrollments.keys()]).toEqual(["old", "e1", "e2"]);
    expect(state.meta.lastSyncAt).toBeNull();

    await synchronize(store, remote, NOW);
    // Pas de nouveau `pull` ni de première page : l'instantané reprend là où il s'est arrêté.
    expect(remote.pull).toHaveBeenCalledOnce();
    expect(remote.snapshot.mock.calls).toEqual([[undefined], ["e2"], ["e2"]]);
    expect([...state.enrollments.keys()]).toEqual(["e1", "e2", "e3"]);
    expect(state.meta).toMatchObject({ cursor: 40, gen: 2, snapshot: null });
  });
});

describe("changements", () => {
  it("pages suivies jusqu'au bout : ajouts, suppressions, configuration, curseur gardé", async () => {
    const { store, state } = memoryStore({ cursor: 40, gen: 1 });
    state.enrollments.set("e1", { ...enrollment("e1"), gen: 1 });
    const change = (seq: number, id: string, rest: Partial<Change>): Change => ({
      seq,
      entity_type: "enrollment",
      entity_id: id,
      operation: "upsert",
      enrollment: null,
      config: null,
      ...rest,
    });
    const remote = server({
      pull: vi
        .fn<SyncServer["pull"]>()
        .mockResolvedValueOnce({
          changes: [change(41, "e1", { operation: "delete" })],
          cursor: 41,
          has_more: true,
        })
        .mockResolvedValueOnce({
          changes: [
            change(42, "e9", { enrollment: enrollment("e9", "transferred") }),
            change(43, "s1", { entity_type: "config", config }),
          ],
          cursor: 43,
          has_more: false,
        }),
    });

    await synchronize(store, remote, NOW);

    expect(remote.pull.mock.calls).toEqual([[40], [41]]);
    expect([...state.enrollments.values()]).toEqual([
      { ...enrollment("e9", "transferred"), gen: 1 },
    ]);
    expect(state.config).toBe(config);
    expect(state.meta.cursor).toBe(43);
    expect(remote.snapshot).not.toHaveBeenCalled();
  });
});

describe("file d'opérations", () => {
  it("envoyée dans l'ordre par 100 avec la séquence des reçus ; refusées gardées et plus renvoyées", async () => {
    const queued = Array.from({ length: 150 }, (_, index) => operation(index));
    const { store, state } = memoryStore({ cursor: 40, gen: 1, receiptSeq: 150 }, queued);
    const remote = server({
      push: vi.fn<SyncServer["push"]>(async (operations) =>
        operations.map((op) =>
          op.op_id === "op-120"
            ? {
                op_id: op.op_id,
                status: "rejected",
                result: {},
                error: { code: "no_open_session", detail: "No open session." },
              }
            : {
                op_id: op.op_id,
                status: op.op_id === "op-007" ? "duplicate" : "applied",
                result: {},
                error: null,
              },
        ),
      ),
    });

    await synchronize(store, remote, NOW);

    expect(remote.push).toHaveBeenCalledTimes(2);
    expect(remote.push.mock.calls[0]![0].map((op) => op.op_id)).toEqual(
      queued.slice(0, 100).map((op) => op.op_id),
    );
    expect(remote.push.mock.calls[1]![0]).toHaveLength(50);
    expect(remote.push.mock.calls[0]![1]).toBe(150);
    // Envoyer d'abord : les changements descendus comprennent déjà ces paiements.
    expect(remote.push.mock.invocationCallOrder[1]).toBeLessThan(
      remote.pull.mock.invocationCallOrder[0]!,
    );
    expect(state.outbox).toEqual([
      {
        ...queued[120],
        status: "rejected",
        error: { code: "no_open_session", detail: "No open session." },
      },
    ]);

    await synchronize(store, remote, NOW);
    expect(remote.push).toHaveBeenCalledTimes(2);
  });

  it("réseau coupé pendant l'envoi : rien de perdu, rien descendu", async () => {
    const { store, state } = memoryStore({ cursor: 40, gen: 1 }, [operation(1), operation(2)]);
    const remote = server({
      push: vi.fn<SyncServer["push"]>(async () => {
        throw new ApiError(0, "network", "No response.");
      }),
    });

    await expect(synchronize(store, remote, NOW)).rejects.toThrow(ApiError);

    expect(state.outbox.map((op) => [op.op_id, op.status])).toEqual([
      ["op-001", "pending"],
      ["op-002", "pending"],
    ]);
    expect(remote.pull).not.toHaveBeenCalled();
    expect(state.meta.lastSyncAt).toBeNull();
  });

  it("appareil déconnecté par l'école : données de l'appareil effacées", async () => {
    const { store, state } = memoryStore({ cursor: 40, gen: 1 }, [operation(1)]);
    state.enrollments.set("e1", { ...enrollment("e1"), gen: 1 });
    const remote = server({
      push: vi.fn<SyncServer["push"]>(async () => {
        throw new ApiError(409, "device_revoked", "This device was disconnected.");
      }),
    });

    expect(await synchronize(store, remote, NOW)).toBe("revoked");

    expect(state.wiped).toBe(true);
    expect(state.enrollments.size).toBe(0);
  });
});
