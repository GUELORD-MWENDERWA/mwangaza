// Délibération d'une classe (8.4.2) : décision proposée, décision prise, écart motivé, résultats
// proclamés ; conseil et sessions de période (NB.5) ; seconde session (NB.6). Lecture : membres du
// conseil ; écriture : `grades.validate`. En ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";
import type { TermKind, TermShape } from "../../lib/terms";
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

export type SessionResult = ClassDeliberation["results"][number];

/** Seconde session (NB.6) dans le choix des sessions : élèves proclamés « repêchage ». */
export const SECOND = "second";

/** Paramètres de la session : vide = fin d'année, `SECOND`, sinon une période ou un semestre. */
export function sessionQuery(termId: string): { term?: string; second?: boolean } {
  if (termId === SECOND) return { second: true };
  return termId ? { term: termId } : {};
}
export type CouncilMember = ClassDeliberation["council"]["members"][number];

/** Tableau d'une session (NB.5) : `termId` vide = fin d'année, `SECOND`, ou période, semestre. */
export function useClassDeliberation(classId: string, termId: string) {
  return useQuery({
    queryKey: [...keys.deliberation, classId, termId],
    queryFn: () =>
      call(
        api.GET("/api/class-groups/{id}/deliberation/", {
          params: { path: { id: classId }, query: sessionQuery(termId) },
        }),
      ),
    enabled: Boolean(classId),
  });
}

/** Procès-verbal de la dernière proclamation de la session (NB.5), PDF ou aperçu. */
export function minutesUrl(classId: string, termId: string, output: "pdf" | "html" = "pdf") {
  const query = new URLSearchParams({ output });
  if (termId === SECOND) query.set("second", "true");
  else if (termId) query.set("term", termId);
  return `/api/class-groups/${classId}/deliberation/minutes/?${query}`;
}

type SessionNode = { id: string; kind: TermKind; name: string; children?: SessionNode[] };

/** Sessions du conseil dans l'ordre de l'année : chaque période, puis le semestre (ou le
 *  trimestre) qui les regroupe ; les examens se délibèrent avec leur semestre. */
export function sessionTerms(nodes: SessionNode[], labels: Map<TermShape, string>) {
  const sessions: { id: string; label: string }[] = [];
  const add = (node: SessionNode) => sessions.push({ id: node.id, label: labels.get(node) ?? "" });
  for (const node of nodes) {
    if (node.kind === "period") add(node);
    if (node.kind !== "semester" && node.kind !== "trimester") continue;
    for (const child of node.children ?? []) if (child.kind === "period") add(child);
    add(node);
  }
  return sessions;
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
