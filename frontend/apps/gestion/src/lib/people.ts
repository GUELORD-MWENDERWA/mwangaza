import type { Schemas } from "@mwangaza/api";
import type { TFunction } from "@mwangaza/i18n";

import type { Me } from "./queries";

type Role = Schemas["RoleSummary"];

/** « Prénom Nom » (post-nom si pas de prénom), comme en haut à droite des maquettes. */
export function displayName(me: Pick<Me, "first_name" | "middle_name" | "last_name">): string {
  return [me.first_name || me.middle_name, me.last_name].filter(Boolean).join(" ");
}

/** Nom d'un rôle : celui donné par l'école, sinon le nom traduit du rôle système. */
export function roleName(role: Role, t: TFunction): string {
  if (role.name) return role.name;
  return role.code ? t(`roles.${role.code}`) : "";
}

export function rolesLabel(roles: Role[], t: TFunction): string {
  return roles.length ? roles.map((role) => roleName(role, t)).join(", ") : t("roles.none");
}

// Partagé avec le Portail.
export { formatPhone } from "@mwangaza/i18n";

/** « Prénom Post-nom NOM » d'une personne. */
export function fullName(person: { first_name: string; middle_name: string; last_name: string }) {
  return [person.first_name, person.middle_name, person.last_name].filter(Boolean).join(" ");
}

/** « NOM POST-NOM Prénom » d'un élève, comme sur les listes de l'école. */
export function studentName(student: {
  first_name: string;
  middle_name: string;
  last_name: string;
}) {
  return [student.last_name.toUpperCase(), student.middle_name.toUpperCase(), student.first_name]
    .filter(Boolean)
    .join(" ");
}
