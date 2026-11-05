// Dépenses (FIN.1, maquette `depenses`) : tout ce que l'école dépense, avec justificatif.
// Le serveur vérifie les droits (saisir, valider — jamais la sienne —, annuler) ; l'écran ne fait
// que masquer. Une dépense n'est jamais effacée : on l'annule avec un motif (elle reste listée).
// Les catégories et le seuil de validation viennent des paramètres de l'école.
import { api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount, parseAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { keys, useMe } from "../../lib/queries";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  type Expense,
  type Filters,
  STATUSES,
  filterQuery,
  toneOf,
  useAddCategory,
  useCategories,
  useExpenseAction,
  useSaveThresholds,
  useThresholds,
} from "./data";

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
const PAGE_SIZE = 50;
const thisMonth = () => new Date().toISOString().slice(0, 7);

type Pending = { expense: Expense; action: "approve" | "reject" | "cancel" } | null;

export function ExpensesPage() {
  const { t, i18n } = useTranslation();
  const me = useMe().data;
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const filters: Filters = {
    month: params.get("month") ?? thisMonth(),
    status: params.get("status") ?? "",
    category: params.get("category") ?? "",
  };
  const query = filterQuery(filters);
  const categories = useCategories();
  const summary = useQuery({
    queryKey: [...keys.expenses, "summary", query],
    queryFn: () => call(api.GET("/api/expenses/summary/", { params: { query } })),
    placeholderData: keepPreviousData,
  });
  const list = useQuery({
    queryKey: [...keys.expenses, query, page],
    queryFn: () =>
      call(
        api.GET("/api/expenses/", {
          params: { query: { ...query, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const thresholds = useThresholds();
  const [pending, setPending] = useState<Pending>(null);
  const [text, setText] = useState("");
  const decide = useExpenseAction(pending?.action ?? "approve");

  if (!me) return null;
  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const canRecord = can(me, ["finance.record_expense"]);
  const canApprove = can(me, ["finance.approve_expense"]);
  const canCancel = can(me, ["finance.cancel_expense"]);
  const canConfigure = can(me, ["finance.configure_fees"]);
  const setFilter = (name: keyof Filters, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next, { replace: true });
    setPage(1);
  };
  const rows: Expense[] = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const totals = summary.data?.by_currency ?? [];
  const waiting = totals.reduce((sum, total) => sum + total.pending_count, 0);
  const cancelled = summary.data?.cancelled ?? [];
  const limits = thresholds.data;
  const monthLabel = new Date(`${filters.month}-01T00:00:00Z`).toLocaleDateString(i18n.language, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });

  const close = () => {
    setPending(null);
    setText("");
    decide.reset();
  };

  return (
    <>
      <PageHeader
        title={t("expenses.title")}
        subtitle={t("expenses.subtitle")}
        actions={
          canRecord && (
            <Button asChild>
              <Link to="/expenses/new">
                <Icon name="plus" size={16} />
                {t("expenses.new")}
              </Link>
            </Button>
          )
        }
      />
      {waiting > 0 && canApprove && limits && (
        <Banner tone="warn">
          <b>{t("expenses.waiting", { count: waiting })}</b>{" "}
          {t("expenses.waitingLimit", {
            usd: money(limits.usd_threshold_minor, "USD"),
            cdf: money(limits.cdf_threshold_minor, "CDF"),
          })}
        </Banner>
      )}
      <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
        <Kpi
          label={t("expenses.kpi.spent", { month: monthLabel })}
          value={totals.map((total) => money(total.spent ?? 0, total.currency)).join(" + ") || "—"}
          className="col-span-2 min-[1000px]:col-span-1"
        />
        <Kpi
          label={t("expenses.kpi.pending")}
          value={waiting}
          tone={waiting ? "warn" : undefined}
          sub={totals
            .filter((total) => total.pending)
            .map((total) => money(total.pending ?? 0, total.currency))
            .join(" + ")}
        />
        <Kpi
          label={t("expenses.kpi.cash")}
          value={
            totals
              .filter((total) => total.cash)
              .map((total) => money(total.cash ?? 0, total.currency))
              .join(" + ") || "—"
          }
        />
        <Kpi
          label={t("expenses.kpi.cancelled")}
          value={cancelled.reduce((sum, item) => sum + item.count, 0)}
          sub={cancelled.map((item) => money(item.total, item.currency)).join(" + ")}
        />
      </div>
      <Card>
        <CardContent className="grid grid-cols-1 gap-2.5 min-[700px]:grid-cols-3">
          <Input
            type="month"
            aria-label={t("expenses.filters.month")}
            value={filters.month}
            onChange={(event) => setFilter("month", event.target.value)}
          />
          <Select
            aria-label={t("expenses.filters.category")}
            value={filters.category}
            onChange={(event) => setFilter("category", event.target.value)}
          >
            <option value="">{t("expenses.filters.allCategories")}</option>
            {(categories.data ?? []).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("expenses.filters.status")}
            value={filters.status}
            onChange={(event) => setFilter("status", event.target.value)}
          >
            <option value="">{t("expenses.filters.allStatuses")}</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`expenses.status.${status}`)}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>
      <Card>
        {!list.data ? (
          <CardContent>
            <Skeleton label={t("common.loading")} />
          </CardContent>
        ) : rows.length === 0 ? (
          <CardContent className="text-ink-3">{t("expenses.empty")}</CardContent>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>{t("expenses.columns.date")}</th>
                <th>{t("expenses.columns.category")}</th>
                <th>{t("expenses.columns.beneficiary")}</th>
                <th>{t("expenses.columns.account")}</th>
                <th className="text-right">{t("expenses.columns.amount")}</th>
                <th>{t("expenses.columns.voucher")}</th>
                <th>{t("expenses.columns.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((expense) => (
                <tr key={expense.id}>
                  <td className="whitespace-nowrap tabular-nums">
                    {formatDay(expense.spent_on, i18n.language)}
                    <span className="block text-xs text-ink-3">{expense.number}</span>
                  </td>
                  <td data-label={t("expenses.columns.category")}>{expense.category_name}</td>
                  <td data-label={t("expenses.columns.beneficiary")} className="min-w-44">
                    <b>{expense.beneficiary}</b>
                    <span className="block text-sm text-ink-3">{expense.reason}</span>
                  </td>
                  <td data-label={t("expenses.columns.account")}>
                    {t(`expenses.account.${expense.account}`)}
                  </td>
                  <td
                    className={`text-right font-bold whitespace-nowrap tabular-nums ${expense.cancelled ? "text-ink-3 line-through" : ""}`}
                    data-label={t("expenses.columns.amount")}
                  >
                    {money(expense.amount_minor, expense.currency)}
                  </td>
                  <td data-label={t("expenses.columns.voucher")}>
                    {expense.has_voucher ? (
                      <a
                        className="font-bold text-lake underline"
                        href={`/api/expenses/${expense.id}/voucher/`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t("expenses.voucher")}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td data-label={t("expenses.columns.status")}>
                    <StatusPill tone={toneOf(expense)}>
                      {t(
                        expense.cancelled
                          ? "expenses.cancelled"
                          : `expenses.status.${expense.status}`,
                      )}
                    </StatusPill>
                    {expense.cancellation_reason && (
                      <span className="block text-xs text-ink-3">
                        {expense.cancellation_reason}
                      </span>
                    )}
                    {expense.decision_note && !expense.cancelled && (
                      <span className="block text-xs text-ink-3">{expense.decision_note}</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap">
                    <div className="flex flex-wrap gap-1.5">
                      {canApprove && expense.status === "pending" && !expense.cancelled && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => setPending({ expense, action: "approve" })}
                          >
                            {t("expenses.approve")}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setPending({ expense, action: "reject" })}
                          >
                            {t("expenses.reject")}
                          </Button>
                        </>
                      )}
                      {canCancel && !expense.cancelled && expense.status !== "rejected" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setPending({ expense, action: "cancel" })}
                        >
                          {t("expenses.cancel")}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
        <Pagination
          page={page}
          hasPrevious={Boolean(list.data?.previous)}
          hasNext={Boolean(list.data?.next)}
          onPage={setPage}
          summary={t("expenses.range", { from, to: from ? from + rows.length - 1 : 0, count })}
        />
      </Card>
      {canConfigure && <Settings />}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && close()}
        title={
          pending ? t(`expenses.dialog.${pending.action}`, { number: pending.expense.number }) : ""
        }
        confirmLabel={pending ? t(`expenses.${pending.action}`) : ""}
        cancelLabel={t("common.cancel")}
        pending={decide.isPending}
        destructive={pending?.action !== "approve"}
        onConfirm={() =>
          pending &&
          decide.mutate({ id: pending.expense.id, text: text.trim() }, { onSuccess: close })
        }
      >
        <Field
          id="expense-text"
          label={t(
            pending?.action === "cancel" ? "expenses.dialog.reason" : "expenses.dialog.note",
          )}
          required={pending?.action === "cancel"}
        >
          {(control) => (
            <Input
              {...control}
              maxLength={200}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}
        </Field>
        {decide.error && (
          <div className="mt-2 text-sm text-due" role="alert">
            {errorMessage(decide.error, t)}
          </div>
        )}
      </ConfirmDialog>
    </>
  );
}

/** Seuil de validation par devise et catégories de l'école (`finance.configure_fees`). */
function Settings() {
  const { t } = useTranslation();
  const thresholds = useThresholds();
  const categories = useCategories();
  const save = useSaveThresholds();
  const add = useAddCategory();
  const [edit, setEdit] = useState<{ usd: string; cdf: string } | null>(null);
  const [name, setName] = useState("");
  const data = thresholds.data;
  if (!data) return null;
  const shown = edit ?? {
    usd: formatAmount(data.usd_threshold_minor, "USD")
      .replace(/[^\d,.\s]/g, "")
      .trim(),
    cdf: formatAmount(data.cdf_threshold_minor, "CDF")
      .replace(/[^\d,.\s]/g, "")
      .trim(),
  };
  const usd = parseAmount(shown.usd, "USD");
  const cdf = parseAmount(shown.cdf, "CDF");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("expenses.settings.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-5 min-[900px]:grid-cols-2">
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (usd === null || cdf === null) return;
            save.mutate(
              { usd_threshold_minor: usd, cdf_threshold_minor: cdf },
              { onSuccess: () => setEdit(null) },
            );
          }}
        >
          <p className="text-sm text-ink-3">{t("expenses.settings.thresholdHelp")}</p>
          <div className="grid grid-cols-2 gap-3">
            <Field id="threshold-usd" label={t("expenses.settings.usd")}>
              {(control) => (
                <Input
                  {...control}
                  inputMode="decimal"
                  value={shown.usd}
                  onChange={(e) => setEdit({ ...shown, usd: e.target.value })}
                />
              )}
            </Field>
            <Field id="threshold-cdf" label={t("expenses.settings.cdf")}>
              {(control) => (
                <Input
                  {...control}
                  inputMode="numeric"
                  value={shown.cdf}
                  onChange={(e) => setEdit({ ...shown, cdf: e.target.value })}
                />
              )}
            </Field>
          </div>
          <Button
            type="submit"
            className="self-start"
            disabled={!edit || usd === null || cdf === null || save.isPending}
          >
            {t("common.save")}
          </Button>
          {save.error && (
            <div className="text-sm text-due" role="alert">
              {errorMessage(save.error, t)}
            </div>
          )}
        </form>
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) add.mutate(name.trim(), { onSuccess: () => setName("") });
          }}
        >
          <div className="flex flex-wrap gap-2">
            {(categories.data ?? []).map((category) => (
              <StatusPill key={category.id} tone={category.is_active ? "info" : "gray"}>
                {category.name}
              </StatusPill>
            ))}
          </div>
          <Field id="category-name" label={t("expenses.settings.addCategory")}>
            {(control) => (
              <div className="flex gap-2">
                <Input
                  {...control}
                  maxLength={80}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <Button type="submit" variant="outline" disabled={!name.trim() || add.isPending}>
                  {t("expenses.settings.add")}
                </Button>
              </div>
            )}
          </Field>
          {add.error && (
            <div className="text-sm text-due" role="alert">
              {errorMessage(add.error, t)}
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
