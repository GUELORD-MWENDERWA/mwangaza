// Crédits à traiter d'un élève (M14, 3.6.2) : à la caisse, proposés au prochain paiement avec ce
// qu'ils paieront (échéances les plus anciennes de leur devise, sans paiement ni reçu) ; sur la
// fiche de l'élève, avec un lien vers « Crédits d'élèves » pour qui peut les traiter.
import type { Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import { Banner, Button } from "@mwangaza/ui";
import { Link } from "react-router";

import { feeLabel, type Line } from "../cash/allocation";
import { creditLines } from "../cash/offline";

type Credit = Schemas["StudentCredit"];
type Charge = Schemas["StudentCharge"];

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

export function StudentCredits({
  credits,
  charges,
  onUse,
  using = false,
  canProcess = false,
}: {
  credits: Credit[];
  /** À la caisse : ce que doit l'élève, pour dire ce que paiera chaque crédit. */
  charges?: Charge[];
  onUse?: (credit: Credit, lines: Line[]) => void;
  using?: boolean;
  /** Fiche de l'élève : lien vers l'écran « Crédits d'élèves ». */
  canProcess?: boolean;
}) {
  const { t } = useTranslation();
  return credits.map((credit) => {
    const lines = charges ? creditLines(charges, credit) : [];
    const origin =
      credit.origin === "offline_surplus"
        ? t("credits.receipt", { number: credit.receipt_number })
        : t("credits.originDetail.discount");
    return (
      <Banner key={credit.id} tone="lamp" icon="credit">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <p className="min-w-0 flex-1">
            <b>
              {t("credits.student.title", {
                amount: money(credit.remaining_minor, credit.currency),
              })}
            </b>
            {` · ${t(`credits.origins.${credit.origin}`)} · ${origin}`}
            {charges && (
              <span className="mt-1 block text-sm">
                {lines.length
                  ? t("credits.student.pays", {
                      list: lines
                        .map(
                          (line) =>
                            `${feeLabel(line.charge)} ${money(line.amount, credit.currency)}`,
                        )
                        .join(" ; "),
                    })
                  : t("credits.nothingOwed")}
              </span>
            )}
          </p>
          {onUse && lines.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={using}
              onClick={() => onUse(credit, lines)}
            >
              {t("credits.use")}
            </Button>
          )}
          {canProcess && (
            <Link to="/credits" state={{ credit: credit.id }} className="text-lake underline">
              {t("credits.student.process")}
            </Link>
          )}
        </div>
      </Banner>
    );
  });
}
