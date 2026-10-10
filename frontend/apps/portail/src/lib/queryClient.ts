import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { accountKey, isSessionEnded } from "./account";

/** Cache des appels à l'API. Sans réseau, l'appel échoue tout de suite (message « pas de
 *  connexion ») au lieu d'attendre en silence. Session finie en cours d'usage, sur n'importe
 *  quel appel : le compte est relu, ce qui mène à la connexion (`RequireAccount`). */
export function createQueryClient() {
  const onError = (error: unknown) => {
    if (isSessionEnded(error)) void client.invalidateQueries({ queryKey: accountKey });
  };
  const client = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: { networkMode: "always" },
      mutations: { networkMode: "always" },
    },
  });
  return client;
}
