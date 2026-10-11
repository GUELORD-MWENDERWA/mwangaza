// Tableau de bord du directeur (G3, maquette `tableau-de-bord`) : tout est calculé par le serveur
// (`finance.view_reports`, il vérifie ; le promoteur le voit aussi, en lecture seule). Montants
// par devise, jamais additionnés : la devise principale de l'école en grand, les autres dessous.
// Alertes selon les seuils de l'école (paramètres, M5). Une classe → ses impayés.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDate, formatDay, formatMonth, formatTime, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Kpi,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
  Tag,
  cn,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link } from "react-router";

import { MENU_ITEMS, type MenuKey } from "../../lib/menu";
import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { SetupChecklist } from "./SetupChecklist";

type Dashboard = Schemas["Dashboard"];
type Amount = { currency: string; amount_minor: number; count?: number };

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

/** La devise principale de l'école en grand ; les autres devises (non nulles) dessous. */
function split(amounts: Amount[], main: string) {
  const first = amounts.find((amount) => amount.currency === main) ?? amounts[0];
  const others = amounts
    .filter((amount) => amount !== first && amount.amount_minor)
    .map((amount) => `+ ${money(amount.amount_minor, amount.currency)}`);
  return { value: first ? money(first.amount_minor, first.currency) : "—", others };
}

/** `2026-10-01` → `2026-09` */
function previousMonth(day: string) {
  const [year = 0, month = 1] = day.split("-").map(Number);
  return month === 1 ? `${year - 1}-12` : `${year}-${String(month - 1).padStart(2, "0")}`;
}

/** Recouvrement : vert à partir de 75 %, orange à partir de 50 %, rouge en dessous. */
function tone(percent: number) {
  return percent >= 75 ? "ok" : percent >= 50 ? "warn" : "due";
}

const BAR_COLORS = { ok: "bg-ok", warn: "bg-warn", due: "bg-due" } as const;

