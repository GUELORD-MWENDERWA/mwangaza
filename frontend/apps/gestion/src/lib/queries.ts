// Données lues partout : l'école de l'adresse (publique), le compte connecté, l'étape de connexion.
import { ApiError, api, call, type Schemas } from "@mwangaza/api";
import { type QueryClient, useQuery } from "@tanstack/react-query";

import { attachDevice, keepForOfflineStart, takeRememberDevice } from "./device";
import { reloadSync } from "./sync/session";

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
  cashRegisters: ["cash-registers"],
  cashSession: ["cash-session"],
  cancellations: ["cancellations"],
  closings: ["cash-closings"],
  payments: ["payments"],
  credits: ["student-credits"],
  unpaid: ["unpaid"],
  dashboard: ["dashboard"],
  setup: ["school-setup"],
  announcements: ["announcements"],
  platformNews: ["platform-news"],
  notifications: ["notifications"],
  notificationPreferences: ["notification-preferences"],
  contactChanges: ["contact-changes"],
  myDevices: ["my-devices"],
  schoolDevices: ["school-devices"],
  /** L'appareil mémorisé dans ce navigateur (code PIN), pas le serveur. */
  localDevice: ["local-device"],
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

const meQuery = {
  queryKey: keys.me,
  queryFn: () => call(api.GET("/api/me/")),
  staleTime: 30_000,
  retry: retryOnNetwork,
};

export function useMe() {
  return useQuery(meQuery);
}

/** Connexion terminée : l'appareil de ce navigateur reprend la session, ou est enregistré si la
 *  case « Se souvenir de cet appareil » était cochée. Un échec n'empêche pas de travailler. */
export async function attachDeviceAfterLogin(queryClient: QueryClient) {
  const remember = takeRememberDevice();
  try {
    const me = await queryClient.fetchQuery(meQuery);
    if (!me.school) return;
    await attachDevice(me.id, remember);
    const school = queryClient.getQueryData<School>(keys.school);
    if (school) await keepForOfflineStart(me, school);
    reloadSync();
    await queryClient.invalidateQueries({ queryKey: keys.myDevices });
    await queryClient.invalidateQueries({ queryKey: keys.schoolDevices });
    await queryClient.invalidateQueries({ queryKey: keys.localDevice });
  } catch {
    // Sans réseau ou sans WebCrypto : l'appareil sera repris à la prochaine connexion.
  }
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
