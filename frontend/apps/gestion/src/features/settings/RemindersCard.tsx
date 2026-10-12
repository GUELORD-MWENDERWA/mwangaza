// Carte « Relances aux parents » des paramètres de l'école (5.6.2) : notifications d'échéance
// proche et de retard, envoyées chaque matin aux familles qui ont un compte du portail.
// Désactivées tant que l'école ne les active pas. Enregistrée avec le reste du formulaire.
import { useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle, Field, Input, Switch } from "@mwangaza/ui";

import type { CardProps } from "./SchoolSettingsPage";

export function RemindersCard({ form }: CardProps) {
  const { t } = useTranslation();
  const errors = form.formState.errors.reminders;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.reminders.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.reminders.intro")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="reminders-enabled" className="cursor-pointer">
            <b>{t("settings.reminders.enabled")}</b>
            <span className="block text-sm text-ink-3">{t("settings.reminders.enabledHelp")}</span>
          </label>
          <Switch
            id="reminders-enabled"
            checked={form.watch("reminders.enabled")}
            onCheckedChange={(on) => form.setValue("reminders.enabled", on, { shouldDirty: true })}
          />
        </div>
        <Field
          id="reminders-days-before"
          label={t("settings.reminders.daysBefore")}
          help={t("settings.reminders.daysBeforeHelp")}
          error={errors?.days_before?.message}
        >
          {(control) => (
            <Input
              {...control}
              inputMode="numeric"
              className="text-right tabular-nums"
              {...form.register("reminders.days_before")}
            />
          )}
        </Field>
        <Field
          id="reminders-overdue-every"
          label={t("settings.reminders.overdueEvery")}
          help={t("settings.reminders.overdueEveryHelp")}
          error={errors?.overdue_every_days?.message}
        >
          {(control) => (
            <Input
              {...control}
              inputMode="numeric"
              className="text-right tabular-nums"
              {...form.register("reminders.overdue_every_days")}
            />
          )}
        </Field>
      </CardContent>
    </Card>
  );
}
