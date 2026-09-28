// Caisse (F1-F2, M13) : `finance.collect_payment` pour ouvrir une caisse et encaisser ; la liste
// des caisses se lit aussi avec `finance.configure_fees` (carte « Caisses » des paramètres).
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

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
export function useSessionPayments(session: string, search: string, page: number) {
  return useQuery({
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
