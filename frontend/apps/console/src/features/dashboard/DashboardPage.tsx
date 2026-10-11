// Tableau de bord de la console (5.2, maquette `console/tableau-de-bord`) : tout est calculé par
// le serveur, pour toutes les écoles (super-admin seulement : il vérifie). Montants par devise,
// jamais additionnés : les dollars en grand, les autres devises dessous.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDay, type TFunction, useTranslation } from "@mwangaza/i18n";
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
type Amount = { currency: string; amount_minor: number };

const money = (amount: Amount) => formatAmount(amount.amount_minor, amount.currency as Currency);

const HEALTH_TONES = { ok: "ok", warning: "warn", error: "due", off: "gray" } as const;
const DOTS = { ok: "bg-ok", warning: "bg-warn", error: "bg-due", off: "bg-ink-3" } as const;
const SCHOOL_TONES = { active: "ok", trial: "info", suspended: "due", stopped: "gray" } as const;

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
                className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-[.92rem] first:border-t-0"
              >
                <span className="flex items-center gap-2">
                  <i aria-hidden="true" className={cn("size-2 rounded-full", DOTS[check.status])} />
                  {t(`console.health.checks.${check.name}`)}
                </span>
                <span className="text-ink-3">{healthValue(check, t)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}

function healthValue(check: HealthCheck, t: TFunction): string {
  if (check.status === "off") return t("console.health.off");
  if (check.value === null) return t("console.health.down");
  if (check.name === "workers") return t("console.health.workers", { count: check.value });
  if (check.name === "disk") return t("console.health.disk", { value: check.value });
  return t("console.health.ms", { value: check.value });
}
