// Budget et rapports (FIN.3, maquette `budget`) : prévu et dépensé par catégorie, entrées et
// sorties par mois, comptes de l'école. Un tableau par devise, jamais de somme USD + FC. Le
// serveur vérifie les droits (lire : `finance.view_reports`, régler : `finance.manage_budget`) ;
// l'écran ne fait que masquer. Soldes de départ et virements ne s'effacent pas : on les annule.
import { api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import { type Currency, parseAmount } from "@mwangaza/money";
import {
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
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { keys, useMe } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import {
  ACCOUNTS,
  type BudgetReport,
  type Movement,
  money,
  plain,
  toneOf,
  useCancelMovement,
  useMovements,
  useRecordMovement,
  useReport,
  useSaveBudget,
  usage,
} from "./data";

type Section = "budget" | "flows" | "accounts";
const today = () => new Date().toISOString().slice(0, 10);

export function BudgetPage() {
  const { t, i18n } = useTranslation();
  const me = useMe().data;
  const [year, setYear] = useState("");
  const [currency, setCurrency] = useState("");
  const [section, setSection] = useState<Section>("budget");
  const years = useQuery({
    queryKey: keys.years,
    queryFn: () => call(api.GET("/api/academic-years/")),
  });
  const report = useReport(year, currency);
  const movements = useMovements(year, section === "accounts");
  if (!me) return null;
  if (report.isError && !report.data) {
    return <LoadError error={report.error} onRetry={() => void report.refetch()} />;
  }
  const data = report.data;
  const canManage = can(me, ["finance.manage_budget"]);
  const yearId = year || data?.academic_year || "";
  const shown = currency || data?.currency || "";

  return (
    <>
      <PageHeader
        title={t("budget.title")}
        subtitle={t("budget.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label={t("budget.year")}
              value={yearId}
              onChange={(event) => setYear(event.target.value)}
            >
              {(years.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            {data && data.currencies.length > 1 && (
              <Segmented
                label={t("budget.currency")}
                value={shown as Currency}
                options={data.currencies.map((value) => ({ value, label: value }))}
                onValueChange={setCurrency}
              />
            )}
            <Button asChild variant="outline">
              <a href={`/api/budget/export/${yearId ? `?academic_year=${yearId}` : ""}`} download>
                <Icon name="download" size={16} />
                {t("budget.excel")}
              </a>
            </Button>
          </div>
        }
      />
      <Segmented
        label={t("budget.sections.label")}
        value={section}
        options={(["budget", "flows", "accounts"] as const).map((value) => ({
          value,
          label: t(`budget.sections.${value}`),
        }))}
        onValueChange={setSection}
        className="self-start max-[600px]:self-stretch"
      />
      {!data ? (
        <Card>
          <CardContent>
            <Skeleton label={t("common.loading")} />
          </CardContent>
        </Card>
      ) : section === "budget" ? (
        <BudgetSection
          key={`${data.academic_year}${data.currency}`}
          data={data}
          canManage={canManage}
        />
      ) : section === "flows" ? (
        <FlowsSection data={data} lang={i18n.language} />
      ) : (
        <AccountsSection
          data={data}
          canManage={canManage}
          movements={movements.data?.results ?? []}
          loading={movements.isPending}
        />
      )}
    </>
  );
}

function BudgetSection({ data, canManage }: { data: BudgetReport; canManage: boolean }) {
  const { t } = useTranslation();
  const save = useSaveBudget();
  const [edit, setEdit] = useState<Record<string, string> | null>(null);
  const left = data.planned_minor - data.spent_minor;
  const percent = usage(data.planned_minor, data.spent_minor);
  const parsed = (edit ? data.budget : []).map((row) => ({
    category: row.category,
    amount: edit?.[row.category] ? parseAmount(edit[row.category] ?? "", data.currency) : 0,
    before: row.planned_minor,
  }));
  const invalid = parsed.some((line) => line.amount === null);
  return (
    <>
      <div className="grid grid-cols-1 gap-4 min-[700px]:grid-cols-3">
        <Kpi label={t("budget.kpi.planned")} value={money(data.planned_minor, data.currency)} />
        <Kpi
          label={t("budget.kpi.spent")}
          value={money(data.spent_minor, data.currency)}
          sub={percent === null ? undefined : t("budget.kpi.share", { percent })}
        />
        <Kpi
          label={t("budget.kpi.left")}
          value={money(left, data.currency)}
          tone={left < 0 ? "due" : undefined}
        />
      </div>
      <Card>
        <CardHeader className="flex-wrap">
          <CardTitle>{t("budget.byCategory")}</CardTitle>
          {canManage && !edit && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setEdit(
                  Object.fromEntries(
                    data.budget.map((row) => [
                      row.category,
                      row.planned_minor ? plain(row.planned_minor, data.currency) : "",
                    ]),
                  ),
                )
              }
            >
              {t("budget.edit")}
            </Button>
          )}
        </CardHeader>
        {data.budget.length === 0 ? (
          <CardContent className="text-ink-3">{t("budget.noCategory")}</CardContent>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>{t("budget.columns.category")}</th>
                <th className="text-right">{t("budget.columns.planned")}</th>
                <th className="text-right">{t("budget.columns.spent")}</th>
                <th className="text-right">{t("budget.columns.left")}</th>
                <th>{t("budget.columns.usage")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.budget.map((row) => {
                const share = usage(row.planned_minor, row.spent_minor);
                const tone = toneOf(row.planned_minor, row.spent_minor);
                return (
                  <tr key={row.category}>
                    <td>
                      <b>{row.name}</b>
                    </td>
                    <td
                      className="text-right whitespace-nowrap tabular-nums"
                      data-label={t("budget.columns.planned")}
                    >
                      {edit ? (
                        <Input
                          aria-label={t("budget.plannedFor", { name: row.name })}
                          inputMode="decimal"
                          className="ml-auto max-w-40 text-right"
                          value={edit[row.category] ?? ""}
                          onChange={(e) => setEdit({ ...edit, [row.category]: e.target.value })}
                        />
                      ) : (
                        money(row.planned_minor, data.currency)
                      )}
                    </td>
                    <td
                      className="text-right whitespace-nowrap tabular-nums"
                      data-label={t("budget.columns.spent")}
                    >
                      {money(row.spent_minor, data.currency)}
                    </td>
                    <td
                      className={`text-right whitespace-nowrap tabular-nums ${row.spent_minor > row.planned_minor ? "text-due" : ""}`}
                      data-label={t("budget.columns.left")}
                    >
                      {money(row.planned_minor - row.spent_minor, data.currency)}
                    </td>
                    <td className="tabular-nums" data-label={t("budget.columns.usage")}>
                      {share === null ? "—" : `${share} %`}
                    </td>
                    <td>
                      <StatusPill tone={tone}>
                        {t(
                          `budget.state.${tone === "gray" ? "none" : tone === "ok" ? "ok" : tone === "warn" ? "near" : share === null ? "unplanned" : "over"}`,
                        )}
                      </StatusPill>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
        {edit && (
          <CardContent className="flex flex-col gap-3">
            <p className="text-sm text-ink-3">{t("budget.editHelp")}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={invalid || save.isPending}
                onClick={() =>
                  save.mutate(
                    {
                      academic_year: data.academic_year,
                      currency: data.currency,
                      lines: parsed
                        .filter((line) => line.amount !== line.before)
                        .map((line) => ({
                          category: line.category,
                          amount_minor: line.amount ?? 0,
                        })),
                    },
                    { onSuccess: () => setEdit(null) },
                  )
                }
              >
                {t("budget.saveBudget")}
              </Button>
              <Button variant="outline" onClick={() => setEdit(null)}>
                {t("common.cancel")}
              </Button>
            </div>
            {save.error && (
              <div className="text-sm text-due" role="alert">
                {errorMessage(save.error, t)}
              </div>
            )}
          </CardContent>
        )}
      </Card>
    </>
  );
}

function FlowsSection({ data, lang }: { data: BudgetReport; lang: string }) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("budget.byMonth")}</CardTitle>
      </CardHeader>
      {data.months.length === 0 ? (
        <CardContent className="text-ink-3">{t("budget.noMonth")}</CardContent>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("budget.columns.month")}</th>
              <th className="text-right">{t("budget.columns.receipts")}</th>
              <th className="text-right">{t("budget.columns.expenses")}</th>
              <th className="text-right">{t("budget.columns.balance")}</th>
            </tr>
          </thead>
          <tbody>
            {data.months.map((row) => (
              <tr key={row.month}>
                <td className="capitalize">
                  {new Date(`${row.month}T00:00:00Z`).toLocaleDateString(lang, {
                    month: "long",
                    year: "numeric",
                    timeZone: "UTC",
                  })}
                </td>
                <td className="text-right tabular-nums" data-label={t("budget.columns.receipts")}>
                  {money(row.receipts_minor, data.currency)}
                </td>
                <td className="text-right tabular-nums" data-label={t("budget.columns.expenses")}>
                  {money(row.expenses_minor, data.currency)}
                </td>
                <td
                  className={`text-right font-bold tabular-nums ${row.balance_minor < 0 ? "text-due" : ""}`}
                  data-label={t("budget.columns.balance")}
                >
                  {money(row.balance_minor, data.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function AccountsSection({
  data,
  canManage,
  movements,
  loading,
}: {
  data: BudgetReport;
  canManage: boolean;
  movements: Movement[];
  loading: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [adding, setAdding] = useState(false);
  const [cancelling, setCancelling] = useState<Movement | null>(null);
  const [reason, setReason] = useState("");
  const cancel = useCancelMovement();
  const currencies = data.currencies;
  const balance = (account: string, currency: string) =>
    data.accounts.find((row) => row.account === account && row.currency === currency)
      ?.balance_minor;
  const closeCancel = () => {
    setCancelling(null);
    setReason("");
    cancel.reset();
  };
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t("budget.accounts")}</CardTitle>
        </CardHeader>
        <Table stacked>
          <thead>
            <tr>
              <th>{t("budget.columns.account")}</th>
              {currencies.map((currency) => (
                <th key={currency} className="text-right">
                  {currency}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ACCOUNTS.map((account) => (
              <tr key={account}>
                <td>
                  <b>{t(`expenses.account.${account}`)}</b>
                </td>
                {currencies.map((currency) => {
                  const value = balance(account, currency);
                  return (
                    <td
                      key={currency}
                      className={`text-right font-bold tabular-nums ${(value ?? 0) < 0 ? "text-due" : ""}`}
                      data-label={currency}
                    >
                      {value === undefined ? "—" : money(value, currency)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </Table>
        <CardContent className="text-sm text-ink-3">{t("budget.accountsHelp")}</CardContent>
      </Card>
      <Card>
        <CardHeader className="flex-wrap">
          <CardTitle>{t("budget.movements.title")}</CardTitle>
          {canManage && (
            <Button size="sm" onClick={() => setAdding(true)}>
              <Icon name="plus" size={16} />
              {t("budget.movements.new")}
            </Button>
          )}
        </CardHeader>
        {loading ? (
          <CardContent>
            <Skeleton label={t("common.loading")} />
          </CardContent>
        ) : movements.length === 0 ? (
          <CardContent className="text-ink-3">{t("budget.movements.empty")}</CardContent>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>{t("budget.columns.date")}</th>
                <th>{t("budget.movements.kind")}</th>
                <th className="text-right">{t("budget.columns.amount")}</th>
                <th>{t("budget.movements.note")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {movements.map((movement) => (
                <tr key={movement.id}>
                  <td className="whitespace-nowrap tabular-nums">
                    {formatDay(movement.made_on, i18n.language)}
                  </td>
                  <td data-label={t("budget.movements.kind")}>
                    {movement.kind === "opening"
                      ? t("budget.movements.openingOf", {
                          account: t(`expenses.account.${movement.to_account}`),
                        })
                      : t("budget.movements.transferOf", {
                          from: t(`expenses.account.${movement.from_account || "cash"}`),
                          to: t(`expenses.account.${movement.to_account}`),
                        })}
                  </td>
                  <td
                    className={`text-right font-bold whitespace-nowrap tabular-nums ${movement.cancelled ? "text-ink-3 line-through" : ""}`}
                    data-label={t("budget.columns.amount")}
                  >
                    {money(movement.amount_minor, movement.currency)}
                  </td>
                  <td data-label={t("budget.movements.note")}>
                    {movement.note}
                    {movement.cancelled && (
                      <span className="block text-xs text-ink-3">
                        {t("budget.movements.cancelled", { reason: movement.cancel_reason })}
                      </span>
                    )}
                  </td>
                  <td>
                    {canManage && !movement.cancelled && (
                      <Button size="sm" variant="ghost" onClick={() => setCancelling(movement)}>
                        {t("budget.movements.cancel")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      {adding && <MovementDialog currencies={currencies} onClose={() => setAdding(false)} />}
      <ConfirmDialog
        open={cancelling !== null}
        onOpenChange={(open) => !open && closeCancel()}
        title={t("budget.movements.cancelTitle")}
        confirmLabel={t("budget.movements.cancel")}
        cancelLabel={t("common.cancel")}
        pending={cancel.isPending}
        destructive
        confirmDisabled={!reason.trim()}
        onConfirm={() =>
          cancelling &&
          cancel.mutate({ id: cancelling.id, reason: reason.trim() }, { onSuccess: closeCancel })
        }
      >
        <Field id="movement-reason" label={t("budget.movements.reason")} required>
          {(control) => (
            <Input
              {...control}
              maxLength={200}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
        </Field>
        {cancel.error && (
          <div className="mt-2 text-sm text-due" role="alert">
            {errorMessage(cancel.error, t)}
          </div>
        )}
      </ConfirmDialog>
    </>
  );
}

/** Solde de départ d'un compte ou virement d'un compte à un autre (`finance.manage_budget`). */
function MovementDialog({
  currencies,
  onClose,
}: {
  currencies: BudgetReport["currencies"];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const record = useRecordMovement();
  const [kind, setKind] = useState<"opening" | "transfer">("opening");
  const [from, setFrom] = useState<(typeof ACCOUNTS)[number]>("cash");
  const [to, setTo] = useState<(typeof ACCOUNTS)[number]>("bank");
  const [currency, setCurrency] = useState<Currency>(currencies[0] ?? "USD");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [note, setNote] = useState("");
  const minor = parseAmount(amount, currency);
  const valid = minor !== null && minor > 0 && Boolean(date) && (kind === "opening" || from !== to);
  const accountSelect = (
    value: string,
    set: (value: (typeof ACCOUNTS)[number]) => void,
    id: string,
  ) => (
    <Select
      id={id}
      value={value}
      onChange={(event) => set(event.target.value as (typeof ACCOUNTS)[number])}
    >
      {ACCOUNTS.map((account) => (
        <option key={account} value={account}>
          {t(`expenses.account.${account}`)}
        </option>
      ))}
    </Select>
  );
  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("budget.movements.new")}
      confirmLabel={t("common.save")}
      cancelLabel={t("common.cancel")}
      pending={record.isPending}
      confirmDisabled={!valid}
      onConfirm={() =>
        valid &&
        record.mutate(
          {
            kind,
            ...(kind === "transfer" ? { from_account: from } : {}),
            to_account: to,
            amount_minor: minor,
            currency,
            made_on: date,
            note: note.trim(),
          },
          { onSuccess: onClose },
        )
      }
    >
      <div className="grid grid-cols-1 gap-3 min-[500px]:grid-cols-2">
        <Field
          id="movement-kind"
          label={t("budget.movements.kind")}
          className="min-[500px]:col-span-2"
        >
          {(control) => (
            <Select
              {...control}
              value={kind}
              onChange={(event) => setKind(event.target.value as "opening" | "transfer")}
            >
              <option value="opening">{t("budget.movements.opening")}</option>
              <option value="transfer">{t("budget.movements.transfer")}</option>
            </Select>
          )}
        </Field>
        {kind === "transfer" && (
          <Field id="movement-from" label={t("budget.movements.from")}>
            {(control) => accountSelect(from, setFrom, control.id)}
          </Field>
        )}
        <Field
          id="movement-to"
          label={t(kind === "transfer" ? "budget.movements.to" : "budget.columns.account")}
        >
          {(control) => accountSelect(to, setTo, control.id)}
        </Field>
        <Field id="movement-amount" label={t("budget.columns.amount")}>
          {(control) => (
            <Input
              {...control}
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          )}
        </Field>
        <Field id="movement-currency" label={t("budget.currency")}>
          {(control) => (
            <Select
              {...control}
              value={currency}
              onChange={(e) => setCurrency(e.target.value as Currency)}
            >
              {currencies.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field id="movement-date" label={t("budget.columns.date")}>
          {(control) => (
            <Input
              {...control}
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          )}
        </Field>
        <Field
          id="movement-note"
          label={t("budget.movements.note")}
          className="min-[500px]:col-span-2"
        >
          {(control) => (
            <Input
              {...control}
              maxLength={200}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          )}
        </Field>
      </div>
      {kind === "transfer" && from === to && (
        <p className="mt-2 text-sm text-due" role="alert">
          {t("budget.movements.sameAccount")}
        </p>
      )}
      {record.error && (
        <div className="mt-2 text-sm text-due" role="alert">
          {errorMessage(record.error, t)}
        </div>
      )}
    </ConfirmDialog>
  );
}
