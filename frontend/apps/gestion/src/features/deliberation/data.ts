// Délibération d'une classe (8.4.2) : décision proposée, décision prise, écart motivé, résultats
// proclamés. Droit `grades.validate` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type ClassDeliberation = Schemas["ClassDeliberation"];
export type DeliberationRow = ClassDeliberation["students"][number];

export const DECISIONS = ["pass", "repeat", "resit", "orient", "exclude", "dropped"] as const;

export function useClassDeliberation(classId: string) {
  return useQuery({
    queryKey: [...keys.deliberation, classId],
    queryFn: () =>
      call(api.GET("/api/class-groups/{id}/deliberation/", { params: { path: { id: classId } } })),
    enabled: Boolean(classId),
  });
}

export type Decision = (typeof DECISIONS)[number];
