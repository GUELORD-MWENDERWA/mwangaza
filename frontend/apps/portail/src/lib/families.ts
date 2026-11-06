import { api, call, type Schemas } from "@mwangaza/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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

/** Conduite d'un enfant (8.5.1b) : cote de chaque période et fautes. */
export function useChildConduct(id: string) {
  return useQuery({
    queryKey: ["portal", "child", id, "conduct"],
    queryFn: () =>
      call(api.GET("/api/portal/children/{id}/conduct/", { params: { path: { id } } })),
  });
}

/** Horaire de la classe de l'enfant (EDT.4b) : la version publiée. */
export function useChildTimetable(id: string) {
  return useQuery({
    queryKey: ["portal", "child", id, "timetable"],
    queryFn: () =>
      call(api.GET("/api/portal/children/{id}/timetable/", { params: { path: { id } } })),
  });
}

/** Présences de l'année d'un enfant (6.6) : totaux, absences, justifications. Sans le module des
 *  présences le serveur répond 404 : l'écran n'affiche alors rien. */
export function useChildAttendance(id: string) {
  return useQuery({
    queryKey: ["portal", "child", id, "attendance"],
    queryFn: () =>
      call(api.GET("/api/portal/children/{id}/attendance/", { params: { path: { id } } })),
    retry: false,
  });
}

/** Le parent justifie une absence : motif et certificat facultatif ; en attente de l'école. */
export function useJustify(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { day: string; reason: string; document: File | null }) => {
      const body = new FormData();
      body.append("starts_on", input.day);
      body.append("ends_on", input.day);
      body.append("reason", input.reason);
      if (input.document) body.append("document", input.document);
      return call(
        api.POST("/api/portal/children/{id}/attendance/justify/", {
          params: { path: { id } },
          body: body as unknown as Schemas["JustificationWriteRequest"],
        }),
      );
    },
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["portal", "child", id, "attendance"] }),
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

export type ChildResults = Schemas["ChildResults"];
export type ChildThread = Schemas["ChildThread"];

/** Notes validées, décision et état du bulletin d'un enfant (8.8). */
export function useChildResults(id: string) {
  return useQuery({
    queryKey: ["portal", "child", id, "results"],
    queryFn: () =>
      call(api.GET("/api/portal/children/{id}/results/", { params: { path: { id } } })),
  });
}

/** Fil de l'enfant avec l'école (8.8). */
export function useChildThread(id: string) {
  return useQuery({
    queryKey: ["portal", "child", id, "thread"],
    queryFn: () => call(api.GET("/api/portal/children/{id}/thread/", { params: { path: { id } } })),
  });
}

/** Le bulletin PDF contrôle le droit à chaque lecture : pas d'adresse de fichier. */
export function reportCardUrl(childId: string): string {
  return `/api/portal/children/${childId}/report-card/`;
}
