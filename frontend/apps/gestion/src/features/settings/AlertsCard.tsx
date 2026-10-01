// Carte « Alertes au directeur » des paramètres de l'école (M5, 4.2) : écart de caisse par
// devise, annulations par caissier et par jour, heure à laquelle une caisse encore ouverte est
// signalée. Enregistrée avec le reste du formulaire ; lue par le tableau de bord (G3).
import { useTranslation } from "@mwangaza/i18n";
import { type Currency, currencySymbol } from "@mwangaza/money";
import { Card, CardContent, CardHeader, CardTitle, Field, Input } from "@mwangaza/ui";

import type { CardProps } from "./SchoolSettingsPage";

export function AlertsCard({ form }: CardProps) {
  const { t } = useTranslation();
  const errors = form.formState.errors.alerts;
  const currencies = form.watch("enabled_currencies") as Currency[];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.alerts.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.alerts.intro")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {currencies.map((currency) => (
          <Field
            key={currency}
            id={`alerts-difference-${currency}`}
            label={t("settings.alerts.difference", { currency: currencySymbol(currency) })}
            help={t("settings.alerts.differenceHelp")}
            error={errors?.difference?.[currency]?.message}
          >
            {(control) => (
              <Input
                {...control}
                inputMode="decimal"
                className="text-right tabular-nums"
                {...form.register(`alerts.difference.${currency}`)}
              />
            )}
          </Field>
        ))}
        <Field
          id="alerts-cancellations"
          label={t("settings.alerts.cancellations")}
          help={t("settings.alerts.cancellationsHelp")}
          error={errors?.cancellations_per_day?.message}
        >
          {(control) => (
            <Input
              {...control}
              inputMode="numeric"
              className="text-right tabular-nums"
              {...form.register("alerts.cancellations_per_day")}
            />
          )}
        </Field>
        <Field
          id="alerts-closing-time"
          label={t("settings.alerts.closingTime")}
          help={t("settings.alerts.closingTimeHelp")}
          error={errors?.closing_time?.message}
        >
          {(control) => (
            <Input {...control} type="time" {...form.register("alerts.closing_time")} />
          )}
        </Field>
      </CardContent>
    </Card>
  );
}
