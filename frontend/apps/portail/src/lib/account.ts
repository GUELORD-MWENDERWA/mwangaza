import { api, ApiError, call, type Schemas } from "@mwangaza/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

export type Account = Schemas["PortalMe"];

export const accountKey = ["portal", "me"] as const;

/** Le compte connecté au portail ; `null` sans session (ou session expirée). */
export function useAccount() {
  return useQuery({
    queryKey: accountKey,
    queryFn: async (): Promise<Account | null> => {
      try {
        return await call(api.GET("/api/portal/me/"));
      } catch (error) {
        if (error instanceof ApiError && error.code === "not_authenticated") return null;
        throw error;
      }
    },
  });
}

/** Après la connexion, l'activation ou un nouveau mot de passe : le compte renvoyé par le
 *  serveur, puis l'accueil. */
export function useSignedIn() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return (account: Account) => {
    queryClient.setQueryData(accountKey, account);
    void navigate("/", { replace: true });
  };
}
