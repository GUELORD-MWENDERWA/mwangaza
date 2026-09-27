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
  settings: ["school-settings"],
  years: ["academic-years"],
  levels: ["levels"],
  tracks: ["tracks"],
  classes: ["class-groups"],
  homeroomCandidates: ["homeroom-candidates"],
  matricule: ["matricule-format"],
  roles: ["roles"],
  staff: ["staff"],
  audit: ["audit"],
  students: ["students"],
  families: ["families"],
  studentImports: ["student-imports"],
  auditActors: ["audit-actors"],
  feeTypes: ["fee-types"],
  feeRules: ["fee-rules"],
  exchangeRates: ["exchange-rates"],
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

/** Rôles de l'école (droit `roles.manage`) : quelques dizaines, sur une page. */
export function useRoles() {
  return useQuery({
    queryKey: keys.roles,
    queryFn: async () => (await call(api.GET("/api/roles/"))).results,
  });
}
