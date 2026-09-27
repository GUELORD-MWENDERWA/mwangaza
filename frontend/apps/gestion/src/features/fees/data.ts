// Frais et barèmes (E1, E2, E5) : lus avec l'un des droits de l'entrée « Frais » du menu
// (`finance.configure_fees`, `finance.set_exchange_rate`, `finance.grant_discount`). Listes de
// configuration : sans pagination.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type FeeType = Schemas["FeeType"];
export type FeeRule = Schemas["FeeRule"];
export type ExchangeRate = Schemas["ExchangeRate"];
export type FeeCategory = Schemas["FeeCategoryEnum"];
export type ScheduleKind = Schemas["ScheduleKindEnum"];

export const CATEGORIES: FeeCategory[] = [
  "tuition",
  "registration",
  "operating",
  "ancillary",
  "uniform",
  "transport",
  "canteen",
  "extracurricular",
  "official_exam",
  "custom",
];
export const SCHEDULE_KINDS: ScheduleKind[] = ["installments", "monthly", "single"];

export function useFeeTypes() {
  return useQuery({ queryKey: keys.feeTypes, queryFn: () => call(api.GET("/api/fee-types/")) });
}

export function useFeeRules(year: string) {
  return useQuery({
    queryKey: [...keys.feeRules, year],
    queryFn: () => call(api.GET("/api/fee-rules/", { params: { query: { academic_year: year } } })),
  });
}

export function useExchangeRates(year: string) {
  return useQuery({
    queryKey: [...keys.exchangeRates, year],
    queryFn: () =>
      call(api.GET("/api/exchange-rates/", { params: { query: { academic_year: year } } })),
  });
}
