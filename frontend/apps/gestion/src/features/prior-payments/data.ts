// Reprise en cours d'année (E6, 4.19) : ce que chaque élève avait payé avant que l'école
// n'utilise l'application, importé d'un fichier. Le même fichier est envoyé deux fois : pour
// l'aperçu, puis avec les totaux de l'aperçu pour l'enregistrer (le serveur refuse si le
// résultat a changé entre-temps). Droit : `finance.import_prior_payments`.
import { api, call, type Schemas } from "@mwangaza/api";
import type { TFunction } from "@mwangaza/i18n";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type PriorPreview = Schemas["PriorPaymentPreview"];
export type PriorLine = Schemas["PriorPaymentLine"];

export const priorTemplateUrl = "/api/prior-payments/template/";

export function sendPriorPayments(file: File, expected?: PriorPreview["totals"]) {
  const body = new FormData();
  body.append("file", file);
  if (expected) body.append("expected", JSON.stringify(expected));
  return call(api.POST("/api/prior-payments/", { body: body as unknown as { file: string } }));
}

/** Reprises d'une inscription (fiche élève), annulées comprises. */
export function usePriorPayments(enrollment: string | undefined) {
  return useQuery({
    enabled: Boolean(enrollment),
    queryKey: [...keys.payments, "prior", enrollment],
    queryFn: () =>
      call(
        api.GET("/api/payments/", {
          params: { query: { enrollment: enrollment!, origin: "prior" } },
        }),
      ),
  });
}

/** Là où s'affiche la caisse d'un paiement : une reprise n'en a pas. */
export function registerLabel(
  payment: { origin: Schemas["PaymentOriginEnum"]; cash_register_name: string },
  t: TFunction,
): string {
  return payment.origin === "prior" ? t("priorPayments.label") : payment.cash_register_name;
}
