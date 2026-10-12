// Centre de notifications du parent (5.5.2, maquette `portail/notifications`) : celles de toutes
// ses écoles, les plus récentes d'abord, et les notifications sur l'écran de ce téléphone (Web
// Push). Les sortes à recevoir s'ajouteront ici avec les premières notifications des écoles (5.6).
import { errorMessage, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  cn,
  Icon,
  Skeleton,
  StatusPill,
  usePlatform,
} from "@mwangaza/ui";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { disablePush, enablePush, pushState, type PushState } from "../../lib/push";
import { PortalFrame } from "../home/PortalFrame";
import {
  type PortalNotification,
  useMarkRead,
  useNotifications,
  usePreferences,
  useSendTest,
  useUnreadNotifications,
} from "./data";

export function NotificationsPage() {
  const { t } = useTranslation();
  const list = useNotifications();
  const unread = useUnreadNotifications().data?.count ?? 0;
  const markRead = useMarkRead();
  const items = list.data?.pages.flatMap((page) => page.results) ?? [];

  return (
    <PortalFrame heading={t("notifications.title")} subtitle={t("portal.notifications.subtitle")}>
      <DeviceCard />
      <Card className="overflow-hidden">
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>{t("notifications.received")}</CardTitle>
          {unread > 0 && (
            <Button variant="outline" size="sm" onClick={() => markRead.mutate(undefined)}>
              {t("notifications.markAll")}
            </Button>
          )}
        </CardHeader>
        {list.isPending && <Skeleton label={t("common.loading")} />}
        {list.isError && (
          <div className="flex flex-col gap-3 px-4 pb-4">
            <Banner tone="due">{errorMessage(list.error, t)}</Banner>
            <Button variant="outline" onClick={() => void list.refetch()}>
              {t("common.retry")}
            </Button>
          </div>
        )}
        {list.isSuccess && items.length === 0 && (
          <p className="border-t border-line px-4 py-5 text-ink-3">{t("notifications.empty")}</p>
        )}
        {items.map((item) => (
          <NotificationRow key={item.id} notification={item} />
        ))}
      </Card>
      {list.hasNextPage && (
        <Button
          variant="outline"
          disabled={list.isFetchingNextPage}
          onClick={() => void list.fetchNextPage()}
        >
          {t("portal.notifications.older")}
        </Button>
      )}
    </PortalFrame>
  );
}

/** Toucher la notification la marque comme lue et ouvre l'écran lié. */
function NotificationRow({ notification }: { notification: PortalNotification }) {
  const { t, i18n } = useTranslation();
  const platform = usePlatform().name;
  const navigate = useNavigate();
  const { mutate: markRead } = useMarkRead();
  const isNew = !notification.read_at;
  const open = () => {
    if (isNew) markRead([notification.id]);
    if (notification.url && notification.url !== "/notifications") void navigate(notification.url);
  };
  return (
    <button
      type="button"
      onClick={open}
      className={cn(
        "flex w-full cursor-pointer gap-3 border-t border-line px-4 py-3.5 text-left",
        isNew && "bg-info-50",
      )}
    >
      <Icon name="bell" size={20} className="mt-0.5 shrink-0 text-lake" />
      <span className="flex min-w-0 flex-col gap-1">
        <span className="flex flex-wrap items-center gap-2">
          <b>{notification.title}</b>
          {isNew && <StatusPill tone="info">{t("notifications.new")}</StatusPill>}
        </span>
        {notification.body && <span className="text-sm text-ink-2">{notification.body}</span>}
        <span className="text-sm text-ink-3">
          {t(`notifications.kinds.${notification.kind}`, { platform })} · {notification.school_name}{" "}
          · {formatDateTime(notification.created_at, i18n.language, notification.school_timezone)}
        </span>
      </span>
    </button>
  );
}

const STATE_PILLS = {
  on: "ok",
  off: "gray",
  denied: "warn",
  unsupported: "gray",
} as const satisfies Record<PushState, string>;

/** Notifications sur l'écran de ce téléphone : chaque appareil s'active à part ; l'autorisation
 *  est demandée par le navigateur. */
function DeviceCard() {
  const { t } = useTranslation();
  const preferences = usePreferences();
  const test = useSendTest();
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    void pushState()
      .then(setState)
      .catch(() => setState("unsupported"));
  }, []);

  const publicKey = preferences.data?.vapid_public_key ?? "";
  const run = (pending: Promise<PushState>) => {
    setBusy(true);
    setError(null);
    pending
      .then(setState)
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const help =
    state === "unsupported"
      ? t("notifications.device.unsupported")
      : state === "denied"
        ? t("notifications.device.denied")
        : preferences.data && !publicKey
          ? t("notifications.device.notConfigured")
          : null;
  const canChange = Boolean(publicKey) && !busy;
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>{t("notifications.device.title")}</CardTitle>
        {state && (
          <StatusPill tone={STATE_PILLS[state]}>
            {t(`notifications.device.states.${state}`)}
          </StatusPill>
        )}
      </CardHeader>
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="text-sm text-ink-2">{t("notifications.device.intro")}</p>
        {help && <Banner tone={state === "denied" ? "warn" : "info"}>{help}</Banner>}
        {error !== null && <Banner tone="due">{errorMessage(error, t)}</Banner>}
        {test.isError && <Banner tone="due">{errorMessage(test.error, t)}</Banner>}
        {test.isSuccess && <Banner tone="ok">{t("notifications.device.testSent")}</Banner>}
      </div>
      {(state === "on" || state === "off") && (
        <CardFooter>
          {state === "on" ? (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={!canChange}
                onClick={() => run(disablePush().then(() => "off" as const))}
              >
                {t("notifications.device.disable")}
              </Button>
              <Button
                size="sm"
                disabled={!canChange || test.isPending}
                onClick={() => test.mutate()}
              >
                {t("notifications.device.test")}
              </Button>
            </>
          ) : (
            <Button size="sm" disabled={!canChange} onClick={() => run(enablePush(publicKey))}>
              <Icon name="bell" size={16} />
              {t("notifications.device.enable")}
            </Button>
          )}
        </CardFooter>
      )}
    </Card>
  );
}
