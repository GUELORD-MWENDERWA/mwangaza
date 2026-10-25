// Lectures gardées sur l'appareil (notes 8.2.3, « Mon horaire » EDT.4b) : ce que le serveur a
// donné en ligne reste lisible sans réseau. Une lecture plus ancienne que celle gardée (réponse
// arrivée en retard) ne la remplace pas.
import { ApiError } from "@mwangaza/api";
import type { EntityTable } from "dexie";

import type { ReadRow } from "./db";

type Kept = EntityTable<ReadRow, "id">;

export async function keep(table: Kept, id: string, value: unknown, readAt = Date.now()) {
  await table.db.transaction("rw", table, async () => {
    const saved = await table.get(id);
    if ((saved?.readAt ?? 0) <= readAt) await table.put({ id, value, readAt });
  });
}

export async function kept<T>(table: Kept, id: string) {
  return (await table.get(id)) as { value: T; readAt: number } | undefined;
}

/** Pas de réponse du serveur (hors ligne, serveur injoignable) : on retombe sur l'appareil. */
export const isNetworkError = (error: unknown) => error instanceof ApiError && error.status === 0;

/** Lecture en ligne, gardée sur l'appareil ; sans réponse du serveur (ou si `prefer` le
 *  demande), la copie gardée, avec l'heure de sa lecture (`keptAt`, vide pour une lecture
 *  fraîche). Sans table (appareil pas enregistré) : en ligne seulement. */
export async function readOrKept<T>(
  table: Kept | null,
  id: string,
  read: () => Promise<T>,
  prefer: () => Promise<boolean> = async () => false,
): Promise<{ value: T; keptAt: number | null }> {
  if (table && (await prefer())) {
    const local = await kept<T>(table, id);
    if (local) return { value: local.value, keptAt: local.readAt };
  }
  const startedAt = Date.now();
  try {
    const value = await read();
    if (table) void keep(table, id, value, startedAt).catch(() => undefined);
    return { value, keptAt: null };
  } catch (error) {
    const local = table && isNetworkError(error) ? await kept<T>(table, id) : undefined;
    if (local) return { value: local.value, keptAt: local.readAt };
    throw error;
  }
}
