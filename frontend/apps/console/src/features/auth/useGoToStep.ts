import { api, call } from "@mwangaza/api";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useNavigate } from "react-router";

import { stepPath } from "../../lib/login";
import { keys, type LoginStep } from "../../lib/queries";

/** Après chaque envoi de la connexion : l'étape suivante (page), ou `done` → la page demandée,
 *  avec le compte relu. */
export function useGoToStep(next: string) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useCallback(
    (step: LoginStep) => {
      if (step === "done") queryClient.removeQueries({ queryKey: keys.me });
      queryClient.setQueryData(keys.loginStep, step);
      navigate(stepPath(step, next), { replace: true });
    },
    [queryClient, navigate, next],
  );
}

/** « Retour » pendant la connexion, ou « Se déconnecter » : le serveur oublie la session, on
 *  revient au numéro et au mot de passe. */
export function useLogout(next = "/") {
  const queryClient = useQueryClient();
  const goToStep = useGoToStep(next);
  return useCallback(async () => {
    try {
      await call(api.POST("/api/auth/logout/"));
    } finally {
      queryClient.removeQueries({ queryKey: keys.me });
      queryClient.removeQueries({ queryKey: keys.dashboard });
      goToStep("password");
    }
  }, [queryClient, goToStep]);
}
