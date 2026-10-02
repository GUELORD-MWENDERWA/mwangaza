// Clôtures de caisse vues par le comptable (M16, F8, maquette `clotures-caisse`), en lecture
// seule (`finance.view_reports`, le serveur vérifie) : une clôture est immuable. Par mois et par
// caisse : attendu, compté et écart par devise (jamais additionnés), sessions restées ouvertes,
// paiements encaissés hors ligne arrivés après la clôture (hors de l'attendu figé) ; le détail,
// le bordereau (celui du caissier) et l'export Excel. L'alerte au directeur : 4.2.
import { api, call, type Schemas } from "@mwangaza/api";
import {
  formatDate,
  formatDateTime,
  formatMonth,
  formatTime,
  useTranslation,
} from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  Kpi,
  List,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tag,
  cn,
} from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { fullName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useSlipPrint } from "../cash/Closing";
import { schoolDay } from "../cash/offline";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";

type Row = Schemas["CashSessionClosing"];
type CurrencyLine = Row["lines"][number];
const PAGE_SIZE = 50;
const MONTHS = 24;
const TONES = { open: "info", unclosed: "due", ok: "ok", difference: "warn" } as const;

/** « USD », « FC » (comme à la caisse). */
const currencyName = (currency: string) => (currency === "CDF" ? "FC" : currency);
const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
const signed = (minor: number, currency: string) =>
  minor >= 0 ? money(minor, currency) : `− ${money(-minor, currency)}`;

/** Les `count` derniers mois, du mois en cours (`2026-10`) au plus ancien. */
function lastMonths(current: string, count: number): string[] {
  const [year, month] = current.split("-").map(Number) as [number, number];
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(Date.UTC(year, month - 1 - index, 1));
    return date.toISOString().slice(0, 7);
  });
}

/** `ITIG-C1-26-000144 → 000184` : la fin seulement quand le début est le même. */
function receiptRange(first: string | null, last: string | null): string {
  if (!first || !last) return "—";
  if (first === last) return first;
  const cut = first.lastIndexOf("-") + 1;
  const tail = last.startsWith(first.slice(0, cut)) ? last.slice(cut) : last;
  return `${first} → ${tail}`;
}

