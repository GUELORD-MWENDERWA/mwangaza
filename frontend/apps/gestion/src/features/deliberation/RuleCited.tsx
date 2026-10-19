// Règle du règlement de l'école qui donne la décision proposée (NB.4), écrite sous la proposition
// avec ses valeurs (seuil, pourcentage, cours). Délibération et repêchage.
import type { Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";

export function RuleCited({
  rule,
  params,
}: {
  rule: Schemas["RuleEnum"];
  params: Record<string, unknown>;
}) {
  const { t, i18n } = useTranslation();
  const value = (name: string) => {
    const raw = params[name];
    if (raw === undefined) return "";
    return name === "percent" ? Number(raw).toLocaleString(i18n.language) : String(raw);
  };
  const values = {
    percent: value("percent"),
    threshold: value("threshold"),
    count: value("count"),
    max: value("max"),
    courses: value("courses"),
    age: value("age"),
    limit: value("limit"),
  };
  return (
    <span className="mt-1 block text-xs text-ink-3">{t(`deliberation.rules.${rule}`, values)}</span>
  );
}
