import type { Schemas } from "@mwangaza/api";

import type { Me } from "./queries";

export type Permission = Schemas["PermissionsEnum"];

/** Le compte a-t-il, dans l'école de l'adresse, au moins un de ces droits (`04` § 8) ? L'interface
 *  ne fait que masquer : le serveur vérifie chaque demande. */
export function can(me: Me, permissions: readonly Permission[]): boolean {
  const granted = me.school?.permissions ?? [];
  return permissions.some((permission) => granted.includes(permission));
}

/** Ce que le registre des modules (`accounts/modules.py`, MOD.1) ne donne qu'à certains modules :
 *  champs de la fiche élève, sections des paramètres. */
export type Feature =
  | "student.national_id"
  | "student.permanent_number"
  | "student.birth_place"
  | "student.nationality"
  | "student.origin"
  | "settings.currencies"
  | "settings.receipt"
  | "settings.alerts"
  | "settings.reminders"
  | "settings.portal"
  | "settings.grading"
  | "settings.pass_rules"
  | "settings.ai";

/** L'école de l'adresse a-t-elle un module qui porte `feature` ? Le serveur n'exige ni n'écrit
 *  jamais ce qui ne s'applique pas ; l'interface le masque. */
export function applies(me: Me, feature: Feature): boolean {
  return me.school?.features.includes(feature) ?? false;
}