export function ClosingsPage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const current = schoolDay(school.timezone).slice(0, 7);
  const [month, setMonth] = useState(current);
  const [register, setRegister] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const filters = { month, ...(register ? { cash_register: register } : {}) };
  const summary = useQuery({
    queryKey: [...keys.closings, "summary", filters],
    queryFn: () => call(api.GET("/api/cash-closings/summary/", { params: { query: filters } })),
    placeholderData: keepPreviousData,
  });
  const sessions = useQuery({
    queryKey: [...keys.closings, filters, page],
    queryFn: () =>
      call(
        api.GET("/api/cash-closings/", {
          params: { query: { ...filters, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });

  if (sessions.isError && !sessions.data) {
    return <LoadError error={sessions.error} onRetry={() => void sessions.refetch()} />;
  }
  const results = sessions.data?.results ?? [];
  const shown = selected ?? results[0]?.id ?? null;
  const count = sessions.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const data = summary.data;
  const unclosed = data?.unclosed ?? [];
  const reset = () => {
    setPage(1);
    setSelected(null);
  };

  return (
    <>
      <PageHeader
        title={t("closings.title")}
        subtitle={t("closings.subtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Select
              aria-label={t("closings.period")}
              value={month}
              onChange={(event) => {
                setMonth(event.target.value);
                reset();
              }}
            >
              {lastMonths(current, MONTHS).map((value) => (
                <option key={value} value={value}>
                  {t("closings.periodOption", { month: formatMonth(value, i18n.language) })}
                </option>
              ))}
            </Select>
            <Select
              aria-label={t("closings.register")}
              value={register}
              onChange={(event) => {
                setRegister(event.target.value);
                reset();
              }}
            >
              <option value="">{t("closings.allRegisters")}</option>
              {(data?.registers ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {t("closings.registerOption", { name: item.name })}
                </option>
              ))}
            </Select>
            <Button asChild variant="outline">
              <a href={`/api/cash-closings/export/?${new URLSearchParams(filters)}`} download>
                <Icon name="excel" size={16} />
                {t("closings.excel")}
              </a>
            </Button>
          </div>
        }
      />
      {unclosed.map((item) => (
        <Banner key={item.id} tone="warn" icon="lock">
          <b>{item.cash_register.name}</b>{" "}
          {t("closings.unclosed", {
            date: formatDate(item.opened_at, i18n.language, school.timezone).slice(0, 5),
            cashier: fullName(item.cashier),
          })}
        </Banner>
      ))}
      <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
        <Kpi
          label={t("closings.kpi.sessions", { month: formatMonth(month, i18n.language) })}
          value={data?.sessions ?? 0}
          sub={t("closings.kpi.registers", { count: data?.cash_registers ?? 0 })}
        />
        {(data?.differences ?? []).map((item) => (
          <Kpi
            key={item.currency}
            label={t("closings.kpi.difference", { currency: currencyName(item.currency) })}
            value={signed(item.difference_minor, item.currency)}
            tone={
              item.difference_minor < 0 ? "due" : item.difference_minor > 0 ? "warn" : undefined
            }
            sub={t("closings.kpi.differenceSessions", { count: item.sessions })}
          />
        ))}
        <Kpi
          label={t("closings.kpi.unclosed")}
          value={unclosed.length}
          tone={unclosed.length ? "warn" : undefined}
          sub={t("closings.kpi.unclosedSub")}
        />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card data-guide="closings-list">
          {!sessions.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : results.length === 0 ? (
            <CardContent className="text-ink-3">{t("closings.empty")}</CardContent>
          ) : (
            <SessionTable sessions={results} selected={shown} onSelect={setSelected} />
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(sessions.data?.previous)}
            hasNext={Boolean(sessions.data?.next)}
            onPage={setPage}
            summary={t("closings.range", {
              from,
              to: from ? from + results.length - 1 : 0,
              count,
            })}
          />
        </Card>
        {shown ? (
          <ClosingDetail key={shown} id={shown} />
        ) : (
          <Card>
            <CardContent className="text-ink-3">{t("closings.pick")}</CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

/** Une valeur par devise, l'une sous l'autre (dollars d'abord). */
function PerCurrency({
  lines,
  value,
}: {
  lines: CurrencyLine[];
  value: (line: CurrencyLine) => ReactNode;
}) {
  return (
    <>
      {lines.map((line) => (
        <span key={line.currency} className="block whitespace-nowrap">
          {value(line)}
        </span>
      ))}
    </>
  );
}

function Difference({ line }: { line: CurrencyLine }) {
  if (line.difference_minor === null) return "—";
  const text = signed(line.difference_minor, line.currency);
  return line.difference_minor ? <b className="text-due">{text}</b> : text;
}

function SessionTable({
  sessions,
  selected,
  onSelect,
}: {
  sessions: Row[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const time = (value: string) => formatTime(value, i18n.language, school.timezone);
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("closings.columns.date")}</th>
          <th>{t("closings.columns.register")}</th>
          <th>{t("closings.columns.cashier")}</th>
          <th className="text-right">{t("closings.columns.payments")}</th>
          <th className="text-right">{t("closings.columns.expected")}</th>
          <th className="text-right">{t("closings.columns.counted")}</th>
          <th className="text-right">{t("closings.columns.difference")}</th>
          <th>{t("closings.columns.state")}</th>
        </tr>
      </thead>
      <tbody>
        {sessions.map((session) => {
          const late = session.late.reduce((sum, item) => sum + item.count, 0);
          return (
            <tr key={session.id} aria-selected={session.id === selected}>
              <td>
                <button
                  type="button"
                  onClick={() => onSelect(session.id)}
                  className="cursor-pointer font-bold tabular-nums focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
                >
                  {formatDate(session.opened_at, i18n.language, school.timezone).slice(0, 5)}
                </button>
              </td>
              <td>
                <Tag>{session.cash_register.name}</Tag>
              </td>
              <td className="text-sm">
                {fullName(session.cashier)}
                <span className="block text-ink-3 tabular-nums">
                  {time(session.opened_at)} – {session.closed_at ? time(session.closed_at) : "…"}
                </span>
              </td>
              <td className="num">{session.payments_count}</td>
              <td className="num text-sm">
                <PerCurrency
                  lines={session.lines}
                  value={(line) => money(line.expected_minor, line.currency)}
                />
              </td>
              <td className="num text-sm">
                <PerCurrency
                  lines={session.lines}
                  value={(line) =>
                    line.counted_minor === null ? "—" : money(line.counted_minor, line.currency)
                  }
                />
              </td>
              <td className="num text-sm">
                <PerCurrency lines={session.lines} value={(line) => <Difference line={line} />} />
              </td>
              <td>
                <StatusPill tone={TONES[session.state]}>
                  {t(`closings.states.${session.state}`)}
                </StatusPill>
                {late > 0 && (
                  <span className="mt-1 block text-[.82rem] text-warn">
                    {t("closings.lateShort", { count: late })}
                  </span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function Line({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex-wrap text-sm">
      <span>{label}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}

function ClosingDetail({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [showPayments, setShowPayments] = useState(false);
  const { print, area } = useSlipPrint();
  const detail = useQuery({
    queryKey: [...keys.closings, "detail", id],
    queryFn: () => call(api.GET("/api/cash-closings/{id}/", { params: { path: { id } } })),
  });

  if (detail.isError) {
    return <LoadError error={detail.error} onRetry={() => void detail.refetch()} />;
  }
  const data = detail.data;
  if (!data) {
    return (
      <Card>
        <CardContent>
          <Skeleton label={t("common.loading")} />
        </CardContent>
      </Card>
    );
  }
  const { session, closing } = data;
  const time = (value: string) => formatTime(value, i18n.language, school.timezone);
  const day = (value: string) => formatDate(value, i18n.language, school.timezone);
  const lines: CurrencyLine[] =
    closing?.lines ??
    data.currencies.map((item) => ({
      currency: item.currency,
      expected_minor: item.expected_minor,
      counted_minor: null,
      difference_minor: null,
    }));
  const cancelled = data.cancelled.reduce((sum, row) => sum + row.count, 0);
  const printSlip = () =>
    closing &&
    print({
      session,
      data,
      lines: closing.lines,
      note: closing.note,
      closedAt: closing.closed_at,
      queued: false,
    });

  return (
    <Card>
      {area}
      <CardHeader>
        <CardTitle>
          {t("closings.detail.title", {
            name: session.cash_register.name,
            date: day(session.opened_at),
          })}
        </CardTitle>
        <StatusPill tone={TONES[data.state]}>{t(`closings.states.${data.state}`)}</StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Table>
          <thead>
            <tr>
              <th>{t("closings.columns.currency")}</th>
              <th className="text-right">{t("closings.columns.expected")}</th>
              <th className="text-right">{t("closings.columns.counted")}</th>
              <th className="text-right">{t("closings.columns.difference")}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.currency}>
                <td className="font-bold">{currencyName(line.currency)}</td>
                <td className="num">{money(line.expected_minor, line.currency)}</td>
                <td className="num">
                  {line.counted_minor === null ? "—" : money(line.counted_minor, line.currency)}
                </td>
                <td
                  className={cn(
                    "num font-bold",
                    line.difference_minor === 0 && "text-ok",
                    line.difference_minor && "text-due",
                  )}
                >
                  {line.difference_minor === null
                    ? "—"
                    : signed(line.difference_minor, line.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        {closing?.note && (
          <p className="text-sm">
            <b>{t("closings.detail.note")}</b> {closing.note}
          </p>
        )}
        <List>
          <Line label={t("closings.detail.receipts")}>
            {receiptRange(data.first_receipt, data.last_receipt)}
          </Line>
          <Line label={t("closings.detail.cancelled")}>
            {cancelled
              ? `${cancelled} (${data.cancelled.map((row) => money(row.amount_minor, row.currency)).join(" · ")})`
              : 0}
          </Line>
          {data.cancellations_pending > 0 && (
            <Line label={t("closings.detail.pending")}>
              <b className="text-warn">{data.cancellations_pending}</b>
            </Line>
          )}
          {closing ? (
            <>
              <Line label={t("closings.detail.closed")}>
                {closing.offline
                  ? t("closings.detail.closedOffline", {
                      time: time(closing.closed_at),
                      received: time(closing.received_at),
                    })
                  : time(closing.closed_at)}
              </Line>
              <Line label={t("closings.detail.signedBy")}>{fullName(closing.closed_by)}</Line>
            </>
          ) : (
            <Line label={t("closings.detail.closed")}>
              {t("closings.detail.notClosed", { time: time(session.opened_at) })}
            </Line>
          )}
        </List>
        {data.late_payments.length > 0 && (
          <Banner tone="warn" icon="wifioff">
            {t("closings.detail.late", { count: data.late_payments.length })}
            <List className="mt-2">
              {data.late_payments.map((payment) => (
                <Line
                  key={payment.id}
                  label={`${payment.receipt_number} · ${payment.student.full_name}`}
                >
                  <b>{money(payment.amount_minor, payment.currency)}</b>{" "}
                  {payment.cancelled && (
                    <StatusPill tone="gray">{t("closings.detail.cancelledPill")}</StatusPill>
                  )}
                  <span className="block text-ink-3">
                    {t("closings.detail.lateLine", {
                      paid: formatDateTime(payment.paid_at, i18n.language, school.timezone),
                      received: formatDateTime(payment.received_at, i18n.language, school.timezone),
                    })}
                  </span>
                </Line>
              ))}
            </List>
          </Banner>
        )}
        <div className="flex flex-wrap gap-2">
          {closing && (
            <Button variant="outline" onClick={printSlip}>
              <Icon name="print" size={16} />
              {t("closings.detail.slip")}
            </Button>
          )}
          <Button variant="outline" onClick={() => setShowPayments((value) => !value)}>
            {t(showPayments ? "closings.detail.hidePayments" : "closings.detail.payments")}
          </Button>
        </div>
        {showPayments && <SessionPayments session={session.id} />}
      </CardContent>
    </Card>
  );
}

/** Paiements de la session (liste du serveur, paginée), annulés compris. */
function SessionPayments({ session }: { session: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [page, setPage] = useState(1);
  const payments = useQuery({
    queryKey: [...keys.payments, "session", session, page],
    queryFn: () =>
      call(
        api.GET("/api/payments/", {
          params: { query: { session, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  if (payments.isError && !payments.data) {
    return <LoadError error={payments.error} onRetry={() => void payments.refetch()} />;
  }
  if (!payments.data) return <Skeleton label={t("common.loading")} />;
  const results = payments.data.results;
  if (!results.length)
    return <p className="text-sm text-ink-3">{t("closings.detail.noPayments")}</p>;
  return (
    <div>
      <List>
        {results.map((payment) => (
          <Line key={payment.id} label={`${payment.receipt_number} · ${payment.student.full_name}`}>
            <span className="tabular-nums">
              {formatTime(payment.paid_at, i18n.language, school.timezone)} ·{" "}
            </span>
            <b className={cn(payment.cancelled && "line-through")}>
              {money(payment.received_amount_minor, payment.received_currency)}
            </b>{" "}
            {payment.cancelled && (
              <StatusPill tone="gray">{t("closings.detail.cancelledPill")}</StatusPill>
            )}
          </Line>
        ))}
      </List>
      <Pagination
        page={page}
        hasPrevious={Boolean(payments.data.previous)}
        hasNext={Boolean(payments.data.next)}
        onPage={setPage}
        summary={t("closings.detail.paymentsCount", { count: payments.data.count })}
      />
    </div>
  );
}
