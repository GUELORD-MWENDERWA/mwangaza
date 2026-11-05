// Caisse (F1-F2, M13) : `finance.collect_payment` pour ouvrir une caisse et encaisser ; la liste
// des caisses se lit aussi avec `finance.configure_fees` (carte « Caisses » des paramètres).
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type CashRegister = Schemas["CashRegisterState"];
export type CurrentSession = Schemas["CurrentCashSession"];
export type Payment = Schemas["Payment"];

export function useCashRegisters() {
  return useQuery({
    queryKey: keys.cashRegisters,
    queryFn: () => call(api.GET("/api/cash-registers/")),
  });
}

/** Caisse ouverte du caissier connecté (ou `null`), ses totaux par devise et le taux. */
export function useCurrentSession() {
  return useQuery({
    queryKey: keys.cashSession,
    queryFn: () => call(api.GET("/api/cash-sessions/current/")),
  });
}

/** Paiements d'une session, les plus récents d'abord ; recherche par reçu, nom ou matricule. */
export function useSessionPayments(session: string, search: string, page: number, enabled = true) {
  return useQuery({
    enabled,
    queryKey: [...keys.payments, session, search, page],
    queryFn: () =>
      call(
        api.GET("/api/payments/", {
          params: {
            query: { session, ...(search ? { search } : {}), ...(page > 1 ? { page } : {}) },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Clôture d'une session (F8) : attendu par devise, détail par type de frais, reçus, annulations
 *  (caisse en ligne ; sur un appareil mémorisé, calculée sur place). */
export function useSessionClosing(session: string, enabled = true) {
  return useQuery({
    enabled,
    queryKey: [...keys.cashSession, session, "closing"],
    queryFn: () =>
      call(api.GET("/api/cash-sessions/{id}/closing/", { params: { path: { id: session } } })),
  });
}

export type CashOut = Schemas["CashOut"];
export type PayableExpense = Schemas["PayableExpense"];

/** Dépenses validées à payer en espèces, pas encore sorties de la caisse (FIN.2). */
export function usePayableExpenses() {
  return useQuery({
    queryKey: [...keys.cashOuts, "payable"],
    queryFn: () => call(api.GET("/api/cash-outs/payable/")),
  });
}

/** Sortir l'argent d'une dépense de la session ouverte. `id` vient de l'appareil (UUID v7) : un
 *  renvoi après une coupure rend la même sortie. */
export function useRecordCashOut() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { id: string; expense: string; received_by: string }) =>
      call(api.POST("/api/cash-outs/", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.cashOuts });
      void client.invalidateQueries({ queryKey: keys.cashSession });
      void client.invalidateQueries({ queryKey: keys.expenses });
    },
  });
}
