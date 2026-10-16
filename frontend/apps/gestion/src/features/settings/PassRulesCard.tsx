// Carte « Réussite et repêchage » des paramètres de l'école (8.4.1) : à quel pourcentage un élève
// réussit et un cours est échoué, quels cours échoués ouvrent un repêchage, combien de cours
// échoués au repêchage font échouer. Valeurs de départ à confirmer par l'école. Enregistrée avec
// le reste du formulaire.
import { useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle, Field, Input } from "@mwangaza/ui";

import type { CardProps } from "./SchoolSettingsPage";

const MODES = ["band", "any_failed"] as const;

export function PassRulesCard({ form }: CardProps) {
  const { t } = useTranslation();
  const errors = form.formState.errors.pass_rules;
  const mode = form.watch("pass_rules.resit_mode");
  const number = (
    name: "pass_percent" | "course_pass_percent" | "resit_floor_percent" | "resit_failures_to_fail",
    label: string,
    help?: string,
  ) => (
    <Field id={`rules-${name}`} label={label} help={help} error={errors?.[name]?.message}>
      {(control) => (
        <Input
          {...control}
          inputMode="numeric"
          className="max-w-32 text-right tabular-nums"
          {...form.register(`pass_rules.${name}`)}
        />
      )}
    </Field>
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.passRules.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.passRules.intro")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {number("pass_percent", t("settings.passRules.passPercent"))}
          {number("course_pass_percent", t("settings.passRules.coursePassPercent"))}
        </div>
        <div className="flex flex-col gap-2" role="radiogroup">
          {MODES.map((value) => (
            <label
              key={value}
              className="flex cursor-pointer items-start gap-3 rounded-md border border-line p-3 has-[:checked]:border-brand"
            >
              <input
                type="radio"
                name="rules-resit-mode"
                className="mt-1"
                checked={mode === value}
                onChange={() =>
                  form.setValue("pass_rules.resit_mode", value, { shouldDirty: true })
                }
              />
              <span>
                <b>{t(`settings.passRules.${value}`)}</b>
                <span className="block text-sm text-ink-3">
                  {t(`settings.passRules.${value}Help`)}
                </span>
              </span>
            </label>
          ))}
        </div>
        {mode === "band" &&
          number(
            "resit_floor_percent",
            t("settings.passRules.floor"),
            t("settings.passRules.floorHelp"),
          )}
        {number(
          "resit_failures_to_fail",
          t("settings.passRules.failures"),
          t("settings.passRules.failuresHelp"),
        )}
      </CardContent>
    </Card>
  );
}
