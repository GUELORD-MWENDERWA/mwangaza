// Données fictives des tests d'écrans (jamais de vraie personne ni de vraie école).
import type { Schemas } from "@mwangaza/api";

import type { Permission } from "../lib/permissions";

export const school: Schemas["CurrentSchool"] = {
  code: "alpha",
  name: "École Alpha (fictive)",
  primary_color: "#0E5C6B",
  text_color: "#FFFFFF",
  logo: null,
  logo_monochrome: null,
  timezone: "Africa/Lubumbashi",
  enabled_currencies: ["USD", "CDF"],
  default_currency: "USD",
  receipt: { printer: "thermal_80", sheet_size: "a6", copies: 1, header: "", footer: "" },
};

// Droits des rôles système (copie de `backend/apps/accounts/roles.py`, `04` § 8).
export const PERMISSIONS = {
  head: [
    "school.configure",
    "classes.manage",
    "roles.manage",
    "students.view",
    "students.edit",
    "students.import",
    "finance.configure_fees",
    "finance.set_exchange_rate",
    "finance.grant_discount",
    "finance.approve_cancellation",
    "finance.view_reports",
    "announcements.publish",
    "audit.view",
  ],
  cashier: [
    "students.view",
    "finance.collect_payment",
    "finance.request_cancellation",
    "finance.close_register",
  ],
  promoter: ["students.view", "finance.view_reports", "audit.view"],
  study_director: ["classes.manage", "students.view", "students.edit", "announcements.publish"],
  teacher: [],
} satisfies Record<string, Permission[]>;

type Role = keyof typeof PERMISSIONS;

function role(code: Role): Schemas["RoleSummary"] {
  return {
    id: `00000000-0000-7000-8000-00000000000${Object.keys(PERMISSIONS).indexOf(code)}`,
    code,
    name: "",
  };
}

export function schoolEntry(overrides: Partial<Schemas["MeSchool"]> = {}): Schemas["MeSchool"] {
  return {
    code: school.code,
    name: school.name,
    status: "active",
    url: "http://alpha.localhost:5173",
    primary_color: school.primary_color,
    text_color: school.text_color,
    logo: null,
    roles: [role("head")],
    last_login_at: null,
    ...overrides,
  };
}

/** Compte connecté avec un rôle dans l'école de l'adresse. */
export function me(code: Role = "head", overrides: Partial<Schemas["Me"]> = {}): Schemas["Me"] {
  return {
    id: "00000000-0000-7000-8000-000000000100",
    phone: "+243000000100",
    last_name: "Test",
    middle_name: "Fictif",
    first_name: "Aline",
    language: "fr",
    totp_enabled: code === "head" || code === "cashier",
    totp_enabled_at: "2026-09-01T08:00:00Z",
    totp_required: code !== "teacher",
    recovery_codes_left: 8,
    is_platform_admin: false,
    schools: [schoolEntry({ roles: [role(code)] })],
    school: {
      code: school.code,
      name: school.name,
      roles: [role(code)],
      permissions: PERMISSIONS[code],
    },
    support: null,
    ...overrides,
  };
}

/** Super-admin à l'adresse de l'école, sans session support : aucun droit. */
export function platformAdmin(overrides: Partial<Schemas["Me"]> = {}): Schemas["Me"] {
  return {
    ...me("teacher"),
    last_name: "Support",
    first_name: "Admin",
    middle_name: "",
    is_platform_admin: true,
    totp_enabled: true,
    totp_required: true,
    schools: [],
    school: null,
    ...overrides,
  };
}

/** Identifiant fictif lisible (UUID v7 bien formé). */
export const fakeId = (n: number) => `00000000-0000-7000-8000-${String(n).padStart(12, "0")}`;

/** Frais dû d'une inscription (2.6), pas encore payé par défaut. */
export function charge(
  n: number,
  label: string,
  due_on: string,
  overrides: Partial<Schemas["StudentCharge"]> = {},
): Schemas["StudentCharge"] {
  const row = {
    id: fakeId(700 + n),
    enrollment: fakeId(80),
    fee_type: fakeId(500),
    fee_type_name: "Minerval",
    fee_category: "tuition",
    label,
    amount_minor: 12000,
    currency: "USD",
    due_on,
    source: "rule",
    status: "active",
    discount_minor: 0,
    paid_minor: 0,
    state: "upcoming",
    ...overrides,
  } as const;
  return {
    remaining_minor: row.amount_minor - row.discount_minor - row.paid_minor,
    ...row,
  } as Schemas["StudentCharge"];
}
