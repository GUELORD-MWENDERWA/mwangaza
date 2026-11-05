// Budget et rapports (FIN.3) : appels au serveur. Un tableau par devise, jamais de somme entre
// deux devises ; un solde de départ ou un virement n'est jamais effacé : on l'annule (motif).
import { type Schemas, api, call } from "@mwangaza/api";
import { type Currency, formatAmount } from "@mwangaza/money";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type BudgetReport = Schemas["BudgetReport"];
export type Movement = Schemas["TreasuryMovement"];
export type Account = Movement["to_account"];
export type NewMovement = Schemas["TreasuryMovementCreateRequest"];

export const ACCOUNTS: Account[] = ["cash", "bank", "mobile_money"];

export const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

/** Le montant sans symbole, pour le remettre dans une case de saisie. */
export const plain = (minor: number, currency: string) =>
  money(minor, currency)
    .replace(/[^\d,.\s]/g, "")
    .trim();

/** Part du prévu déjà dépensée, en pour cent entier (`null` : rien de prévu). */
export const usage = (planned: number, spent: number) =>
  planned > 0 ? Math.round((spent * 100) / planned) : null;

/** Ton de la pastille : dans le budget, presque atteint (dès 90 %), dépassé, non prévu. */
export function toneOf(planned: number, spent: number) {
  const percent = usage(planned, spent);
  if (percent === null) return spent > 0 ? ("due" as const) : ("gray" as const);
  return percent > 100 ? ("due" as const) : percent >= 90 ? ("warn" as const) : ("ok" as const);
}

export function useReport(year: string, currency: string) {
  return useQuery({
    queryKey: [...keys.budget, year, currency],
    queryFn: () =>
      call(
        api.GET("/api/budget/", {
          params: {
            query: {
              ...(year ? { academic_year: year } : {}),
              ...(currency ? { currency: currency as Currency } : {}),
            },
          },
        }),
      ),
  });
}

export function useMovements(year: string, enabled: boolean) {
  return useQuery({
    queryKey: [...keys.treasury, year],
    queryFn: () =>
      call(
        api.GET("/api/treasury-movements/", {
          params: { query: year ? { academic_year: year } : {} },
        }),
      ),
    enabled,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: keys.budget }),
      client.invalidateQueries({ queryKey: keys.treasury }),
    ]);
}

export function useSaveBudget() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: Schemas["BudgetWriteRequest"]) => call(api.PUT("/api/budget/", { body })),
    onSuccess: refresh,
  });
}

export function useRecordMovement() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: NewMovement) => call(api.POST("/api/treasury-movements/", { body })),
    onSuccess: refresh,
  });
}

export function useCancelMovement() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      call(
        api.POST("/api/treasury-movements/{id}/cancel/", {
          params: { path: { id } },
          body: { reason },
        }),
      ),
    onSuccess: refresh,
  });
}
