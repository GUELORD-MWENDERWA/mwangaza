// Impayés (G1, maquette `impayes`) : élèves ayant au moins une échéance dépassée non soldée,
// calculés par le serveur (`finance.view_reports`, il vérifie) avec le même solde que la fiche
// élève : réductions déduites, paiements annulés exclus, devises jamais additionnées. Filtres dans
// l'adresse, repris par l'export. Élèves cochés sur la page : leurs situations financières
// imprimées ensemble (4.1.2, une page par élève) ; relances : V1.1.
import { api, call } from "@mwangaza/api";
import { formatDate, formatDay, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Button,
  Card,
  CardContent,
  Checkbox,
  Icon,
  Kpi,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { formatPhone, studentName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { schoolDay } from "../cash/offline";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { type FilterName, ORDERS, OVER_DAYS, type UnpaidRow, exportUrl, filtersOf } from "./data";

const PAGE_SIZE = 50;
// Au-delà, le retard est en rouge (chiffre clé « Retard de plus de 30 jours »).
const LONG_DELAY = 30;

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
/** « USD », « FC » (comme à la caisse). */
const currencyName = (currency: string) => (currency === "CDF" ? "FC" : currency);

export function UnpaidPage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  // Cochés sur la page affichée : oubliés quand la page ou les filtres changent.
  const shown = `${params}#${page}`;
  const [selection, setSelection] = useState({ shown: "", ids: [] as string[] });
  const selected = selection.shown === shown ? selection.ids : [];
  const select = (ids: string[], on: boolean) =>
    setSelection({
      shown,
      ids: on ? [...new Set([...selected, ...ids])] : selected.filter((id) => !ids.includes(id)),
    });
  const filters = filtersOf(params);
  const summary = useQuery({
    queryKey: [...keys.unpaid, "summary", filters],
    queryFn: () => call(api.GET("/api/unpaid/summary/", { params: { query: filters } })),
    placeholderData: keepPreviousData,
  });
  const list = useQuery({
    queryKey: [...keys.unpaid, filters, page],
    queryFn: () =>
      call(
        api.GET("/api/unpaid/", {
          params: { query: { ...filters, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const setFilter = (name: FilterName, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next, { replace: true });
    setPage(1);
  };
  const filtered = Object.keys(filters).length > 0;
  const data = summary.data;
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const query = new URLSearchParams(filters).toString();
  const percent = data?.enrolled ? Math.round((data.students * 100) / data.enrolled) : 0;
  const today = formatDay(schoolDay(school.timezone), i18n.language);

  const choose = (name: FilterName, label: string, options: [string, string][], all?: string) => (
    <Select
      aria-label={label}
      value={params.get(name) ?? ""}
      onChange={(event) => setFilter(name, event.target.value)}
    >
      {all !== undefined && <option value="">{all}</option>}
      {options.map(([value, text]) => (
        <option key={value} value={value}>
          {text}
        </option>
      ))}
    </Select>
  );

  return (
    <>
      <PageHeader
        title={t("unpaid.title")}
        subtitle={t("unpaid.subtitle", { date: today })}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <a
                href={exportUrl(filters, {
                  output: "xlsx",
                  group: "class",
                  pagePerClass: true,
                  phone: true,
                  detail: false,
                })}
                download
              >
                <Icon name="download" size={16} />
                {t("unpaid.excel")}
              </a>
            </Button>
            <Button asChild variant="outline">
              <Link to={`/unpaid/export${query ? `?${query}` : ""}`}>
                <Icon name="print" size={16} />
                {t("unpaid.pdf")}
              </Link>
            </Button>
            <Button variant="outline" disabled>
              <Icon name="bell" size={16} />
              {t("unpaid.reminder")} <Tag lot>V1.1</Tag>
            </Button>
          </div>
        }
      />
      {/* Sur téléphone, les montants (longs) sur toute la largeur, sous les deux compteurs. */}
      <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
        <Kpi
          label={t("unpaid.kpi.students")}
          value={data?.students ?? 0}
          sub={t("unpaid.kpi.enrolled", { count: data?.enrolled ?? 0, percent })}
        />
        {(data?.amounts ?? []).map((amount) => (
          <Kpi
            key={amount.currency}
            label={t("unpaid.kpi.amount", { currency: currencyName(amount.currency) })}
            value={money(amount.overdue_minor, amount.currency)}
            tone={amount.overdue_minor ? "due" : undefined}
            className="col-span-2 max-[999px]:order-2 min-[1000px]:col-span-1"
          />
        ))}
        <Kpi
          label={t("unpaid.kpi.long", { days: LONG_DELAY })}
          value={data?.long_overdue ?? 0}
          tone={data?.long_overdue ? "due" : undefined}
          sub={t("unpaid.kpi.longSub")}
          className="max-[999px]:order-1"
        />
      </div>
      <Card>
        <CardContent className="flex flex-wrap gap-2.5">
          {choose(
            "class_group",
            t("unpaid.filters.class"),
            (data?.class_groups ?? []).map((group) => [
              group.id,
              t("unpaid.filters.classOption", { name: group.name }),
            ]),
            t("unpaid.filters.allClasses"),
          )}
          {choose(
            "fee_type",
            t("unpaid.filters.fee"),
            (data?.fee_types ?? []).map((fee) => [
              fee.id,
              t("unpaid.filters.feeOption", { name: fee.name }),
            ]),
            t("unpaid.filters.allFees"),
          )}
          {choose(
            "installment",
            t("unpaid.filters.installment"),
            (data?.installments ?? []).map((label) => [
              label,
              t("unpaid.filters.installmentOption", { name: label }),
            ]),
            t("unpaid.filters.allInstallments"),
          )}
          {choose(
            "over_days",
            t("unpaid.filters.late"),
            OVER_DAYS.map((days) => [
              days === "0" ? "" : days,
              days === "0"
                ? t("unpaid.filters.lateAll")
                : t("unpaid.filters.lateOver", { count: Number(days) }),
            ]),
          )}
          {choose(
            "currency",
            t("unpaid.filters.currency"),
            (data?.amounts ?? []).map(({ currency }) => [
              currency,
              t("unpaid.filters.currencyOption", { name: currencyName(currency) }),
            ]),
            t("unpaid.filters.allCurrencies"),
          )}
          {choose(
            "order",
            t("unpaid.filters.order"),
            ORDERS.map((order) => [
              order === "amount" ? "" : order,
              t(`unpaid.filters.orders.${order}`),
            ]),
          )}
          <Button
            variant="ghost"
            disabled={!filtered}
            onClick={() => {
              setParams(new URLSearchParams(), { replace: true });
              setPage(1);
            }}
          >
            {t("unpaid.filters.clear")}
          </Button>
        </CardContent>
      </Card>
      <Card>
        {!list.data ? (
          <CardContent>
            <Skeleton label={t("common.loading")} />
          </CardContent>
        ) : rows.length === 0 ? (
          <CardContent className="text-ink-3">
            {filtered ? t("unpaid.emptyFiltered") : t("unpaid.empty")}
          </CardContent>
        ) : (
          <>
            <UnpaidTable rows={rows} selected={selected} onSelect={select} />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-[18px] py-3 text-sm text-ink-3">
              <span>{t("unpaid.selected", { count: selected.length })}</span>
              {selected.length > 0 ? (
                <Button asChild size="sm" variant="outline">
                  <Link
                    to={`/unpaid/statements?${new URLSearchParams(selected.map((id) => ["enrollment", id]))}`}
                  >
                    <Icon name="print" size={16} />
                    {t("unpaid.printSelected")}
                  </Link>
                </Button>
              ) : (
                <Button size="sm" variant="outline" disabled>
                  <Icon name="print" size={16} />
                  {t("unpaid.printSelected")}
                </Button>
              )}
            </div>
          </>
        )}
        <Pagination
          page={page}
          hasPrevious={Boolean(list.data?.previous)}
          hasNext={Boolean(list.data?.next)}
          onPage={setPage}
          summary={t("unpaid.range", {
            from,
            to: from ? from + rows.length - 1 : 0,
            count,
          })}
        />
      </Card>
    </>
  );
}

function UnpaidTable({
  rows,
  selected,
  onSelect,
}: {
  rows: UnpaidRow[];
  selected: string[];
  onSelect: (ids: string[], on: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  return (
    <Table>
      <thead>
        <tr>
          <th className="w-10">
            <Checkbox
              aria-label={t("unpaid.selectPage")}
              checked={
                selected.length === 0 ? false : selected.length === rows.length || "indeterminate"
              }
              onCheckedChange={(checked) =>
                onSelect(
                  rows.map((row) => row.enrollment),
                  checked === true,
                )
              }
            />
          </th>
          <th>{t("unpaid.columns.student")}</th>
          <th>{t("unpaid.columns.detail")}</th>
          <th className="text-right">{t("unpaid.columns.overdue")}</th>
          <th>{t("unpaid.columns.late")}</th>
          <th>{t("unpaid.columns.guardian")}</th>
          <th>{t("unpaid.columns.lastPayment")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const payment = row.last_payment;
          return (
            <tr key={row.enrollment}>
              <td>
                <Checkbox
                  aria-label={t("unpaid.select", { name: studentName(row.student) })}
                  checked={selected.includes(row.enrollment)}
                  onCheckedChange={(checked) => onSelect([row.enrollment], checked === true)}
                />
              </td>
              <td className="min-w-44">
                <Link
                  to={`/students/${row.student.id}/finances`}
                  className="font-bold hover:underline focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
                >
                  {studentName(row.student)}
                </Link>
                <span className="block text-sm text-ink-3">{row.class_group}</span>
              </td>
              <td className="min-w-40 text-sm">
                {row.charges
                  .map((charge) =>
                    charge.label === charge.fee_type_name
                      ? charge.label
                      : `${charge.fee_type_name} ${charge.label}`,
                  )
                  .join(" + ")}
              </td>
              <td className="text-right font-bold whitespace-nowrap text-due tabular-nums">
                {row.amounts
                  .map((amount) => money(amount.overdue_minor, amount.currency))
                  .join(" + ")}
              </td>
              <td>
                <StatusPill tone={row.days_late > LONG_DELAY ? "due" : "warn"}>
                  {t("unpaid.days", { count: row.days_late })}
                </StatusPill>
              </td>
              <td className="text-sm">
                {row.guardian
                  ? [row.guardian.full_name, row.guardian.phone && formatPhone(row.guardian.phone)]
                      .filter(Boolean)
                      .join(" · ")
                  : "—"}
              </td>
              <td className="text-sm whitespace-nowrap text-ink-3 tabular-nums">
                {payment
                  ? `${formatDate(payment.paid_at, i18n.language, school.timezone).slice(0, 5)} · ${money(payment.received_amount_minor, payment.received_currency)}`
                  : "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
