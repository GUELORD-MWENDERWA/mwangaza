import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

export type LinkedFamily = Schemas["LinkedFamily"];
export type Child = Schemas["Child"];

export type ChildPayments = Schemas["ChildPayments"];
export type ChildFee = Schemas["ChildFee"];

export const familiesKey = ["portal", "families"] as const;

/** Les familles reliées au compte, une par école, avec leurs enfants (H2). */
export function useFamilies() {
  return useQuery({
    queryKey: familiesKey,
    queryFn: () => call(api.GET("/api/portal/families/")),
  });
}

/** Paiements d'un enfant (H3) : frais dus, solde, paiements et reçus. */
export function useChild(id: string) {
  return useQuery({
    queryKey: ["portal", "child", id],
    queryFn: () => call(api.GET("/api/portal/children/{id}/", { params: { path: { id } } })),
  });
}

/** Reçu PDF d'un paiement, ouvert par le navigateur (session du portail). */
export function receiptUrl(paymentId: string): string {
  return `/api/portal/payments/${paymentId}/receipt/`;
}

/** Données du portail gardées par le service worker pour un affichage sans réseau (H6) :
 *  effacées à la déconnexion (téléphone prêté ou partagé). */
export const OFFLINE_CACHE = "portal-data";

export async function forgetOfflineData() {
  if ("caches" in window) await caches.delete(OFFLINE_CACHE);
}
