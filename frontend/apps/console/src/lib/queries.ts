import { ApiError, api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

export type LoginStep = Schemas["StepEnum"];

export const keys = {
  me: ["me"],
  loginStep: ["login-step"],
  dashboard: ["console", "dashboard"],
};

export function hasCode(error: unknown, ...codes: string[]): error is ApiError {
  return error instanceof ApiError && codes.includes(error.code);
}

/** Le compte connecté ; pas connecté : erreur `not_authenticated`. */
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => call(api.GET("/api/me/")),
    retry: false,
    staleTime: 60_000,
  });
}

/** Étape de la connexion en cours, gardée par le serveur (après un rechargement aussi). */
export function useLoginStep() {
  return useQuery({
    queryKey: keys.loginStep,
    queryFn: async () => (await call(api.GET("/api/auth/login/"))).step,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
