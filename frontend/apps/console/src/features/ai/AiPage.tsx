// Page « IA » de la console (IA.1.2, maquette `console/ia`) : dépense du mois face au plafond,
// alertes, par école, par usage ; en mode réel, réglages, prix des modèles et réglage d'un usage.
// Droit `platform.ai.manage` ; le serveur vérifie et écrit chaque changement au journal.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatMonth, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  Kpi,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Switch,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { formatMicro, microInput, parseMicro } from "./money";

type Overview = Schemas["AiOverview"];
type UseRow = Overview["uses"][number];
type Price = NonNullable<Overview["settings"]>["prices"][number];

const percent = (value: number | null | undefined) => (value == null ? "—" : `${value} %`);

export function AiPage() {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const overview = useQuery({
    queryKey: keys.ai,
    queryFn: () => call(api.GET("/api/console/ai/")),
  });
  const [editing, setEditing] = useState<UseRow | Price | null>(null);
  const saved = (data: Overview) => client.setQueryData(keys.ai, data);

  if (overview.isPending) return <Skeleton label={t("common.loading")} />;
  if (overview.isError) {
    return <Banner tone="due">{errorMessage(overview.error, t)}</Banner>;
  }
  const data = overview.data;
  const nf = (value: number) => value.toLocaleString(i18n.language);

  return (
    <>
      <PageHeader
        title={t("console.ai.title")}
        subtitle={t("console.ai.subtitle", {
          month: formatMonth(data.month.slice(0, 7), i18n.language),
        })}
      />
      <div className="grid grid-cols-2 gap-3.5 min-[820px]:grid-cols-4">
        <Kpi
          label={t("console.ai.spent")}
          value={formatMicro(data.spent_micro)}
          sub={
            data.cap_micro
              ? t("console.ai.ofCap", {
                  cap: formatMicro(data.cap_micro),
                  percent: Math.floor((data.spent_micro * 100) / data.cap_micro),
                })
              : t("console.ai.demoSpent")
          }
        >
          {data.cap_micro ? (
            <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-line-soft">
              <i
                className="block h-full rounded-full bg-brand"
                style={{ width: `${Math.min(100, (data.spent_micro * 100) / data.cap_micro)}%` }}
              />
            </div>
          ) : null}
        </Kpi>
        <Kpi
          label={t("console.ai.calls")}
          value={nf(data.calls)}
          sub={t("console.ai.callsSub", { refused: data.refused, errors: data.errors })}
        />
        <Kpi
          label={t("console.ai.kept")}
          value={percent(data.kept_percent)}
          sub={t("console.ai.keptSub")}
        />
        <Kpi
          label={t("console.ai.schoolsWithAi")}
          value={data.schools_with_ai}
          sub={t("console.ai.paused", { count: data.schools_paused })}
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t("console.ai.alerts")}</CardTitle>
        </CardHeader>
        <ul className="m-0 list-none p-0">
          {data.alerts.length === 0 && (
            <li className="flex items-center gap-2.5 px-4 py-2.5 text-md">
              <span className="size-2.5 rounded-full bg-ok" aria-hidden />
              {t("console.ai.noAlert")}
            </li>
          )}
          {data.alerts.map((alert) => (
            <li
              key={alert.id ?? alert.kind}
              className="flex items-center gap-2.5 border-t border-line px-4 py-2.5 text-md first:border-t-0"
            >
              <span
                className={`size-2.5 flex-none rounded-full ${alert.percent >= 100 ? "bg-due" : "bg-warn"}`}
                aria-hidden
              />
              {alert.kind === "platform_cap" ? (
                <span>{t("console.ai.capAlert", { percent: alert.percent })}</span>
              ) : (
                <span>
                  <Link to={`/schools/${alert.id}`} className="font-bold">
                    {alert.name}
                  </Link>{" "}
                  {t("console.ai.creditsAlert", { percent: alert.percent })}
                </span>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <div
        className={`grid items-start gap-4 ${data.settings ? "min-[1100px]:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" : ""}`}
      >
        <div className="flex min-w-0 flex-col gap-4">
          <SchoolsCard rows={data.schools} />
          <UsesCard rows={data.uses} live={data.live} onEdit={setEditing} />
        </div>
        {data.settings && (
          <div className="flex min-w-0 flex-col gap-4">
            <SettingsCard settings={data.settings} onSaved={saved} />
            <PricesCard prices={data.settings.prices} onEdit={setEditing} />
          </div>
        )}
      </div>
      {editing && "code" in editing && (
        <UseDialog
          row={editing}
          models={data.settings?.prices.map((p) => p.model) ?? []}
          onClose={() => setEditing(null)}
          onSaved={saved}
        />
      )}
      {editing && !("code" in editing) && (
        <PriceDialog price={editing} onClose={() => setEditing(null)} onSaved={saved} />
      )}
    </>
  );
}

function SchoolsCard({ rows }: { rows: Overview["schools"] }) {
  const { t, i18n } = useTranslation();
  const nf = (value: number) => value.toLocaleString(i18n.language);
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("console.ai.bySchool")}</CardTitle>
        <span className="text-sm text-ink-3">{t("console.ai.creditUnit")}</span>
      </CardHeader>
      {rows.length === 0 ? (
        <p className="px-4 py-5 text-ink-3">{t("console.ai.noSchool")}</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("console.ai.school")}</th>
              <th className="text-right">{t("console.ai.granted")}</th>
              <th className="text-right">{t("console.ai.used")}</th>
              <th className="text-right">{t("console.ai.remaining")}</th>
              <th className="text-right">{t("console.ai.callsShort")}</th>
              <th className="text-right">{t("console.ai.keptShort")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link to={`/schools/${row.id}`} className="font-bold">
                    {row.name}
                  </Link>
                  <span className="block text-sm text-ink-3">
                    {row.code} · {t("console.ai.usesCount", { count: row.uses })}
                    {row.paused && ` · ${t("console.ai.pausedTag")}`}
                  </span>
                </td>
                <td className="text-right tabular-nums">{nf(row.granted_credits)}</td>
                <td className="text-right tabular-nums">{nf(row.spent_credits)}</td>
                <td className="text-right tabular-nums">
                  {row.granted_credits > 0 &&
                  row.spent_credits * 100 >= row.granted_credits * 80 ? (
                    <StatusPill tone="warn">{nf(row.remaining_credits)}</StatusPill>
                  ) : (
                    nf(row.remaining_credits)
                  )}
                </td>
                <td className="text-right tabular-nums">{nf(row.calls)}</td>
                <td className="text-right whitespace-nowrap tabular-nums">
                  {percent(row.kept_percent)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function UsesCard({
  rows,
  live,
  onEdit,
}: {
  rows: UseRow[];
  live: boolean;
  onEdit: (row: UseRow) => void;
}) {
  const { t, i18n } = useTranslation();
  const nf = (value: number) => value.toLocaleString(i18n.language);
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("console.ai.byUse")}</CardTitle>
        <span className="text-sm text-ink-3">{t("console.ai.byUseSub")}</span>
      </CardHeader>
      <Table>
        <thead>
          <tr>
            <th>{t("console.ai.use")}</th>
            <th>{t("console.ai.model")}</th>
            <th className="text-right">{t("console.ai.callsShort")}</th>
            <th className="text-right">{t("console.ai.keptShort")}</th>
            <th className="text-right">{t("console.ai.abandoned")}</th>
            <th className="text-right">{t("console.ai.cost")}</th>
            {live && <th />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.code}>
              <td>
                <b>{row.label}</b>
                <span className="block text-sm text-ink-3">
                  {t("console.ai.limits", {
                    module: row.module_label,
                    input: nf(row.max_input_tokens),
                    output: nf(row.max_output_tokens),
                  })}
                </span>
              </td>
              <td className="whitespace-nowrap">
                {row.model}
                {row.changed && (
                  <span className="block text-sm text-ink-3">{t("console.ai.changed")}</span>
                )}
              </td>
              <td className="text-right tabular-nums">{nf(row.calls)}</td>
              <td className="text-right whitespace-nowrap tabular-nums">
                {percent(row.kept_percent)}
              </td>
              <td className="text-right tabular-nums">{nf(row.abandoned)}</td>
              <td className="text-right whitespace-nowrap tabular-nums">
                {formatMicro(row.cost_micro)}
              </td>
              {live && (
                <td>
                  <Button size="sm" variant="outline" onClick={() => onEdit(row)}>
                    {t("console.ai.edit")}
                  </Button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </Table>
      <p className="border-t border-line px-4 py-2.5 text-sm text-ink-3">
        {t("console.ai.useHelp")}
      </p>
    </Card>
  );
}

function SettingsCard({
  settings,
  onSaved,
}: {
  settings: NonNullable<Overview["settings"]>;
  onSaved: (data: Overview) => void;
}) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(settings.enabled);
  const [cap, setCap] = useState(microInput(settings.monthly_cap_micro));
  const [hourly, setHourly] = useState(String(settings.hourly_limit));
  const [done, setDone] = useState(false);
  const capMicro = parseMicro(cap);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/console/ai/", {
          body: {
            enabled,
            monthly_cap_micro: capMicro ?? settings.monthly_cap_micro,
            hourly_limit: Number(hourly),
          },
        }),
      ),
    onSuccess: (data) => {
      setDone(true);
      onSaved(data);
    },
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.ai.settings")}</CardTitle>
      </CardHeader>
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <label htmlFor="ai-enabled">
          <b>{t("console.ai.enabled")}</b>
          <span className="block text-sm text-ink-3">{t("console.ai.enabledHelp")}</span>
        </label>
        <Switch id="ai-enabled" checked={enabled} onCheckedChange={setEnabled} />
      </div>
      <CardContent className="flex flex-col gap-3">
        <Field
          id="ai-cap"
          label={t("console.ai.cap")}
          error={capMicro === null ? t("console.ai.invalidAmount") : undefined}
        >
          {(control) => (
            <Input
              {...control}
              inputMode="decimal"
              value={cap}
              onChange={(e) => setCap(e.target.value)}
            />
          )}
        </Field>
        <Field id="ai-hourly" label={t("console.ai.hourly")}>
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              max={500}
              value={hourly}
              onChange={(e) => setHourly(e.target.value)}
            />
          )}
        </Field>
        {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
        {done && !save.isPending && <Banner tone="ok">{t("console.ai.saved")}</Banner>}
        <Button
          className="w-fit"
          disabled={capMicro === null || save.isPending}
          onClick={() => {
            setDone(false);
            save.mutate();
          }}
        >
          {t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}

function PricesCard({ prices, onEdit }: { prices: Price[]; onEdit: (price: Price) => void }) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("console.ai.prices")}</CardTitle>
        <span className="text-sm text-ink-3">{t("console.ai.pricesUnit")}</span>
      </CardHeader>
      <Table>
        <thead>
          <tr>
            <th>{t("console.ai.model")}</th>
            <th className="text-right">{t("console.ai.input")}</th>
            <th className="text-right">{t("console.ai.output")}</th>
            <th className="text-right">{t("console.ai.cache")}</th>
          </tr>
        </thead>
        <tbody>
          {prices.map((price) => (
            <tr key={price.model}>
              <td>
                <button
                  type="button"
                  className="text-left text-brand underline"
                  onClick={() => onEdit(price)}
                >
                  {price.model}
                </button>
              </td>
              <td className="text-right tabular-nums">{microInput(price.input)}</td>
              <td className="text-right tabular-nums">{microInput(price.output)}</td>
              <td className="text-right tabular-nums">{microInput(price.cache_read)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
      <p className="border-t border-line px-4 py-2.5 text-sm text-ink-3">
        {t("console.ai.pricesHelp")}
      </p>
    </Card>
  );
}

function UseDialog({
  row,
  models,
  onClose,
  onSaved,
}: {
  row: UseRow;
  models: string[];
  onClose: () => void;
  onSaved: (data: Overview) => void;
}) {
  const { t } = useTranslation();
  const [model, setModel] = useState(row.model);
  const [input, setInput] = useState(String(row.max_input_tokens));
  const [output, setOutput] = useState(String(row.max_output_tokens));
  const save = useMutation({
    mutationFn: (reset: boolean) =>
      call(
        api.PUT("/api/console/ai/uses/{code}/", {
          params: { path: { code: row.code } },
          body: reset
            ? {}
            : { model, max_input_tokens: Number(input), max_output_tokens: Number(output) },
        }),
      ),
    onSuccess: (data) => {
      onSaved(data);
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={row.label}
      confirmLabel={t("common.save")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => save.mutate(false)}
      pending={save.isPending}
    >
      <Field id="use-model" label={t("console.ai.model")}>
        {(control) => (
          <Select {...control} value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field id="use-input" label={t("console.ai.maxInput")}>
        {(control) => (
          <Input
            {...control}
            type="number"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
        )}
      </Field>
      <Field id="use-output" label={t("console.ai.maxOutput")}>
        {(control) => (
          <Input
            {...control}
            type="number"
            value={output}
            onChange={(e) => setOutput(e.target.value)}
          />
        )}
      </Field>
      {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
      {row.changed && (
        <Button variant="outline" className="w-fit" onClick={() => save.mutate(true)}>
          {t("console.ai.reset")}
        </Button>
      )}
    </ConfirmDialog>
  );
}

function PriceDialog({
  price,
  onClose,
  onSaved,
}: {
  price: Price;
  onClose: () => void;
  onSaved: (data: Overview) => void;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState({
    input: microInput(price.input),
    output: microInput(price.output),
    cache_read: microInput(price.cache_read),
  });
  const parsed = {
    input: parseMicro(values.input),
    output: parseMicro(values.output),
    cache_read: parseMicro(values.cache_read),
  };
  const valid = Object.values(parsed).every((value) => value !== null);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/console/ai/prices/{model}/", {
          params: { path: { model: price.model } },
          body: {
            input: parsed.input ?? 0,
            output: parsed.output ?? 0,
            cache_read: parsed.cache_read ?? 0,
          },
        }),
      ),
    onSuccess: (data) => {
      onSaved(data);
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={price.model}
      confirmLabel={t("common.save")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => valid && save.mutate()}
      pending={save.isPending}
    >
      <p className="text-sm text-ink-3">{t("console.ai.pricesUnit")}</p>
      {(["input", "output", "cache_read"] as const).map((key) => (
        <Field
          key={key}
          id={`price-${key}`}
          label={t(`console.ai.${key === "cache_read" ? "cache" : key}`)}
          error={parsed[key] === null ? t("console.ai.invalidAmount") : undefined}
        >
          {(control) => (
            <Input
              {...control}
              inputMode="decimal"
              value={values[key]}
              onChange={(e) => setValues({ ...values, [key]: e.target.value })}
            />
          )}
        </Field>
      ))}
      {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
    </ConfirmDialog>
  );
}
