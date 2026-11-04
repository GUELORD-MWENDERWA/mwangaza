// Carte « IA » de la fiche d'une école (IA.1.2, maquette `console/ia`, section « Fiche ») :
// crédits du mois, usages rangés par module (un usage ne se coche qu'avec son module hôte),
// crédits par mois, pause, recharge, derniers appels (jamais leur texte). Droit
// `platform.ai.manage` ; chaque changement va au journal de la plateforme.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Field,
  Input,
  Skeleton,
  StatusPill,
  Switch,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { keys } from "../../lib/queries";

type AiCard = Schemas["AiSchoolCard"];

export function AiSchoolCard({ schoolId }: { schoolId: string }) {
  const { t } = useTranslation();
  const card = useQuery({
    queryKey: [...keys.ai, "school", schoolId],
    queryFn: () =>
      call(api.GET("/api/console/ai/schools/{id}/", { params: { path: { id: schoolId } } })),
  });
  if (card.isPending) return <Skeleton label={t("common.loading")} />;
  if (card.isError) return <Banner tone="due">{errorMessage(card.error, t)}</Banner>;
  return <AiCardBody key={card.dataUpdatedAt} schoolId={schoolId} data={card.data} />;
}

function AiCardBody({ schoolId, data }: { schoolId: string; data: AiCard }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const [chosen, setChosen] = useState(
    data.uses.filter((use) => use.granted).map((use) => use.code),
  );
  const [monthly, setMonthly] = useState(String(data.monthly_credits));
  const [paused, setPaused] = useState(data.paused);
  const [topUp, setTopUp] = useState("");
  const [done, setDone] = useState<"saved" | "topped" | null>(null);
  const path = { params: { path: { id: schoolId } } };
  const refresh = (next: AiCard) => client.setQueryData([...keys.ai, "school", schoolId], next);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/console/ai/schools/{id}/", {
          ...path,
          body: { uses: chosen, monthly_credits: Number(monthly), paused },
        }),
      ),
    onSuccess: (next) => {
      setDone("saved");
      refresh(next);
    },
  });
  const recharge = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/console/ai/schools/{id}/top-up/", {
          ...path,
          body: { credits: Number(topUp) },
        }),
      ),
    onSuccess: (next) => {
      setDone("topped");
      refresh(next);
    },
  });
  const nf = (value: number) => value.toLocaleString(i18n.language);
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const used = data.granted_credits ? (data.spent_credits * 100) / data.granted_credits : 0;
  const modules = [...new Set(data.uses.map((use) => use.module))];
  const error = save.error ?? recharge.error;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.ai.cardTitle")}</CardTitle>
        {data.paused ? (
          <StatusPill tone="warn">{t("console.ai.pausedTag")}</StatusPill>
        ) : chosen.length > 0 && data.has_module ? (
          <StatusPill tone="ok">{t("console.ai.active")}</StatusPill>
        ) : null}
      </CardHeader>
      {!data.has_module && (
        <p className="border-b border-line px-4 py-2.5 text-sm text-ink-3">
          {t("console.ai.noModule")}
        </p>
      )}
      <dl className="grid grid-cols-3 gap-2 px-4 pt-3 [&_dd]:text-lg [&_dd]:font-bold [&_dd]:tabular-nums [&_dt]:text-sm [&_dt]:text-ink-3">
        <div>
          <dt>{t("console.ai.granted")}</dt>
          <dd>{nf(data.granted_credits)}</dd>
        </div>
        <div>
          <dt>{t("console.ai.used")}</dt>
          <dd>{nf(data.spent_credits)}</dd>
        </div>
        <div>
          <dt>{t("console.ai.remaining")}</dt>
          <dd>{nf(data.remaining_credits)}</dd>
        </div>
      </dl>
      <div className="px-4 pt-2 pb-3">
        <div className="h-2 overflow-hidden rounded-full bg-line-soft">
          <i
            className={`block h-full rounded-full ${used >= 80 ? "bg-warn" : "bg-brand"}`}
            style={{ width: `${Math.min(100, used)}%` }}
          />
        </div>
        <p className="mt-1.5 text-sm text-ink-3">{t("console.ai.creditHelp")}</p>
      </div>
      {modules.map((module) => {
        const rows = data.uses.filter((use) => use.module === module);
        return (
          <fieldset key={module} className="m-0 border-0 border-t border-line px-4 py-2.5">
            <legend className="p-0 text-xs font-bold tracking-wider text-ink-3 uppercase">
              {rows[0]?.module_label}
            </legend>
            {rows.map((use) => (
              <div key={use.code} className="flex flex-wrap items-center justify-between gap-x-3">
                <CheckboxField
                  id={`ai-use-${use.code}`}
                  label={use.label}
                  checked={chosen.includes(use.code)}
                  disabled={!use.available && !chosen.includes(use.code)}
                  onCheckedChange={(on) =>
                    setChosen((list) =>
                      on === true ? [...list, use.code] : list.filter((code) => code !== use.code),
                    )
                  }
                />
                <span className="text-sm text-ink-3">
                  {!use.available
                    ? t("console.ai.moduleMissing")
                    : use.calls
                      ? t("console.ai.useStats", {
                          count: use.calls,
                          kept: use.kept_percent ?? 0,
                        })
                      : "—"}
                </span>
              </div>
            ))}
          </fieldset>
        );
      })}
      <CardContent className="flex flex-col gap-3 border-t border-line">
        <Field id="ai-monthly" label={t("console.ai.monthly")}>
          {(control) => (
            <Input
              {...control}
              type="number"
              min={0}
              value={monthly}
              onChange={(e) => setMonthly(e.target.value)}
            />
          )}
        </Field>
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="ai-paused">
            <b>{t("console.ai.pause")}</b>
            <span className="block text-sm text-ink-3">{t("console.ai.pauseHelp")}</span>
          </label>
          <Switch id="ai-paused" checked={paused} onCheckedChange={setPaused} />
        </div>
        {error && <Banner tone="due">{errorMessage(error, t)}</Banner>}
        {done && !error && (
          <Banner tone="ok">
            {t(done === "saved" ? "console.ai.saved" : "console.ai.topped")}
          </Banner>
        )}
        <Button className="w-fit" disabled={save.isPending} onClick={() => save.mutate()}>
          {t("common.save")}
        </Button>
        <div className="flex items-end gap-2">
          <Field id="ai-top-up" label={t("console.ai.topUp")} className="flex-1">
            {(control) => (
              <Input
                {...control}
                type="number"
                min={1}
                value={topUp}
                onChange={(e) => setTopUp(e.target.value)}
              />
            )}
          </Field>
          <Button
            variant="outline"
            disabled={!(Number(topUp) > 0) || recharge.isPending}
            onClick={() => recharge.mutate()}
          >
            {t("console.ai.topUpButton")}
          </Button>
        </div>
      </CardContent>
      <h3 className="m-0 border-t border-line px-4 pt-3 pb-1 text-md font-bold">
        {t("console.ai.lastCalls")}
      </h3>
      {data.last_calls.length === 0 ? (
        <p className="px-4 pb-4 text-sm text-ink-3">{t("console.ai.noCall")}</p>
      ) : (
        <ul className="m-0 list-none p-0">
          {data.last_calls.map((item) => (
            <li key={item.id} className="border-t border-line px-4 py-2 text-md first:border-t-0">
              <b>{item.use_label}</b> · {t(`console.ai.states.${item.state}`)}
              <span className="block text-sm text-ink-3">
                {formatDateTime(item.created_at, i18n.language, timeZone)} · {item.user} ·{" "}
                {item.on_platform
                  ? t("console.ai.onPlatform")
                  : t("console.ai.credits", { count: item.credits })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
