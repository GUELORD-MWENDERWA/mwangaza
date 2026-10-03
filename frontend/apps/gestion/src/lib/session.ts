import { api, call } from "@mwangaza/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { signOutDevice } from "./pin";
import { disablePush } from "./push";
import { keys, type Me } from "./queries";

/** « Se déconnecter » : seulement une fois la session fermée par le serveur. Sans réseau, le
 *  message d'erreur reste affiché : l'appareil ne doit pas paraître déconnecté s'il ne l'est pas. */
export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async () => {
      // Ordinateur partagé : plus rien sur l'écran pour ce compte (5.5), tant que la session dure.
      await disablePush().catch(() => undefined);
      return call(api.POST("/api/auth/logout/"));
    },
    onSuccess: () => {
      // Plus de déverrouillage par PIN ici avant une nouvelle connexion complète (B5).
      const user = queryClient.getQueryData<Me>(keys.me)?.id;
      if (user) void signOutDevice(user).catch(() => undefined);
      navigate("/login", { replace: true });
      // Tout ce qui a été lu avec ce compte est oublié ; l'école de l'adresse reste.
      queryClient.removeQueries({ predicate: ({ queryKey }) => queryKey[0] !== keys.school[0] });
      queryClient.setQueryData(keys.loginStep, "password");
    },
  });
}
