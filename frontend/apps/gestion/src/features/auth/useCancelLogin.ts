import { api, call } from "@mwangaza/api";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { keys } from "../../lib/queries";
import { useGoToStep } from "./useGoToStep";

/** « Retour » / « Se déconnecter » pendant la connexion : la connexion en cours est oubliée par le
 *  serveur, on revient au numéro et au mot de passe. */
export function useCancelLogin(next: string) {
  const queryClient = useQueryClient();
  const goToStep = useGoToStep(next);
  return useCallback(async () => {
    try {
      await call(api.POST("/api/auth/logout/"));
    } finally {
      queryClient.removeQueries({ queryKey: keys.me });
      goToStep("password");
    }
  }, [queryClient, goToStep]);
}
