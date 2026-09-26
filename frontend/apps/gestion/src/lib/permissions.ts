import type { Schemas } from "@mwangaza/api";

import type { Me } from "./queries";

export type Permission = Schemas["PermissionsEnum"];

/** Le compte a-t-il, dans l'école de l'adresse, au moins un de ces droits (`04` § 8) ? L'interface
 *  ne fait que masquer : le serveur vérifie chaque demande. */
export function can(me: Me, permissions: readonly Permission[]): boolean {
  const granted = me.school?.permissions ?? [];
  return permissions.some((permission) => granted.includes(permission));
}
