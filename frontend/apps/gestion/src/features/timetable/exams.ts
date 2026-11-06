// Horaire des épreuves (EDT.5b) : lecture, enregistrement, publication, et liste des périodes
// où l'on peut fixer des épreuves (périodes et examens de l'année en cours).
import { api, call, type Schemas } from "@mwangaza/api";
import type { TFunction } from "@mwangaza/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";
import { type TermShape, termLabels } from "../../lib/terms";
import type { Year } from "../organisation/data";

export type ExamSchedule = Schemas["ExamSchedule"];
export type ExamSitting = Schemas["ExamSitting"];
export type ExamIssue = Schemas["ExamIssue"];
export type SittingBody = Schemas["ExamSittingWriteRequest"];

export const examsKey = (term: string) => [...keys.timetable, "exams", term];

export function useExamSchedule(term: string) {
  return useQuery({
    enabled: Boolean(term),
    queryKey: examsKey(term),
    queryFn: () =>
      call(
        api.GET("/api/timetable/exams/{term}/", {
          params: { path: { term }, query: { term } },
        }),
      ),
  });
}

type TermNode = Omit<Schemas["Term"], "children"> & { children?: TermNode[] };

/** Seules les périodes et les examens (feuilles de l'arbre) ont un horaire d'épreuves. */
export function examTerms(year: Year | undefined, t: TFunction) {
  const tree = (year?.terms ?? []) as TermNode[];
  const labels = termLabels(tree as TermShape[], t);
  const leaves: { id: string; name: string; starts_on: string | null; ends_on: string | null }[] =
    [];
  const walk = (nodes: TermNode[]) => {
    for (const node of nodes) {
      if (node.children?.length) walk(node.children);
      else if (node.kind === "period" || node.kind === "exam") {
        leaves.push({
          id: node.id,
          name: labels.get(node as TermShape) ?? node.name,
          starts_on: node.starts_on,
          ends_on: node.ends_on,
        });
      }
    }
  };
  walk(tree);
  return leaves;
}

function useRefresh(term: string) {
  const client = useQueryClient();
  return (schedule?: ExamSchedule) =>
    schedule
      ? client.setQueryData(examsKey(term), schedule)
      : client.invalidateQueries({ queryKey: examsKey(term) });
}

export function useSaveSitting(term: string, id?: string) {
  const refresh = useRefresh(term);
  return useMutation({
    mutationFn: (body: SittingBody) =>
      id
        ? call(api.PATCH("/api/timetable/exams/sittings/{id}/", { params: { path: { id } }, body }))
        : call(
            api.POST("/api/timetable/exams/{term}/", {
              params: { path: { term } },
              body,
            }),
          ),
    onSuccess: () => refresh(),
  });
}

export function useDeleteSitting(term: string) {
  const refresh = useRefresh(term);
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE("/api/timetable/exams/sittings/{id}/", { params: { path: { id } } })),
    onSuccess: () => refresh(),
  });
}

export function usePublishExams(term: string) {
  const refresh = useRefresh(term);
  return useMutation({
    mutationFn: (publish: boolean) =>
      publish
        ? call(api.POST("/api/timetable/exams/{term}/publish/", { params: { path: { term } } }))
        : call(api.DELETE("/api/timetable/exams/{term}/publish/", { params: { path: { term } } })),
    onSuccess: (schedule) => refresh(schedule),
  });
}

export const examPrintUrl = (term: string, kind: "class" | "general") =>
  `/api/timetable/exams/${term}/print/?kind=${kind}&output=pdf`;

export const hhmm = (time: string) => time.slice(0, 5);
