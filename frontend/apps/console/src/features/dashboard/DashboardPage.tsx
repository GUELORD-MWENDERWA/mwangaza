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
// Guide pour l'administrateur du serveur, dans le dépôt du projet (PERF.5b).
const OPERATIONS_GUIDE =
  "https://github.com/GUELORD-MWENDERWA/mwangaza/blob/main/docs/exploitation.md";
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
          sub={[
            data.schools.trial > 0 &&
              t("console.dashboard.trialSub", { count: data.schools.trial }),
            data.schools.trial_ending > 0 &&
              t("console.dashboard.endingSub", { count: data.schools.trial_ending }),
            data.schools.suspended > 0 &&
              t("console.dashboard.suspendedLine", { count: data.schools.suspended }),
          ].filter((line): line is string => Boolean(line))}
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
              <HealthRow
                key={check.name}
                status={check.status}
                label={t(`console.health.checks.${check.name}`)}
                value={healthValue(check, t)}
                help={check.name}
              />
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
          <HealthRow
            key={row.key}
            status={row.status}
            label={t(`console.platform.${row.key}`)}
            value={row.value}
            help={row.key}
          />
        ))}
      </ul>
      {platform.containers.length > 0 && (
        <>
          <div className="border-t border-line bg-table-head px-4 py-2.5">
            <p className="text-sm font-bold text-ink-2">{t("console.platform.containers")}</p>
            <p className="text-sm text-ink-3">{t("console.platform.containersHint")}</p>
          </div>
          <ul>
            {platform.containers.map((container) => (
              <HealthRow
                key={container.name}
                status={container.status}
                label={serviceText(t, container.name, "label") ?? container.name}
                role={serviceText(t, container.name, "role")}
                technical={container.name}
                value={t("console.platform.memory", {
                  used: container.used_mb,
                  limit: container.limit_mb,
                  percent: container.percent,
                })}
                alert={
                  container.oom_killed
                    ? t("console.platform.oom")
                    : container.restarted_at
                      ? t("console.platform.restarted", { at: when(container.restarted_at) })
                      : undefined
                }
              />
            ))}
          </ul>
        </>
      )}
      <div className="border-t border-line bg-table-head px-4 py-2.5">
        <p className="text-sm font-bold text-ink-2">{t("console.platform.syncs")}</p>
        <p className="text-sm text-ink-3">{t("console.platform.syncsHint")}</p>
      </div>
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
              <span className="ml-auto text-right text-ink-3">
                {school.last_sync_at
                  ? when(school.last_sync_at)
                  : t("console.platform.neverSynced")}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-line px-4 py-3 text-sm">
        <a
          className="font-bold text-brand underline"
          href={OPERATIONS_GUIDE}
          target="_blank"
          rel="noreferrer"
        >
          {t("console.platform.guide")}
        </a>
      </p>
    </Card>
  );
}

const SERVICES = ["django", "worker", "worker-heavy", "scheduler", "db", "redis", "caddy"] as const;
type Service = (typeof SERVICES)[number];
const isService = (name: string): name is Service => (SERVICES as readonly string[]).includes(name);

// Un service que la console ne connaît pas (nouveau conteneur) s'affiche sous son nom technique.
function serviceText(t: TFunction, service: string, part: "label" | "role") {
  return isService(service) ? t(`console.platform.services.${service}.${part}`) : undefined;
}

type Help = HealthCheck["name"] | "backup" | "copy" | "scheduler" | "print";

// Une ligne de santé : point de couleur, nom, valeur ; pour un conteneur, son rôle en une phrase
// et son nom technique ; et, repliable, « ce que ça veut dire / que faire » (ouvert d'office
// quand ce n'est pas vert, pour ne pas laisser l'administrateur chercher).
function HealthRow(props: {
  status: HealthCheck["status"];
  label: string;
  value: string;
  help?: Help;
  role?: string;
  technical?: string;
  alert?: string;
}) {
  const { t } = useTranslation();
  const { status, label, value, help, role, technical, alert } = props;
  return (
    <li className="border-t border-line px-4 py-2.5 text-md first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="flex items-center gap-2">
          <i aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", DOTS[status])} />
          <span>
            {label}
            {technical && <code className="ml-2 text-sm text-ink-3">{technical}</code>}
          </span>
        </span>
        <span className="ml-auto text-right text-ink-3">{value}</span>
      </div>
      {role && <p className="ml-4 text-sm text-ink-3">{role}</p>}
      {alert && <p className="ml-4 text-sm font-bold text-due">{alert}</p>}
      {help && (
        <details className="group ml-4 mt-1" open={status === "warning" || status === "error"}>
          <summary className="cursor-pointer text-sm font-bold text-brand">
            {t("console.platform.meaning")}
          </summary>
          <p className="mt-1 text-sm text-ink-2">{t(`console.platform.help.${help}.meaning`)}</p>
          <p className="mt-1 text-sm font-bold text-ink-2">{t("console.platform.todo")}</p>
          <p className="text-sm text-ink-2">{t(`console.platform.help.${help}.todo`)}</p>
        </details>
      )}
    </li>
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
