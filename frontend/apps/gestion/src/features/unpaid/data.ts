// Impayés (G1) : les filtres sont dans l'adresse (`?class_group=…&over_days=30`), pour que
// l'écran « Exporter » reprenne exactement ceux de la liste, comme le serveur.
import type { Schemas } from "@mwangaza/api";

import { layoutQuery, type PrintLayout } from "../printing/printOptions";

export type UnpaidRow = Schemas["UnpaidStudent"];
export type UnpaidSummary = Schemas["UnpaidSummary"];

export const FILTERS = [
  "class_group",
  "fee_type",
  "installment",
  "over_days",
  "currency",
  "order",
] as const;
export type FilterName = (typeof FILTERS)[number];

/** Retard : tous, ou de plus de N jours. */
export const OVER_DAYS = ["0", "7", "30", "60", "90"] as const;
export const ORDERS = ["amount", "days", "name", "class"] as const;

/** Les filtres choisis, sans les valeurs par défaut (0 jour, tri par montant). */
export function filtersOf(params: URLSearchParams): Record<string, string> {
  const filters: Record<string, string> = {};
  for (const name of FILTERS) {
    const value = params.get(name);
    if (
      value &&
      !(name === "over_days" && value === "0") &&
      !(name === "order" && value === "amount")
    )
      filters[name] = value;
  }
  return filters;
}

export type ExportOptions = {
  output: "xlsx" | "pdf" | "html";
  group: "class" | "list";
  pagePerClass: boolean;
  phone: boolean;
  detail: boolean;
  layout: PrintLayout;
};

/** Adresse de l'export, avec les filtres de la liste. */
export function exportUrl(filters: Record<string, string>, options: ExportOptions) {
  const query = new URLSearchParams({
    ...filters,
    output: options.output,
    group: options.group,
    page_per_class: String(options.pagePerClass),
    phone: String(options.phone),
    detail: String(options.detail),
    ...layoutQuery(options.layout),
  });
  return `/api/unpaid/export/?${query}`;
}
