import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

export type LinkedFamily = Schemas["LinkedFamily"];
export type Child = Schemas["Child"];

export const familiesKey = ["portal", "families"] as const;

/** Les familles reliées au compte, une par école, avec leurs enfants (H2). */
export function useFamilies() {
  return useQuery({
    queryKey: familiesKey,
    queryFn: () => call(api.GET("/api/portal/families/")),
  });
}

/** Données du portail gardées par le service worker pour un affichage sans réseau (H6) :
 *  effacées à la déconnexion (téléphone prêté ou partagé). */
export const OFFLINE_CACHE = "portal-data";

export async function forgetOfflineData() {
  if ("caches" in window) await caches.delete(OFFLINE_CACHE);
}
