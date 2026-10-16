// Tableau de bord de la console (5.2, maquette `console/tableau-de-bord`) : tout est calculé par
// le serveur, pour toutes les écoles (super-admin seulement : il vérifie). Montants par devise,
// jamais additionnés : les dollars en grand, les autres devises dessous.
import { api, call, type Schemas } from "@mwangaza/api";
import {
  errorMessage,
  formatDateTime,
  formatDay,
  type TFunction,
  useTranslation,
} from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  Kpi,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  cn,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

type HealthCheck = Schemas["HealthCheck"];
type Platform = Schemas["PlatformHealth"];
type Amount = { currency: string; amount_minor: number };

const money = (amount: Amount) => formatAmount(amount.amount_minor, amount.currency as Currency);

const HEALTH_TONES = { ok: "ok", warning: "warn", error: "due", off: "gray" } as const;
const DOTS = { ok: "bg-ok", warning: "bg-warn", error: "bg-due", off: "bg-ink-3" } as const;
const SCHOOL_TONES = {
  active: "ok",
  trial: "info",
  suspended: "due",
  stopped: "gray",
  deleting: "gray",
} as const;

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const dashboard = useQuery({
    queryKey: keys.dashboard,
    queryFn: () => call(api.GET("/api/console/dashboard/")),
    refetchInterval: 60_000,
  });

  if (dashboard.isPending) return <Skeleton label={t("common.loading")} />;
  if (dashboard.isError) {
    return (
      <>
        <Banner tone="due">{errorMessage(dashboard.error, t)}</Banner>
        <Button variant="outline" className="w-fit" onClick={() => void dashboard.refetch()}>
          {t("common.retry")}
        </Button>
      </>
    );
  }
  const data = dashboard.data;
  const [main, ...others] = data.today;

  return (
    <>
      <PageHeader
        title={t("console.dashboard.title")}
        subtitle={t("console.dashboard.subtitle", { day: formatDay(data.day, i18n.language) })}
        actions={
          <StatusPill tone={HEALTH_TONES[data.health.status]}>
            {t(
              data.health.status === "ok"
                ? "console.health.allGood"
                : data.health.status === "warning"
                  ? "console.health.warning"
                  : "console.health.error",
            )}
          </StatusPill>
        }
      />
      <div className="grid grid-cols-2 gap-3.5 min-[820px]:grid-cols-4">
        <Kpi
          label={t("console.dashboard.activeSchools")}
          value={data.schools.active}
          sub={t("console.dashboard.schoolsSub", {
            trial: data.schools.trial,
            ending: data.schools.trial_ending,
            suspended: data.schools.suspended,
          })}
        />
        <Kpi
          label={t("console.dashboard.students")}
          value={data.students.toLocaleString(i18n.language)}
          sub={t("console.dashboard.studentsSub")}
        />
        <Kpi
          label={t("console.dashboard.payments")}
          value={data.payments_today}
          sub={t("console.dashboard.paymentsSub")}
        />
        <Kpi
          label={t("console.dashboard.collected")}
          value={main ? money(main) : "—"}
          sub={others
            .filter((amount) => amount.amount_minor)
            .map((amount) => `+ ${money(amount)}`)
            .join(" · ")}
        />
      </div>
      <div className="grid gap-4 min-[820px]:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>{t("console.dashboard.busiest")}</CardTitle>
          </CardHeader>
          {data.active_schools.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("console.dashboard.noPayment")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t("console.dashboard.school")}</th>
                  <th>{t("console.dashboard.status")}</th>
                  <th className="text-right">{t("console.dashboard.count")}</th>
                  <th className="text-right">{t("console.dashboard.amount")}</th>
                </tr>
              </thead>
              <tbody>
                {data.active_schools.map((school) => (
                  <tr key={school.id}>
                    <td>
                      <b>{school.name}</b>
                      <br />
                      <span className="text-sm text-ink-3">{school.code}</span>
                    </td>
                    <td>
                      <StatusPill tone={SCHOOL_TONES[school.status]}>
                        {t(`console.dashboard.schoolStatus.${school.status}`)}
                      </StatusPill>
                    </td>
                    <td className="text-right tabular-nums">{school.payments}</td>
                    <td className="text-right tabular-nums">
                      {school.today.map((amount, index) => (
                        <span
                          key={amount.currency}
                          className={cn(
                            "block whitespace-nowrap",
                            index > 0 && "text-sm text-ink-3",
                          )}
                        >
                          {index > 0 && "+ "}
                          {money(amount)}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("console.health.title")}</CardTitle>
          </CardHeader>
          <ul>
            {data.health.checks.map((check) => (
              <li
                key={check.name}
                className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-t border-line px-4 py-2.5 text-md first:border-t-0"
              >
                <span className="flex items-center gap-2">
                  <i
                    aria-hidden="true"
                    className={cn("size-2 shrink-0 rounded-full", DOTS[check.status])}
                  />
                  {t(`console.health.checks.${check.name}`)}
                </span>
                <span className="ml-auto text-right text-ink-3">{healthValue(check, t)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <PlatformCard platform={data.platform} />
    </>
  );
}

// Sauvegardes, planificateur et dernière synchronisation de chaque école (4.25) : l'état, pas
// l'historique. Une page sur le serveur tombe avec lui : la surveillance extérieure reste.
function PlatformCard({ platform }: { platform: Platform }) {
  const { t, i18n } = useTranslation();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const when = (value: string | null) =>
    value ? formatDateTime(value, i18n.language, timeZone) : t("console.platform.never");
  const rows = [
    {
      key: "backup",
      status: platform.backup.status,
      value: when(platform.backup.done_at),
    },
    {
      key: "copy",
      status: platform.backup.copied_status,
      value:
        platform.backup.copied_status === "off"
          ? t("console.platform.noCopy")
          : when(platform.backup.copied_at),
    },
    {
      key: "scheduler",
      status: platform.scheduler.status,
      value:
        platform.scheduler.status === "off"
          ? t("console.health.off")
          : t("console.platform.tick", {
              at: when(platform.scheduler.last_tick_at),
              queue: platform.scheduler.queue_size ?? "?",
            }),
    },
    {
      key: "print",
      status: platform.print.status,
      value: t("console.platform.printQueue", {
        queued: platform.print.queued,
        running: platform.print.running,
        wait: Math.round(platform.print.longest_wait_seconds / 60),
      }),
    },
  ] as const;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.platform.title")}</CardTitle>
      </CardHeader>
      <ul>
        {rows.map((row) => (
          <li
            key={row.key}
            className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-t border-line px-4 py-2.5 text-md first:border-t-0"
          >
            <span className="flex items-center gap-2">
              <i
                aria-hidden="true"
                className={cn("size-2 shrink-0 rounded-full", DOTS[row.status])}
              />
              {t(`console.platform.${row.key}`)}
            </span>
            <span className="ml-auto text-right text-ink-3">{row.value}</span>
          </li>
        ))}
      </ul>
      {platform.containers.length > 0 && (
        <>
          <p className="border-t border-line bg-table-head px-4 py-2.5 text-sm font-bold text-ink-2">
            {t("console.platform.containers")}
          </p>
          <ul>
            {platform.containers.map((container) => (
              <li
                key={container.name}
                className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-t border-line px-4 py-2.5 text-md"
              >
                <span className="flex items-center gap-2">
                  <i
                    aria-hidden="true"
                    className={cn("size-2 shrink-0 rounded-full", DOTS[container.status])}
                  />
                  {container.name}
                </span>
                <span className="ml-auto text-right text-ink-3">
                  {t("console.platform.memory", {
                    used: container.used_mb,
                    limit: container.limit_mb,
                    percent: container.percent,
                  })}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="border-t border-line bg-table-head px-4 py-2.5 text-sm font-bold text-ink-2">
        {t("console.platform.syncs")}
      </p>
      {platform.syncs.length === 0 ? (
        <p className="border-t border-line px-4 py-5 text-center text-ink-3">
          {t("console.platform.noSchool")}
        </p>
      ) : (
        <ul>
          {platform.syncs.map((school) => (
            <li
              key={school.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-t border-line px-4 py-2.5 text-md"
            >
              <span>
                {school.name} <span className="text-sm text-ink-3">{school.code}</span>
              </span>
              <span className="ml-auto text-right text-ink-3">{when(school.last_sync_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function healthValue(check: HealthCheck, t: TFunction): string {
  if (check.status === "off") return t("console.health.off");
  if (check.value === null) return t("console.health.down");
  if (check.name === "workers") return t("console.health.workers", { count: check.value });
  if (check.name === "disk" || check.name === "memory") {
    return t("console.health.free", { value: check.value });
  }
  if (check.name === "swap") return t("console.health.swapUsed", { value: check.value });
  return t("console.health.ms", { value: check.value });
}
