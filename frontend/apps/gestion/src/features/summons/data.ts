// Convocations des parents (5.7) : liste paginée (recherche par élève), nouvelle convocation,
// annulation. Jamais modifiée : on l'annule et on en fait une autre.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Summons = Schemas["Summons"];
export const PAGE_SIZE = 50;

export function useSummons(search: string, page: number) {
  return useQuery({
    queryKey: [...keys.summons, search, page],
    queryFn: () => call(api.GET("/api/summons/", { params: { query: { search, page } } })),
    placeholderData: keepPreviousData,
  });
}

export type NewSummons = Schemas["SummonsCreateRequest"];

export function useIssue() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewSummons) => call(api.POST("/api/summons/", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.summons }),
  });
}

export function useCancel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      call(api.POST("/api/summons/{id}/cancel/", { params: { path: { id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.summons }),
  });
}

/** Lettre de convocation (PDF) : ouverte dans un nouvel onglet, à imprimer. */
export const letterUrl = (id: string) => `/api/summons/${id}/letter/`;
