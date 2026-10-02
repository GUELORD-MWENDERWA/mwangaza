// Annonces des écoles reliées (H4) : pages de 50, marquées lues à l'affichage.
import { api, call, type Schemas } from "@mwangaza/api";
import { useInfiniteQuery, useMutation } from "@tanstack/react-query";

export type PortalAnnouncement = Schemas["PortalAnnouncement"];

/** Toutes les écoles, ou celle d'une famille (`family`). La 1re page sans `?page=` : c'est
 *  elle que le service worker garde pour un affichage sans réseau. */
export function useAnnouncements(family?: string) {
  return useInfiniteQuery({
    queryKey: ["portal", "announcements", family ?? "all"],
    queryFn: ({ pageParam }) =>
      call(
        api.GET("/api/portal/announcements/", {
          params: { query: { family, page: pageParam > 1 ? pageParam : undefined } },
        }),
      ),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
}

/** « Lue par N familles » dans la Gestion. Sans réseau, l'envoi échoue sans bruit : elles
 *  restent non lues et repartent à la prochaine visite. */
export function useMarkRead() {
  return useMutation({
    mutationFn: (ids: string[]) =>
      call(api.POST("/api/portal/announcements/read/", { body: { ids } })),
  });
}
