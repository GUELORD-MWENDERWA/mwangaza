// Examens de repêchage (8.4.1) : cours échoués de chaque élève d'une classe et note de repêchage.
// Lus avec `grades.enter`, `grades.enter_any` ou `grades.validate` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type ClassResits = Schemas["ClassResits"];
export type StudentResits = ClassResits["students"][number];
export type ResitCourse = StudentResits["courses"][number];

export function useClassResits(classId: string) {
  return useQuery({
    queryKey: [...keys.resits, classId],
    queryFn: () =>
      call(api.GET("/api/class-groups/{id}/resits/", { params: { path: { id: classId } } })),
    enabled: Boolean(classId),
  });
}
