// Carte « Règles de délibération » des paramètres de l'école (8.4.1, NB.4) : le règlement des
// études qui donne la décision proposée. Deux préréglages (donnés par l'API) remplissent le
// formulaire ; l'école corrige ensuite chaque valeur. Enregistrée avec le reste du formulaire.
// Maquette : maquettes/gestion/parametres-ecole.html.
import type { Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Switch,
} from "@mwangaza/ui";

import type { CardProps } from "./SchoolSettingsPage";

type PassRules = Schemas["PassRulesSettings"];
export const RULE_FLAGS = [
  "practical_resit",
  "exclude_repeated_class",
  "application_counts",
] as const;
type Flag = (typeof RULE_FLAGS)[number];
type NumberField = Exclude<keyof PassRules, Flag>;
export type RulesDraft = Record<NumberField, string> & Record<Flag, boolean>;

const PRESETS = ["common", "catholic"] as const;

/** Règles de l'API → valeurs du formulaire (texte pour les nombres). */
export function rulesToForm(rules: PassRules): RulesDraft {
  return Object.fromEntries(
    Object.entries(rules).map(([name, value]) => [
      name,
      typeof value === "boolean" ? value : String(value),
    ]),
  ) as unknown as RulesDraft;
}

/** Valeurs du formulaire → règles de l'API. */
export function rulesFromForm(draft: RulesDraft): PassRules {
  return Object.fromEntries(
    Object.entries(draft).map(([name, value]) => [
      name,
      typeof value === "boolean" ? value : Number(value),
    ]),
  ) as unknown as PassRules;
}

export function PassRulesCard({
  form,
  presets,
}: CardProps & { presets: Record<string, PassRules> }) {
  const { t } = useTranslation();
  const errors = form.formState.errors.pass_rules;
  const number = (name: NumberField, help?: string) => (
    <Field
      id={`rules-${name}`}
      label={t(`settings.passRules.fields.${name}`)}
      help={help}
      error={errors?.[name]?.message}
    >
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
  const flag = (name: Flag) => (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-md border border-line p-3">
      <span>
        <b>{t(`settings.passRules.fields.${name}`)}</b>
        <span className="block text-sm text-ink-3">{t(`settings.passRules.help.${name}`)}</span>
      </span>
      <Switch
        checked={form.watch(`pass_rules.${name}`)}
        onCheckedChange={(checked) =>
          form.setValue(`pass_rules.${name}`, checked, { shouldDirty: true })
        }
      />
    </label>
  );
  const apply = (preset: string) => {
    const values = rulesToForm(presets[preset]!);
    // L'âge limite est propre à chaque niveau : un préréglage ne le change pas.
    for (const [name, value] of Object.entries(values)) {
      if (name === "age_limit") continue;
      form.setValue(`pass_rules.${name as keyof RulesDraft}`, value, { shouldDirty: true });
    }
  };
  const section = (title: string) => <h3 className="mt-2 font-bold text-ink">{title}</h3>;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.passRules.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.passRules.intro")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="flex flex-col divide-y divide-line rounded-md border border-line">
          {PRESETS.filter((preset) => presets[preset]).map((preset) => (
            <li key={preset} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <span className="min-w-0 flex-1 basis-60">
                <b>{t(`settings.passRules.presets.${preset}`)}</b>
                <span className="block text-sm text-ink-3">
                  {t(`settings.passRules.presets.${preset}Help`)}
                </span>
              </span>
              <Button type="button" variant="outline" size="sm" onClick={() => apply(preset)}>
                {t("settings.passRules.apply")}
              </Button>
            </li>
          ))}
        </ul>
        {section(t("settings.passRules.sections.pass"))}
        <div className="grid gap-4 sm:grid-cols-2">
          {number("pass_percent")}
          {number("course_pass_percent")}
        </div>
        {number("final_pass_percent", t("settings.passRules.help.final_pass_percent"))}
        {section(t("settings.passRules.sections.resit"))}
        <div className="grid gap-4 sm:grid-cols-2">
          {number("resit_percent")}
          {number("max_resit_courses")}
          {number("max_main_resits", t("settings.passRules.help.max_main_resits"))}
          {number("max_option_resits")}
        </div>
        {flag("practical_resit")}
        {number("resit_failures_to_fail", t("settings.passRules.help.resit_failures_to_fail"))}
        {section(t("settings.passRules.sections.leave"))}
        <div className="grid gap-4 sm:grid-cols-2">
          {number("orientation_percent", t("settings.passRules.help.orientation_percent"))}
          {number("max_repeats", t("settings.passRules.help.max_repeats"))}
        </div>
        {flag("exclude_repeated_class")}
        <div className="grid gap-4 sm:grid-cols-2">
          {number("conduct_ma_to_exclude", t("settings.passRules.help.conduct"))}
          {number("conduct_me_to_exclude")}
        </div>
        {flag("application_counts")}
        {section(t("settings.passRules.sections.age"))}
        <div className="grid gap-4 sm:grid-cols-2">
          {number("age_exception_years")}
          {number("age_exception_percent")}
        </div>
        <span className="text-sm text-ink-3">{t("settings.passRules.ageHelp")}</span>
      </CardContent>
    </Card>
  );
}
