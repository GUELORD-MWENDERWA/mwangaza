import { ApiError } from "@mwangaza/api";
import { describe, expect, it } from "vitest";

import type { ReadRow } from "./db";
import { keep, readOrKept } from "./reads";

/** Table de l'appareil en mémoire (pas d'IndexedDB dans les tests). */
function table() {
  const rows = new Map<string, ReadRow>();
  const fake = {
    get: async (id: string) => rows.get(id),
    put: async (row: ReadRow) => void rows.set(row.id, row),
    db: { transaction: async (_mode: string, _t: unknown, run: () => Promise<void>) => run() },
  };
  return fake as unknown as Parameters<typeof readOrKept>[0] & object;
}

const offline = () => Promise.reject(new ApiError(0, "network", "No response."));

describe("lecture gardée sur l'appareil (« Mon horaire », EDT.4b)", () => {
  it("garde la lecture en ligne et la rend, datée, quand le réseau manque", async () => {
    const kept = table();
    const online = await readOrKept(kept, "mine", async () => ({ lessons: 3 }));
    expect(online).toEqual({ value: { lessons: 3 }, keptAt: null });
    await new Promise((resolve) => setTimeout(resolve, 0));

    const later = await readOrKept(kept, "mine", offline);
    expect(later.value).toEqual({ lessons: 3 });
    expect(later.keptAt).toBeGreaterThan(0);
  });

  it("une réponse arrivée en retard ne remplace pas une lecture plus récente", async () => {
    const kept = table();
    await keep(kept, "mine", "récente", 2_000);
    await keep(kept, "mine", "ancienne", 1_000);
    expect((await readOrKept(kept, "mine", offline)).value).toBe("récente");
  });

  it("sans copie, ou pour une vraie erreur du serveur, l'erreur remonte", async () => {
    await expect(readOrKept(table(), "mine", offline)).rejects.toThrow();
    const kept = table();
    await keep(kept, "mine", "gardée");
    const refused = () => Promise.reject(new ApiError(403, "module_missing", "No."));
    await expect(readOrKept(kept, "mine", refused)).rejects.toMatchObject({ status: 403 });
  });
});
