// Application (8.5.1c) : cote d'application de chaque élève d'une classe, par période. Lue avec
// `grades.enter`, `grades.enter_any` ou `grades.validate` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type ClassApplication = Schemas["ClassApplication"];
export type StudentApplication = ClassApplication["students"][number];
export type TermApplication = StudentApplication["terms"][number];

export function useClassApplication(classId: string) {
  return useQuery({
    queryKey: [...keys.application, classId],
    queryFn: () =>
      call(api.GET("/api/class-groups/{id}/application/", { params: { path: { id: classId } } })),
    enabled: Boolean(classId),
  });
}
