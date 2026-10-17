// Délibération d'une classe (8.4.2) : décision proposée, décision prise, écart motivé, résultats
// proclamés. Droit `grades.validate` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";
import { layoutQuery, type PrintLayout } from "../printing/printOptions";

export type ClassDeliberation = Schemas["ClassDeliberation"];
export type DeliberationRow = ClassDeliberation["students"][number];

export const DECISIONS = ["pass", "repeat", "resit", "orient", "exclude", "dropped"] as const;

export const TONES: Record<string, "ok" | "warn" | "due" | "gray"> = {
  pass: "ok",
  resit: "warn",
  repeat: "due",
  orient: "warn",
  exclude: "due",
  dropped: "gray",
};

export function useClassDeliberation(classId: string) {
  return useQuery({
    queryKey: [...keys.deliberation, classId],
    queryFn: () =>
      call(api.GET("/api/class-groups/{id}/deliberation/", { params: { path: { id: classId } } })),
    enabled: Boolean(classId),
  });
}

export type Decision = (typeof DECISIONS)[number];

export type SituationKind = "class" | "school";
export type Criterion = "rules" | "average";

/** Situation d'une classe ou de l'école (8.4.4) : PDF ou aperçu, critère et parties choisis. */
export function situationUrl(options: {
  kind: SituationKind;
  classId?: string;
  criterion: Criterion;
  columns: string[];
  output: "html" | "pdf";
  layout: PrintLayout;
}) {
  const query = new URLSearchParams({ criterion: options.criterion, output: options.output });
  for (const column of options.columns) query.append("columns", column);
  for (const [key, value] of Object.entries(layoutQuery(options.layout))) query.set(key, value);
  return options.kind === "class"
    ? `/api/class-groups/${options.classId}/situation/?${query}`
    : `/api/situation/?${query}`;
}

/** Pourcentage repris tapé à la française (« 62,5 ») → valeur de l'API ; vide : aucun. */
export function priorPercent(text: string): string | null {
  const value = text.trim().replace(",", ".");
  return value === "" ? null : value;
}

export type PriorResultPreview = Schemas["PriorResultPreview"];
export type PriorResultLine = Schemas["PriorResultLine"];

export const priorResultsTemplateUrl = "/api/deliberation/prior-results/template/";

/** Reprise des résultats (8.4.7) : le même fichier est envoyé pour l'aperçu, puis avec le nombre
 * de lignes prêtes et la date pour l'enregistrer (le serveur refuse si le résultat a changé). */
export function sendPriorResults(file: File, record?: { expected: number; heldOn: string }) {
  const body = new FormData();
  body.append("file", file);
  if (record) {
    body.append("expected", String(record.expected));
    body.append("held_on", record.heldOn);
  }
  return call(
    api.POST("/api/deliberation/prior-results/", { body: body as unknown as { file: string } }),
  );
}
