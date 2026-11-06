// Écran « Cartes » (lot 10, 6.1 · A.5) : listes, compteurs, impression et révocation. Le jeton du
// QR n'existe que dans le PDF qu'on vient d'émettre : l'écran ne le voit jamais.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type CardStudent = Schemas["CardStudent"];
export type CardStaff = Schemas["CardStaff"];
export type CardSettings = Schemas["CardSettings"];
export type CardLayout = Schemas["LayoutEnum"];
export type CardFilter = "" | "active" | "none";

export const cardKeys = {
  all: ["cards"] as const,
  summary: ["cards", "summary"] as const,
};

export type CardListQuery = { search: string; classGroup: string; card: CardFilter };

function params(filter: CardListQuery, page: number, withClass: boolean) {
  return {
    ...(filter.search ? { search: filter.search } : {}),
    ...(withClass && filter.classGroup ? { class_group: filter.classGroup } : {}),
    ...(filter.card ? { card: filter.card } : {}),
    ...(page > 1 ? { page } : {}),
  };
}

export function useCardSummary() {
  return useQuery({
    queryKey: cardKeys.summary,
    queryFn: () => call(api.GET("/api/attendance/cards/summary/")),
  });
}

export function useCardStudents(filter: CardListQuery, page: number) {
  return useQuery({
    queryKey: [...cardKeys.all, "students", filter, page],
    queryFn: () =>
      call(
        api.GET("/api/attendance/cards/students/", {
          params: { query: params(filter, page, true) },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useCardStaff(filter: CardListQuery, page: number) {
  return useQuery({
    queryKey: [...cardKeys.all, "staff", filter, page],
    queryFn: () =>
      call(
        api.GET("/api/attendance/cards/staff/", {
          params: { query: params(filter, page, false) },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Après une émission ou une révocation : relire listes et compteurs. */
export function useCardRefresh() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: cardKeys.all });
}

export function usePrintCards() {
  const refresh = useCardRefresh();
  return useMutation({
    mutationFn: (body: Schemas["CardPrintRequest"]) =>
      call(api.POST("/api/attendance/cards/print/", { body })),
    onSuccess: () => void refresh(),
  });
}

export function useRevokeCard() {
  const refresh = useCardRefresh();
  return useMutation({
    mutationFn: (input: { id: string; reason: Schemas["ReasonEnum"] }) =>
      call(
        api.POST("/api/attendance/cards/{id}/revoke/", {
          params: { path: { id: input.id } },
          body: { reason: input.reason },
        }),
      ),
    onSuccess: () => void refresh(),
  });
}
