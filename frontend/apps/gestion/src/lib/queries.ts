// Données lues partout : l'école de l'adresse (publique), le compte connecté, l'étape de connexion.
import { ApiError, api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

export type Me = Schemas["Me"];
export type School = Schemas["CurrentSchool"];
export type LoginStep = Schemas["StepEnum"];

export const keys = {
  school: ["school"],
  me: ["me"],
  loginStep: ["login-step"],
} as const;

/** Nouvel essai seulement sans réponse du serveur (réseau), jamais sur un refus de l'API. */
export function retryOnNetwork(failures: number, error: unknown) {
  return error instanceof ApiError && error.status === 0 && failures < 2;
}

export function hasCode(error: unknown, ...codes: string[]): error is ApiError {
  return error instanceof ApiError && codes.includes(error.code);
}

export function useSchool() {
  return useQuery({
    queryKey: keys.school,
    queryFn: () => call(api.GET("/api/school/")),
    staleTime: Infinity,
    retry: retryOnNetwork,
  });
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => call(api.GET("/api/me/")),
    staleTime: 30_000,
    retry: retryOnNetwork,
  });
}

/** Le compte connecté, sous `RequireAuth` (qui n'affiche ses écrans qu'une fois le compte lu). */
export function useCurrentMe(): Me {
  const { data } = useMe();
  if (!data) throw new Error("useCurrentMe() hors de RequireAuth");
  return data;
}

/** Étape de la connexion en cours, demandée au serveur (ex. après un rechargement de la page).
 *  Jamais relue d'elle-même : chaque écran la met à jour avec la réponse de son envoi. */
export function useLoginStep() {
  return useQuery({
    queryKey: keys.loginStep,
    queryFn: async () => (await call(api.GET("/api/auth/login/"))).step,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: retryOnNetwork,
  });
}
