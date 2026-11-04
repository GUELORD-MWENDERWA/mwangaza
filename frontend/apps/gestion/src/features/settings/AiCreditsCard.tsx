// « Crédits IA » (IA.1.2, maquette `gestion/parametres-ecole`) : lecture seule ; la plateforme
// règle les usages et les crédits depuis la console. Montrée si l'école a le module « IA ».
import { formatMonth, useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle, List, Skeleton } from "@mwangaza/ui";

import { blockedCode, useAiCredits } from "../ai/AiButton";

export function AiCreditsCard() {
  const { t, i18n } = useTranslation();
  const credits = useAiCredits();
  if (credits.isPending) return <Skeleton label={t("common.loading")} />;
  if (credits.isError) return null;
  const data = credits.data;
  const nf = (value: number) => value.toLocaleString(i18n.language);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("ai.credits.title")}</CardTitle>
        <span className="text-sm text-ink-3">
          {formatMonth(data.month.slice(0, 7), i18n.language)}
        </span>
      </CardHeader>
      <CardContent>
        <List className="text-md">
          <div>
            <span>{t("ai.credits.granted")}</span>
            <b className="tabular-nums">{nf(data.granted_credits)}</b>
          </div>
          <div>
            <span>{t("ai.credits.spent")}</span>
            <b className="tabular-nums">{nf(data.spent_credits)}</b>
          </div>
          <div>
            <span>{t("ai.credits.remaining")}</span>
            <b className="tabular-nums">{nf(data.remaining_credits)}</b>
          </div>
          <div className="!items-start">
            <span className="flex-none">{t("ai.credits.uses")}</span>
            <span className="text-right text-ink-3">
              {data.uses.length
                ? data.uses.map((use) => use.label).join(" · ")
                : t("ai.credits.none")}
            </span>
          </div>
          {data.blocked && (
            <div>
              <span className="font-bold text-due">
                {t(`ai.blocked.${blockedCode(data.blocked)}`)}
              </span>
            </div>
          )}
          <div>
            <span className="text-sm text-ink-3">{t("ai.credits.help")}</span>
          </div>
        </List>
      </CardContent>
    </Card>
  );
}
