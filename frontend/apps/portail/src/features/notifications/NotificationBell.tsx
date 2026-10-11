// Cloche de l'en-tête (5.5.2, maquette `portail/notifications`) : nombre de non lues, ouvre le
// centre de notifications. Écoute aussi le service worker (`push-sw.js`) : notification reçue
// (la cloche se met à jour), notification touchée (écran lié ouvert ici, sans recharger).
import { useTranslation } from "@mwangaza/i18n";
import { Icon } from "@mwangaza/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useNavigate } from "react-router";

import { notificationsKey, useMarkRead, useUnreadNotifications } from "./data";

type WorkerMessage = { type?: string; id?: string; path?: string };

function useWorkerMessages() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { mutate: markRead } = useMarkRead();
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const onMessage = (event: MessageEvent<WorkerMessage>) => {
      if (event.data?.type === "notification") {
        void queryClient.invalidateQueries({ queryKey: notificationsKey });
      } else if (event.data?.type === "open") {
        if (event.data.id) markRead([event.data.id]);
        void navigate(event.data.path || "/notifications");
      }
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, [queryClient, navigate, markRead]);
}

export function NotificationBell() {
  const { t } = useTranslation();
  const unread = useUnreadNotifications().data?.count ?? 0;
  useWorkerMessages();
  return (
    <Link
      to="/notifications"
      aria-label={
        unread ? t("notifications.bellUnread", { count: unread }) : t("notifications.title")
      }
      className="relative grid size-11 shrink-0 place-items-center rounded-full text-basalt-ink"
    >
      <Icon name="bell" size={22} />
      {unread > 0 && (
        <span
          aria-hidden
          className="absolute top-0.5 right-0 rounded-full bg-lamp px-1.5 text-xs font-bold text-basalt"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
