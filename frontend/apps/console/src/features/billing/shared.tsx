// Éléments communs de la facturation (ABO.1, ABO.2, CTR.1) : montants, dates, liste simple.
import { formatDay, useTranslation } from "@mwangaza/i18n";
import { formatAmount, type Currency } from "@mwangaza/money";

export const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

export function useDay() {
  const { i18n } = useTranslation();
  return (value: string | null | undefined) => (value ? formatDay(value, i18n.language) : "—");
}

export const pdfUrl = (kind: "contracts" | "invoices", id: string) =>
  `/api/console/billing/${kind}/${encodeURIComponent(id)}/pdf/`;
