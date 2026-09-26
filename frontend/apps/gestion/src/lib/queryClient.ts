import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { hasCode, keys } from "./queries";

/** Cache des appels à l'API. Sans réseau, l'appel échoue tout de suite (message « pas de
 *  connexion ») au lieu d'attendre en silence ; la file d'opérations hors-ligne arrive en 3.4.
 *  Session fermée pendant le travail (`not_authenticated` sur un écran) : le compte est relu, et
 *  `RequireAuth` affiche « Votre session a expiré ». */
export function createQueryClient() {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error, query) => onError(error, query.queryKey) }),
    mutationCache: new MutationCache({ onError: (error) => onError(error, []) }),
    defaultOptions: {
      queries: { networkMode: "always" },
      mutations: { networkMode: "always" },
    },
  });

  function onError(error: unknown, queryKey: readonly unknown[]) {
    if (hasCode(error, "not_authenticated") && queryKey[0] !== keys.me[0]) {
      void queryClient.invalidateQueries({ queryKey: keys.me });
    }
  }

  return queryClient;
}
