// Annonces de la plateforme (5.4.3) : non lues (bandeau, nombre dans le menu), liste, « lue ».
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type PlatformNews = Schemas["PlatformNews"];
export const PAGE_SIZE = 50;
const unreadKey = [...keys.platformNews, "unread"];

/** Non lues par ce compte, la plus récente d'abord ; relues toutes les cinq minutes au plus. */
export function useUnreadNews() {
  return useQuery({
    queryKey: unreadKey,
    queryFn: () =>
      call(api.GET("/api/platform-announcements/", { params: { query: { unread: true } } })),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useNews(page: number) {
  return useQuery({
    queryKey: [...keys.platformNews, page],
    queryFn: () => call(api.GET("/api/platform-announcements/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
}

/** Note des annonces comme lues ; la liste ouverte garde sa pastille « Nouvelle ». */
export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) =>
      call(api.POST("/api/platform-announcements/read/", { body: { ids } })),
    onSettled: () => queryClient.invalidateQueries({ queryKey: unreadKey }),
  });
}
