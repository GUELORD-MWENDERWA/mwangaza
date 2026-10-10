import { api, ApiError, call, type Schemas } from "@mwangaza/api";
import { type QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { forgetOfflineData } from "./families";

export type Account = Schemas["PortalMe"];

export const accountKey = ["portal", "me"] as const;

/** Le serveur ne reconnaît plus le compte. Pas de réponse du serveur (`network`) n'en est pas
 *  une : réseau lent ou coupé ne renvoie jamais à la connexion. */
export const isSessionEnded = (error: unknown) =>
  error instanceof ApiError && error.code === "not_authenticated";

/** Le compte connecté au portail ; `null` sans session, ou session finie : rien de la famille ne
 *  reste alors sur le téléphone. */
export function useAccount() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: accountKey,
    queryFn: async (): Promise<Account | null> => {
      try {
        return await call(api.GET("/api/portal/me/"));
      } catch (error) {
        if (!isSessionEnded(error)) throw error;
        await forgetFamilyData(queryClient);
        return null;
      }
    },
  });
}

/** Fin de la session (déconnexion, ou compte que le serveur ne reconnaît plus) : rien de cette
 *  famille ne reste sur le téléphone, ni en mémoire ni hors ligne (téléphone prêté ou partagé). */
export async function forgetFamilyData(queryClient: QueryClient) {
  await forgetOfflineData();
  queryClient.removeQueries({
    queryKey: ["portal"],
    predicate: (query) => query.queryKey[1] !== accountKey[1],
  });
}

const LAST_SESSION_KEY = "mwangaza.portal.lastSession";

/** Trace d'une session ouverte sur ce téléphone, gardée jusqu'à la déconnexion : si le serveur ne
 *  reconnaît plus le compte, la session est finie (message, retour à la page demandée). Le numéro
 *  n'y est qu'avec « Rester connecté ». */
export type LastSession = { phone?: string };

export function lastSession(): LastSession | null {
  try {
    const raw = localStorage.getItem(LAST_SESSION_KEY);
    return raw ? (JSON.parse(raw) as LastSession) : null;
  } catch {
    return null;
  }
}

function keepLastSession(session: LastSession | null) {
  try {
    if (session) localStorage.setItem(LAST_SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(LAST_SESSION_KEY);
  } catch {
    // Stockage refusé (navigation privée) : connexion ordinaire, sans numéro rempli.
  }
}

export const forgetLastSession = () => keepLastSession(null);

/** Après la connexion, l'activation ou un nouveau mot de passe : le compte renvoyé par le
 *  serveur, puis l'accueil (ou `to`). */
export function useSignedIn(to = "/", remember = true) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return (account: Account) => {
    keepLastSession(remember ? { phone: account.phone } : {});
    queryClient.setQueryData(accountKey, account);
    void navigate(to, { replace: true });
  };
}
