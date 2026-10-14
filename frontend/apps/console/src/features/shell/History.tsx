// « Derniers changements » d'une fiche de la console (journal de la plateforme) : écoles (5.3),
// comptes (5.4.1).
import type { Schemas } from "@mwangaza/api";
import { formatDateTime, useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle } from "@mwangaza/ui";
import type { ReactNode } from "react";

export type Change = Schemas["PlatformChange"];

export function History({
  changes,
  details,
}: {
  changes: Change[];
  /** Précisions sous l'action (ex. les champs changés). */
  details?: (change: Change) => ReactNode;
}) {
  const { t, i18n } = useTranslation();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.historyTitle")}</CardTitle>
      </CardHeader>
      {changes.length === 0 && (
        <CardContent className="text-md text-ink-3">{t("console.identity.noChange")}</CardContent>
      )}
      <ul className="m-0 list-none p-0">
        {changes.map((change) => (
          <li
            key={change.id}
            className="flex flex-col gap-0.5 border-t border-line px-4 py-2.5 text-md first:border-t-0"
          >
            <b>{t(`console.actions.${change.action}`)}</b>
            <span className="text-sm text-ink-3">
              {formatDateTime(change.created_at, i18n.language, timeZone)}
              {change.actor && ` · ${[change.actor.first_name, change.actor.last_name].join(" ")}`}
            </span>
            {details?.(change)}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** « Champ : avant → après » pour chaque champ changé que `label` nomme (les autres sont
 *  tus). */
export function Differences({
  change,
  label,
  shown = (_field, value) => value,
}: {
  change: Change;
  label: (field: string) => string | null;
  shown?: (field: string, value: string) => string;
}) {
  const { t } = useTranslation();
  const before = (change.before ?? {}) as Record<string, string | null>;
  const after = (change.after ?? {}) as Record<string, string | null>;
  const text = (field: string, value: string | null | undefined) =>
    value ? shown(field, value) : t("console.identity.empty");
  return Object.keys(after).map((field) => {
    const name = label(field);
    return (
      name && (
        <span key={field} className="text-sm break-words">
          {t("console.identity.difference", {
            field: name,
            before: text(field, before[field]),
            after: text(field, after[field]),
          })}
        </span>
      )
    );
  });
}
