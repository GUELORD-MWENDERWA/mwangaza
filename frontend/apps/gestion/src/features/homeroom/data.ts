// Espace du titulaire (NB.3) : sa classe dans une période, et « Bulletins prêts ». En ligne
// seulement : tout est calculé au serveur d'après le bulletin de la classe.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type HomeroomData = Schemas["Homeroom"];
export type HomeroomCourse = Schemas["HomeroomCourse"];

export function useHomeroom(classGroup: string, term: string) {
  return useQuery({
    queryKey: [...keys.homeroom, classGroup, term],
    queryFn: () =>
      call(
        api.GET("/api/homeroom/", {
          params: {
            query: { ...(classGroup && { class_group: classGroup }), ...(term && { term }) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Déclarer les bulletins prêts (`ready` vrai) ou retirer la déclaration. */
export function useReady() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ready, ...target }: { ready: boolean; class_group: string; term: string }) =>
      ready
        ? call(api.POST("/api/homeroom/ready/", { body: target }))
        : call(api.DELETE("/api/homeroom/ready/", { params: { query: target } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.homeroom });
      void queryClient.invalidateQueries({ queryKey: keys.gradeValidation });
    },
  });
}

/** Pourcentage à une décimale, à la façon de la langue (« 67,5 % »). */
export function formatPercent(value: string | null | undefined, language: string): string {
  if (value == null) return "—";
  const number = Number(value).toLocaleString(language, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return `${number} %`;
}
