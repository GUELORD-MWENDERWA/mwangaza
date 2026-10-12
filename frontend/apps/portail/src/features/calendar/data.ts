// Calendrier du portail (5.7) : événements des écoles des enfants (pages de 50) et convocations
// des parents, notées « vues » à l'affichage.
import { api, call, type Schemas } from "@mwangaza/api";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type PortalEvent = Schemas["PortalEvent"];
export type PortalSummons = Schemas["PortalSummons"];
const summonsKey = ["portal", "summons"];

/** La 1re page sans `?page=` : c'est elle que le service worker garde pour un affichage sans
 *  réseau. */
export function useCalendar() {
  return useInfiniteQuery({
    queryKey: ["portal", "calendar"],
    queryFn: ({ pageParam }) =>
      call(
        api.GET("/api/portal/calendar/", {
          params: { query: { page: pageParam > 1 ? pageParam : undefined } },
        }),
      ),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
}

/** Convocations à venir ou de la semaine passée, la plus proche d'abord (accueil, calendrier). */
export function useSummons() {
  return useQuery({
    queryKey: summonsKey,
    queryFn: () => call(api.GET("/api/portal/summons/")),
    staleTime: 60_000,
  });
}

/** « Vue le » dans la Gestion. Sans réseau, l'envoi échoue sans bruit et repart à la prochaine
 *  visite. */
export function useMarkSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => call(api.POST("/api/portal/summons/seen/", { body: { ids } })),
    onSuccess: () => client.invalidateQueries({ queryKey: summonsKey }),
  });
}
