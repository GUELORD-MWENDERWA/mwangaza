// Carte « Saisie des points » des paramètres de l'école (8.4.0) : devoirs détaillés (une note par
// devoir) ou seulement le total de la période, reporté sur la fiche de cotation. Chaque cours
// peut y déroger (écran des cours). Enregistrée avec le reste du formulaire.
import { useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle } from "@mwangaza/ui";

import type { CardProps } from "./SchoolSettingsPage";

const ENTRIES = ["detailed", "totals"] as const;

export function GradingCard({ form }: CardProps) {
  const { t } = useTranslation();
  const entry = form.watch("grading.entry");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.grading.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.grading.intro")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-2" role="radiogroup">
        {ENTRIES.map((value) => (
          <label
            key={value}
            className="flex cursor-pointer items-start gap-3 rounded-md border border-line p-3 has-[:checked]:border-brand"
          >
            <input
              type="radio"
              name="grading-entry"
              className="mt-1"
              checked={entry === value}
              onChange={() => form.setValue("grading.entry", value, { shouldDirty: true })}
            />
            <span>
              <b>{t(`settings.grading.${value}`)}</b>
              <span className="block text-sm text-ink-3">{t(`settings.grading.${value}Help`)}</span>
            </span>
          </label>
        ))}
      </CardContent>
    </Card>
  );
}