function Bar({ percent, className }: { percent: number; className?: string }) {
  return (
    <div className={cn("h-2 overflow-hidden rounded-full bg-gray-50", className)}>
      <div
        className={cn("h-full rounded-full", BAR_COLORS[tone(percent)])}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const dashboard = useQuery({
    queryKey: keys.dashboard,
    queryFn: () => call(api.GET("/api/dashboard/")),
  });
  if (dashboard.isPending) return <Skeleton label={t("common.loading")} />;
  if (dashboard.isError) {
    return <LoadError error={dashboard.error} onRetry={() => void dashboard.refetch()} />;
  }
  const data = dashboard.data;
  const main = school.default_currency;
  const language = i18n.language;
  // « Voir » seulement vers un écran que le compte peut ouvrir.
  const open = (key: MenuKey) => {
    const item = MENU_ITEMS.find((entry) => entry.key === key)!;
    return can(me, item.permissions) ? `/${item.path}` : null;
  };

  const today = split(data.today, main);
  const month = split(data.month, main);
  const overdue = split(data.overdue, main);
  const current = data.month.find((amount) => amount.currency === main)?.amount_minor ?? 0;
  const before = data.previous_month.find((amount) => amount.currency === main)?.amount_minor;
  const change = before ? Math.round(((current - before) * 100) / before) : null;

  return (
    <>
      <PageHeader
        crumbs={formatDay(data.date, language)}
        title={t("dashboard.title")}
        subtitle={
          data.academic_year
            ? t("dashboard.subtitle", { year: data.academic_year })
            : t("dashboard.subtitleNoYear")
        }
      />
      <SetupChecklist />
      <Alerts alerts={data.alerts} open={open} />
      <div className="grid gap-4 min-[560px]:grid-cols-2 min-[1000px]:grid-cols-4">
        <Kpi
          label={t("dashboard.kpi.today")}
          value={today.value}
          sub={[
            ...today.others,
            t("dashboard.kpi.payments", {
              count: data.today.reduce((total, amount) => total + amount.count, 0),
            }),
          ].join(" · ")}
        />
        <Kpi
          label={t("dashboard.kpi.month", { month: formatMonth(data.date.slice(0, 7), language) })}
          value={month.value}
          sub={[
            ...month.others,
            ...(change === null
              ? []
              : [
                  t("dashboard.kpi.change", {
                    arrow: change >= 0 ? "▲" : "▼",
                    percent: Math.abs(change),
                    month: formatMonth(previousMonth(data.date), language),
                  }),
                ]),
          ].join(" · ")}
        />
        <Kpi
          label={t("dashboard.kpi.overdue")}
          value={overdue.value}
          tone={data.overdue_students ? "due" : undefined}
          sub={[
            ...overdue.others,
            t("dashboard.kpi.overdueStudents", { count: data.overdue_students }),
          ].join(" · ")}
        />
        <Kpi
          label={t("dashboard.kpi.recovery")}
          value={data.recovery_percent === null ? "—" : `${data.recovery_percent} %`}
          sub={
            <>
              {t("dashboard.kpi.recoverySub")}
              {data.recovery_percent !== null && (
                <Bar percent={data.recovery_percent} className="mt-2" />
              )}
            </>
          }
        />
      </div>
      <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <DailyChart days={data.daily} main={main} />
        <Enrollment data={data} />
      </div>
      <div className="grid items-start gap-4 min-[1000px]:grid-cols-2">
        <Classes classes={data.classes} />
        <RecentPayments payments={data.recent_payments} timezone={school.timezone} />
      </div>
    </>
  );
}

function AlertBanner({
  tone,
  icon,
  to,
  children,
}: {
  tone: "lamp" | "warn" | "due";
  icon: "undo" | "lock" | "alert";
  to: string | null;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <Banner tone={tone} icon={icon}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1">{children}</span>
        {to && (
          <Button asChild size="sm" variant="outline">
            <Link to={to}>{t("dashboard.see")}</Link>
          </Button>
        )}
      </div>
    </Banner>
  );
}

function Alerts({
  alerts,
  open,
}: {
  alerts: Dashboard["alerts"];
  open: (key: MenuKey) => string | null;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const date = (value: string) => formatDate(value, i18n.language, school.timezone);
  const banners = [
    ...(alerts.pending_cancellations
      ? [
          <AlertBanner key="pending" tone="lamp" icon="undo" to={open("cancellations")}>
            <b>{t("dashboard.alerts.pending", { count: alerts.pending_cancellations })}</b>
          </AlertBanner>,
        ]
      : []),
    ...alerts.unclosed.map((session) => (
      <AlertBanner key={session.id} tone="warn" icon="lock" to={open("closings")}>
        <b>{session.cash_register.name}</b>{" "}
        {t("dashboard.alerts.unclosed", {
          date: date(session.opened_at),
          time: formatTime(session.opened_at, i18n.language, school.timezone),
          cashier: fullName(session.cashier),
        })}
      </AlertBanner>
    )),
    ...alerts.differences.map((line) => (
      <AlertBanner key={line.id} tone="warn" icon="alert" to={open("closings")}>
        <b>{line.cash_session.cash_register.name}</b>{" "}
        {t("dashboard.alerts.difference", {
          amount: money(line.difference_minor, line.currency),
          date: date(line.closed_at),
          cashier: fullName(line.cash_session.cashier),
        })}
      </AlertBanner>
    )),
    ...alerts.cancellations.map((row) => (
      <AlertBanner
        key={`${row.cashier.id}-${row.date}`}
        tone="due"
        icon="undo"
        to={open("cancellations")}
      >
        <b>{fullName(row.cashier)}</b>{" "}
        {t("dashboard.alerts.cancellations", {
          count: row.count,
          date: formatDay(row.date, i18n.language),
        })}
      </AlertBanner>
    )),
  ];
  if (!banners.length) return null;
  return <div className="grid gap-3 min-[1000px]:grid-cols-2">{banners}</div>;
}

function DailyChart({ days, main }: { days: Dashboard["daily"]; main: string }) {
  const { t, i18n } = useTranslation();
  const currencies = days[0]?.amounts.map((amount) => amount.currency) ?? [main];
  const [chosen, setChosen] = useState(main);
  const currency = (currencies.includes(chosen) ? chosen : currencies[0]) as Currency;
  const values: number[] = days.map(
    (day) => day.amounts.find((amount) => amount.currency === currency)?.amount_minor ?? 0,
  );
  const max = Math.max(...values, 0);
  const name = (code: string) => (code === "CDF" ? "FC" : code);
  const day = (index: number) => formatDay(days[index]?.date ?? "", i18n.language).slice(0, 5);
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("dashboard.chart.title")}</CardTitle>
        {currencies.length > 1 && (
          <Segmented
            label={t("dashboard.chart.currency")}
            value={currency}
            onValueChange={setChosen}
            options={currencies.map((code) => ({ value: code, label: name(code) }))}
          />
        )}
      </CardHeader>
      <CardContent>
        <div
          role="img"
          aria-label={t("dashboard.chart.label", {
            currency: name(currency),
            from: formatDay(days[0]?.date ?? "", i18n.language),
            to: formatDay(days.at(-1)?.date ?? "", i18n.language),
            total: formatAmount(
              values.reduce((total, value) => total + value, 0),
              currency,
            ),
          })}
        >
          <p className="text-right text-[.78rem] text-ink-3 tabular-nums">
            {formatAmount(max, currency)}
          </p>
          {/* Aujourd'hui en couleur lampe ; le montant de chaque jour au survol. */}
          <div className="flex h-40 items-end gap-[3px] border-t border-b border-dashed border-line">
            {values.map((value, index) => (
              <div
                key={days[index]?.date}
                title={t("dashboard.chart.bar", {
                  date: formatDay(days[index]?.date ?? "", i18n.language),
                  amount: formatAmount(value, currency),
                })}
                className={cn(
                  "min-w-0 flex-1 rounded-t-[3px]",
                  index === values.length - 1 ? "bg-lamp" : "bg-lake",
                )}
                style={{ height: max ? `${(value * 100) / max}%` : 0 }}
              />
            ))}
          </div>
          <div className="mt-1.5 flex justify-between text-[.78rem] text-ink-3 tabular-nums">
            <span>{day(0)}</span>
            <span>{day(Math.floor(days.length / 2))}</span>
            <span>{day(days.length - 1)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Enrollment({ data }: { data: Dashboard }) {
  const { t, i18n } = useTranslation();
  // Par option ; les classes sans option (éducation de base) par cycle.
  const groups = new Map<string, number>();
  for (const group of data.classes) {
    const label = group.track || t(`cycles.${group.cycle}`);
    groups.set(label, (groups.get(label) ?? 0) + group.enrolled);
  }
  const male = data.enrolled ? (data.male * 100) / data.enrolled : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("dashboard.enrollment.title")}</CardTitle>
        <span className="text-sm text-ink-3">
          {t("dashboard.enrollment.at", { date: formatDay(data.date, i18n.language) })}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-[1.65rem] font-bold tabular-nums">
              {data.enrolled.toLocaleString(i18n.language)}
            </p>
            <p className="text-[.82rem] text-ink-3">{t("dashboard.enrollment.enrolled")}</p>
          </div>
          <svg
            viewBox="0 0 42 42"
            className="size-[110px]"
            role="img"
            aria-label={t("dashboard.enrollment.chart", { male: data.male, female: data.female })}
          >
            <circle
              cx={21}
              cy={21}
              r={15.9}
              fill="none"
              strokeWidth={6}
              className="stroke-gray-50"
            />
            {data.enrolled > 0 && (
              <>
                <circle
                  cx={21}
                  cy={21}
                  r={15.9}
                  fill="none"
                  strokeWidth={6}
                  strokeDasharray={`${male} ${100 - male}`}
                  transform="rotate(-90 21 21)"
                  className="stroke-lake"
                  pathLength={100}
                />
                <circle
                  cx={21}
                  cy={21}
                  r={15.9}
                  fill="none"
                  strokeWidth={6}
                  strokeDasharray={`${100 - male} ${male}`}
                  strokeDashoffset={-male}
                  transform="rotate(-90 21 21)"
                  className="stroke-lamp"
                  pathLength={100}
                />
              </>
            )}
          </svg>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="info">
            {t("dashboard.enrollment.male", { count: data.male })}
          </StatusPill>
          <StatusPill tone="warn">
            {t("dashboard.enrollment.female", { count: data.female })}
          </StatusPill>
        </div>
        {groups.size > 0 && (
          <Table>
            <tbody>
              {[...groups].map(([label, count]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td className="text-right tabular-nums">{count}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function Classes({ classes }: { classes: Dashboard["classes"] }) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("dashboard.classes.title")}</CardTitle>
        <Link to="/unpaid" className="text-sm font-bold text-lake">
          {t("dashboard.classes.all")}
        </Link>
      </CardHeader>
      {classes.length === 0 ? (
        <CardContent className="text-ink-3">{t("dashboard.classes.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("dashboard.classes.class")}</th>
              <th>{t("dashboard.classes.students")}</th>
              <th>{t("dashboard.classes.recovery")}</th>
            </tr>
          </thead>
          <tbody>
            {classes.map((group) => (
              <tr key={group.id}>
                <td>
                  <Link
                    to={`/unpaid?class_group=${group.id}`}
                    aria-label={t("dashboard.classes.open", { name: group.name })}
                    className="font-bold text-ink hover:text-lake"
                  >
                    {group.name}
                  </Link>
                </td>
                <td className="whitespace-nowrap text-ink-2 tabular-nums">
                  {t("dashboard.classes.sexes", { male: group.male, female: group.female })}
                </td>
                <td className="w-[45%]">
                  {group.recovery_percent === null ? (
                    <span className="text-sm text-ink-3">{t("dashboard.classes.none")}</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Bar percent={group.recovery_percent} className="flex-1" />
                      <b className="w-11 text-right tabular-nums">{group.recovery_percent} %</b>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function RecentPayments({
  payments,
  timezone,
}: {
  payments: Dashboard["recent_payments"];
  timezone: string;
}) {
  const { t, i18n } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("dashboard.recent.title")}</CardTitle>
      </CardHeader>
      {payments.length === 0 ? (
        <CardContent className="text-ink-3">{t("dashboard.recent.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("dashboard.recent.time")}</th>
              <th>{t("dashboard.recent.student")}</th>
              <th className="text-right">{t("dashboard.recent.amount")}</th>
              <th>{t("dashboard.recent.register")}</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((payment) => (
              <tr key={payment.id}>
                <td className="text-ink-3 tabular-nums">
                  {formatTime(payment.paid_at, i18n.language, timezone)}
                </td>
                <td>
                  <b>{payment.student.full_name}</b>
                  <span className="block text-sm text-ink-3">{payment.class_group}</span>
                </td>
                <td className="text-right font-bold whitespace-nowrap tabular-nums">
                  {money(payment.received_amount_minor, payment.received_currency)}
                </td>
                <td>
                  <Tag>{payment.cash_register}</Tag>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}
