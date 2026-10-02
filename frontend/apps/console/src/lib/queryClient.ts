import { QueryClient } from "@tanstack/react-query";

/** Cache des appels à l'API. Sans réseau, l'appel échoue tout de suite (message « pas de
 *  connexion ») au lieu d'attendre en silence. */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { networkMode: "always" },
      mutations: { networkMode: "always" },
    },
  });
}
