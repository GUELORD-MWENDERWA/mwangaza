// Cloche de la barre du haut (5.5, maquette `gestion/notifications`) : nombre de non lues, ouvre
// le centre de notifications. Écoute aussi le service worker (`push-sw.js`) : notification reçue
// (la cloche se met à jour), notification touchée (écran lié ouvert ici, sans recharger).
import { useTranslation } from "@mwangaza/i18n";
import { Button, Icon } from "@mwangaza/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useNavigate } from "react-router";

import { keys } from "../../lib/queries";
import { useMarkRead, useUnreadNotifications } from "./data";

type WorkerMessage = { type?: string; id?: string; path?: string };

function useWorkerMessages() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { mutate: markRead } = useMarkRead();
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const onMessage = (event: MessageEvent<WorkerMessage>) => {
      if (event.data?.type === "notification") {
        void queryClient.invalidateQueries({ queryKey: keys.notifications });
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
    <Button asChild variant="outline" size="sm" className="relative ml-auto size-11 p-0">
      <Link
        to="/notifications"
        aria-label={
          unread ? t("notifications.bellUnread", { count: unread }) : t("notifications.title")
        }
      >
        <Icon name="bell" size={18} />
        {unread > 0 && (
          <span
            aria-hidden
            className="absolute -top-1.5 -right-1.5 rounded-full bg-lamp px-1.5 text-xs font-bold text-basalt"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </Link>
    </Button>
  );
}
