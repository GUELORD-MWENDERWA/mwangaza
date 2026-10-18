// Centre de notifications de la Gestion (5.5, maquette `gestion/notifications`) : celles de ce
// compte dans cette école, les plus récentes d'abord ; notifications sur l'écran de cet appareil
// (Web Push) et sortes à recevoir (préférences du compte, toutes ses écoles). En ligne seulement.
import { formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  cn,
  Icon,
  type IconName,
  PageHeader,
  Skeleton,
  StatusPill,
  Switch,
  usePlatform,
} from "@mwangaza/ui";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { errorMessage } from "../../lib/errors";
import { useCurrentMe, type Me } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  type AppNotification,
  type NotificationKind,
  PAGE_SIZE,
  useMarkRead,
  useNotifications,
  usePreferences,
  useSavePreferences,
  useSendTest,
  useUnreadNotifications,
} from "./data";
import { disablePush, enablePush, pushState, type PushState } from "../../lib/push";

// Celles du parent (paiement, annonce, échéance, retard) ne viennent jamais dans la Gestion : là
// pour que chaque sorte ait son icône.
const KIND_ICONS: Record<NotificationKind, IconName> = {
  test: "bell",
  platform_news: "megaphone",
  payment_received: "cash",
  announcement: "megaphone",
  cancellation_request: "undo",
  cash_difference: "alert",
  payment_due: "calendar",
  payment_overdue: "clock",
  register_open: "clock",
  staff_announcement: "megaphone",
  summons: "file",
  discipline_incident: "alert",
  place_offered: "users",
  sensitive_rights: "shield",
  grades_sent: "file",
  grades_returned: "undo",
};

export function NotificationsPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const [page, setPage] = useState(1);
  const list = useNotifications(page);
  const unread = useUnreadNotifications().data?.count ?? 0;
  const markRead = useMarkRead();

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <PageHeader
        title={t("notifications.title")}
        subtitle={t("notifications.subtitle")}
        actions={
          unread > 0 && (
            <Button variant="outline" onClick={() => markRead.mutate(undefined)}>
              {t("notifications.markAll")}
            </Button>
          )
        }
      />
      <div className="grid items-start gap-4 min-[1100px]:grid-cols-2">
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>{t("notifications.received")}</CardTitle>
            {unread > 0 && (
              <span className="text-sm text-ink-3">
                {t("notifications.unread", { count: unread })}
              </span>
            )}
          </CardHeader>
          {!list.data ? (
            <Skeleton label={t("common.loading")} />
          ) : results.length === 0 ? (
            <p className="border-t border-line px-4 py-5 text-ink-3">{t("notifications.empty")}</p>
          ) : (
            results.map((notification) => (
              <NotificationRow key={notification.id} notification={notification} />
            ))
          )}
          {count > PAGE_SIZE && (
            <Pagination
              page={page}
              hasPrevious={Boolean(list.data?.previous)}
              hasNext={Boolean(list.data?.next)}
              onPage={setPage}
              summary={t("notifications.range", { from, to: from + results.length - 1, count })}
            />
          )}
        </Card>
        <div className="flex flex-col gap-4">
          <DeviceCard me={me} />
          <KindsCard me={me} />
        </div>
      </div>
    </>
  );
}

/** Toucher la notification la marque comme lue et ouvre l'écran lié. */
function NotificationRow({ notification }: { notification: AppNotification }) {
  const { t, i18n } = useTranslation();
  const platform = usePlatform().name;
  const school = useCurrentSchool();
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
        "flex w-full cursor-pointer gap-3 border-t border-line px-4 py-3.5 text-left hover:bg-surface",
        isNew && "bg-info-50",
      )}
    >
      <Icon name={KIND_ICONS[notification.kind]} size={20} className="mt-0.5 shrink-0 text-lake" />
      <span className="flex min-w-0 flex-col gap-1">
        <span className="flex flex-wrap items-center gap-2">
          <b>{notification.title}</b>
          {isNew && <StatusPill tone="info">{t("notifications.new")}</StatusPill>}
        </span>
        {notification.body && <span className="text-sm text-ink-2">{notification.body}</span>}
        <span className="text-sm text-ink-3">
          {t(`notifications.kinds.${notification.kind}`, { platform })} ·{" "}
          {formatDateTime(notification.created_at, i18n.language, school.timezone)}
        </span>
      </span>
    </button>
  );
}

const STATE_PILLS = {
  on: "ok",
  off: "gray",
  denied: "due",
  unsupported: "gray",
} as const satisfies Record<PushState, string>;

/** Notifications sur l'écran de cet appareil : chaque appareil (et chaque adresse d'école)
 *  s'active à part ; l'autorisation est demandée par le navigateur. */
function DeviceCard({ me }: { me: Me }) {
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
  const run = (pending: ReturnType<typeof pushState>) => {
    setBusy(true);
    setError(null);
    pending
      .then(setState)
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const help = me.support
    ? t("notifications.device.support")
    : state === "unsupported"
      ? t("notifications.device.unsupported")
      : state === "denied"
        ? t("notifications.device.denied")
        : preferences.data && !publicKey
          ? t("notifications.device.notConfigured")
          : null;
  const canChange = !me.support && Boolean(publicKey) && !busy;
  return (
    <Card>
      <CardHeader>
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

/** Sortes reçues sur l'écran ; une sorte coupée reste dans la liste. */
function KindsCard({ me }: { me: Me }) {
  const { t } = useTranslation();
  const platform = usePlatform().name;
  const preferences = usePreferences();
  const save = useSavePreferences();
  const kinds = preferences.data?.kinds ?? [];
  const muted = preferences.data?.muted ?? [];
  if (preferences.data && kinds.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("notifications.kindsTitle")}</CardTitle>
      </CardHeader>
      {!preferences.data ? (
        <Skeleton label={t("common.loading")} />
      ) : (
        kinds.map((kind) => {
          const label = t(`notifications.kinds.${kind}`, { platform });
          return (
            <label
              key={kind}
              className="flex cursor-pointer items-center justify-between gap-3 border-t border-line px-4 py-3.5"
            >
              <span className="flex flex-col">
                <b>{label}</b>
                <span className="text-sm text-ink-3">{t(`notifications.kindHelp.${kind}`)}</span>
              </span>
              <Switch
                aria-label={label}
                checked={!muted.includes(kind)}
                disabled={Boolean(me.support) || save.isPending}
                onCheckedChange={(on) =>
                  save.mutate(on ? muted.filter((other) => other !== kind) : [...muted, kind])
                }
              />
            </label>
          );
        })
      )}
      {save.isError && (
        <div className="px-4 pb-3">
          <Banner tone="due">{errorMessage(save.error, t)}</Banner>
        </div>
      )}
      <CardFooter>
        <span className="text-sm text-ink-3">{t("notifications.kindsHelp")}</span>
      </CardFooter>
    </Card>
  );
}
