// Notifications du parent (5.5.2) : non lues (cloche), liste par pages de 50, « lue », clé pour
// abonner ce téléphone, essai.
import { api, call, type Schemas } from "@mwangaza/api";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type PortalNotification = Schemas["PortalNotification"];
export const notificationsKey = ["portal", "notifications"] as const;

/** Non lues du compte, toutes écoles mêlées. Lues à l'ouverture, puis seulement quand une
 *  notification arrive sur ce téléphone (`push-sw.js`) : pas de relecture périodique. */
export function useUnreadNotifications() {
  return useQuery({
    queryKey: [...notificationsKey, "unread"],
    queryFn: () =>
      call(api.GET("/api/portal/notifications/", { params: { query: { unread: true } } })),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useNotifications() {
  return useInfiniteQuery({
    queryKey: [...notificationsKey, "list"],
    queryFn: ({ pageParam }) =>
      call(
        api.GET("/api/portal/notifications/", {
          params: { query: { page: pageParam > 1 ? pageParam : undefined } },
        }),
      ),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
}

/** Celles données, ou toutes sans liste. */
export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) =>
      call(api.POST("/api/portal/notifications/read/", { body: ids ? { ids } : {} })),
    onSettled: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  });
}

/** Clé publique pour abonner ce téléphone (vide : le serveur n'envoie pas sur l'écran). */
export function usePreferences() {
  return useQuery({
    queryKey: [...notificationsKey, "preferences"],
    queryFn: () => call(api.GET("/api/portal/notifications/preferences/")),
  });
}

export function useSendTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => call(api.POST("/api/portal/notifications/test/")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  });
}
