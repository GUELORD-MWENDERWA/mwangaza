import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useNavigate } from "react-router";

import { stepPath } from "../../lib/login";
import { attachDeviceAfterLogin, keys, type LoginStep } from "../../lib/queries";

/** Après chaque envoi de la connexion : l'étape suivante (page), ou `done` → la page demandée,
 *  avec le compte relu. */
export function useGoToStep(next: string) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useCallback(
    (step: LoginStep) => {
      if (step === "done") {
        queryClient.removeQueries({ queryKey: keys.me });
        void attachDeviceAfterLogin(queryClient);
      }
      queryClient.setQueryData(keys.loginStep, step);
      navigate(stepPath(step, next), { replace: true });
    },
    [queryClient, navigate, next],
  );
}
