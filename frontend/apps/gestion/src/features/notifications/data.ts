// Notifications (5.5) : non lues (cloche), liste, « lue », préférences du compte, essai.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type AppNotification = Schemas["Notification"];
export type NotificationKind = Schemas["NotificationKindEnum"];
export const PAGE_SIZE = 50;
const unreadKey = [...keys.notifications, "unread"];

/** Non lues de ce compte dans l'école ; relues toutes les cinq minutes, et dès qu'une
 *  notification arrive sur l'appareil (`push-sw.js`). */
export function useUnreadNotifications() {
  return useQuery({
    queryKey: unreadKey,
    queryFn: () => call(api.GET("/api/notifications/", { params: { query: { unread: true } } })),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
    retry: false,
  });
}

export function useNotifications(page: number) {
  return useQuery({
    queryKey: [...keys.notifications, page],
    queryFn: () => call(api.GET("/api/notifications/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
}

/** Celles données, ou toutes sans liste. */
export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) =>
      call(api.POST("/api/notifications/read/", { body: ids ? { ids } : {} })),
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.notifications }),
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: keys.notificationPreferences,
    queryFn: () => call(api.GET("/api/notifications/preferences/")),
  });
}

export function useSavePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (muted: NotificationKind[]) =>
      call(api.PUT("/api/notifications/preferences/", { body: { muted } })),
    onSuccess: (data) => queryClient.setQueryData(keys.notificationPreferences, data),
  });
}

export function useSendTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => call(api.POST("/api/notifications/test/")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.notifications }),
  });
}
