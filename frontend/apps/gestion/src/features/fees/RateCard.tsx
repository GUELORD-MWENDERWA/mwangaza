// Taux de l'année (E5) : francs pour 1 dollar, fixe toute l'année. Une correction ajoute une
// ligne avec son motif (obligatoire) ; l'historique garde qui, quand, l'ancien et le nouveau
// taux ; les paiements déjà faits gardent le taux qu'ils ont utilisé. Droit
// `finance.set_exchange_rate` pour saisir.
import { api, call } from "@mwangaza/api";
import { formatDate, formatDateTime, useTranslation } from "@mwangaza/i18n";
import { formatRate, parseRate } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Skeleton,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { applyServerErrors } from "../../lib/errors";
import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe, useSchool } from "../../lib/queries";
import { useRefresh, type Year } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { useExchangeRates } from "./data";

export function RateCard({ year }: { year: Year }) {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const school = useSchool().data;
  const rates = useExchangeRates(year.id);
  const refresh = useRefresh();
  const [general, setGeneral] = useState<string | null>(null);
  const form = useForm({ defaultValues: { rate: "", reason: "" } });
  const current = rates.data?.[0];
  const save = useMutation({
    mutationFn: (body: { rate: string; reason: string }) =>
      call(api.POST("/api/exchange-rates/", { body: { ...body, academic_year: year.id } })),
    onSuccess: async () => {
      await refresh(keys.exchangeRates);
      form.reset();
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["rate", "reason"], form.setError, t)),
  });
  const timeZone = school?.timezone ?? "Africa/Lubumbashi";
  const bothCurrencies = ["USD", "CDF"].every((code) =>
    school?.enabled_currencies.includes(code as "USD" | "CDF"),
  );
  const { errors } = form.formState;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("fees.rate.title")}</CardTitle>
        <span className="text-sm text-ink-3">{year.name}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!bothCurrencies ? (
          <p className="text-ink-3">{t("fees.rate.singleCurrency")}</p>
        ) : rates.isPending ? (
          <Skeleton label={t("common.loading")} />
        ) : rates.isError ? (
          <LoadError error={rates.error} onRetry={() => void rates.refetch()} />
        ) : (
          <>
            {current ? (
              <div>
                <p className="num text-2xl font-bold">
                  {t("fees.rate.value", { rate: formatRate(current.rate) })}
                </p>
                <p className="text-sm text-ink-3">
                  {current.set_by
                    ? t("fees.rate.setBy", {
                        name: fullName(current.set_by),
                        date: formatDateTime(current.set_at, i18n.language, timeZone),
                      })
                    : t("fees.rate.setAt", {
                        date: formatDateTime(current.set_at, i18n.language, timeZone),
                      })}
                </p>
              </div>
            ) : (
              <p className="text-ink-3">{t("fees.rate.none", { year: year.name })}</p>
            )}
            {can(me, ["finance.set_exchange_rate"]) && (
              <form
                noValidate
                className="flex flex-col gap-3"
                onSubmit={form.handleSubmit((values) => {
                  setGeneral(null);
                  const rate = parseRate(values.rate);
                  if (!rate) {
                    form.setError("rate", { message: t("fees.rate.invalid") });
                    return;
                  }
                  if (current && !values.reason.trim()) {
                    form.setError("reason", { message: t("fieldErrors.reason_required") });
                    return;
                  }
                  save.mutate({ rate, reason: values.reason.trim() });
                })}
              >
                {general && <Banner tone="due">{general}</Banner>}
                <Field
                  id="rate-value"
                  label={current ? t("fees.rate.newRate") : t("fees.rate.firstRate")}
                  help={t("fees.rate.help")}
                  required
                  error={errors.rate?.message}
                >
                  {(control) => (
                    <Input
                      {...control}
                      inputMode="decimal"
                      className="num"
                      {...form.register("rate")}
                    />
                  )}
                </Field>
                {current && (
                  <Field
                    id="rate-reason"
                    label={t("fees.rate.reason")}
                    required
                    error={errors.reason?.message}
                  >
                    {(control) => (
                      <Input {...control} maxLength={200} {...form.register("reason")} />
                    )}
                  </Field>
                )}
                <Button type="submit" variant="outline" disabled={save.isPending}>
                  {current ? t("fees.rate.correct") : t("fees.rate.submit")}
                </Button>
              </form>
            )}
            {rates.data.length > 1 && (
              <div className="text-sm text-ink-3">
                <p className="font-bold text-ink-2">{t("fees.rate.history")}</p>
                <ul>
                  {rates.data.slice(1).map((rate) => (
                    <li key={rate.id}>
                      {t("fees.rate.historyItem", {
                        date: formatDate(rate.set_at, i18n.language, timeZone),
                        rate: formatRate(rate.rate),
                      })}
                    </li>
                  ))}
                </ul>
                {current?.reason && <p>{t("fees.rate.lastReason", { reason: current.reason })}</p>}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
