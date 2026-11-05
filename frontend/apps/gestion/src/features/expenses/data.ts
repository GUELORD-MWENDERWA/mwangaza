// Dépenses (FIN.1) : appels au serveur. Une dépense n'est jamais effacée : on l'annule (motif).
import { type Schemas, api, call } from "@mwangaza/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Expense = Schemas["Expense"];
export type ExpenseCategory = Schemas["ExpenseCategory"];
export type Account = Expense["account"];
export type ExpenseStatus = Expense["status"];

export const ACCOUNTS: Account[] = ["cash", "bank", "mobile_money"];
export const STATUSES: ExpenseStatus[] = ["pending", "approved", "paid", "rejected"];
export const MAX_VOUCHER_BYTES = 5 * 1024 * 1024;

export type Filters = { month: string; status: string; category: string };

export const filterQuery = (filters: Filters) =>
  Object.fromEntries(Object.entries(filters).filter(([, value]) => value)) as Record<
    string,
    string
  >;

/** Couleur de la pastille d'une dépense (annulée : grise, comme un paiement annulé). */
export function toneOf(expense: Pick<Expense, "status" | "cancelled">) {
  if (expense.cancelled) return "gray" as const;
  return { pending: "warn", approved: "info", paid: "ok", rejected: "due" }[expense.status] as
    "warn" | "info" | "ok" | "due";
}

export function useCategories() {
  return useQuery({
    queryKey: keys.expenseCategories,
    queryFn: () => call(api.GET("/api/expense-categories/")),
  });
}

export function useThresholds() {
  return useQuery({
    queryKey: [...keys.expenses, "settings"],
    queryFn: () => call(api.GET("/api/expense-settings/")),
  });
}

export type NewExpense = {
  id: string;
  category: string;
  beneficiary: string;
  reason: string;
  amount_minor: number;
  currency: "USD" | "CDF";
  spent_on: string;
  account: Account;
  voucher: File | null;
};

export function useRecordExpense() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (expense: NewExpense) => {
      const body = new FormData();
      for (const [name, value] of Object.entries(expense)) {
        if (value === null) continue;
        body.append(name, value instanceof File ? value : String(value));
      }
      return call(
        api.POST("/api/expenses/", { body: body as unknown as Schemas["ExpenseCreateRequest"] }),
      );
    },
    onSuccess: () => client.invalidateQueries({ queryKey: keys.expenses }),
  });
}

/** Valider, refuser ou annuler : même forme, une note ou un motif. */
export function useExpenseAction(action: "approve" | "reject" | "cancel") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) =>
      action === "cancel"
        ? call(
            api.POST("/api/expenses/{id}/cancel/", {
              params: { path: { id } },
              body: { reason: text },
            }),
          )
        : call(
            api.POST(`/api/expenses/{id}/${action}/`, {
              params: { path: { id } },
              body: { note: text },
            }),
          ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.expenses }),
  });
}

export function useSaveThresholds() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ExpenseSettingsRequest"]) =>
      call(api.PUT("/api/expense-settings/", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.expenses }),
  });
}

export function useAddCategory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => call(api.POST("/api/expense-categories/", { body: { name } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.expenseCategories }),
  });
}
