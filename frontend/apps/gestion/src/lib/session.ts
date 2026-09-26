import { api, call } from "@mwangaza/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { keys } from "./queries";

/** « Se déconnecter » : seulement une fois la session fermée par le serveur. Sans réseau, le
 *  message d'erreur reste affiché : l'appareil ne doit pas paraître déconnecté s'il ne l'est pas. */
export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () => call(api.POST("/api/auth/logout/")),
    onSuccess: () => {
      navigate("/login", { replace: true });
      // Tout ce qui a été lu avec ce compte est oublié ; l'école de l'adresse reste.
      queryClient.removeQueries({ predicate: ({ queryKey }) => queryKey[0] !== keys.school[0] });
      queryClient.setQueryData(keys.loginStep, "password");
    },
  });
}
