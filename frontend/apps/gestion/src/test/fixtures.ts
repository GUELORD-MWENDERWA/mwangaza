// Données fictives des tests d'écrans (jamais de vraie personne ni de vraie école).
import type { Schemas } from "@mwangaza/api";

import type { Permission } from "../lib/permissions";

const ALL_MODULES: Schemas["ModulesEnum"][] = [
  "students",
  "finance",
  "communication",
  "portal",
  "notifications",
  "offline",
];

export const school: Schemas["CurrentSchool"] = {
  code: "alpha",
  name: "École Alpha (fictive)",
  primary_color: "#0B5FCC",
  text_color: "#FFFFFF",
  logo: null,
  logo_monochrome: null,
  timezone: "Africa/Lubumbashi",
  enabled_currencies: ["USD", "CDF"],
  default_currency: "USD",
  auto_matricule: true,
  environment: "live",
  setup_done: true,
  receipt: { printer: "thermal_80", sheet_size: "a6", copies: 1, header: "", footer: "" },
};

// Droits des rôles du modèle de départ (copie de `backend/apps/accounts/roles.py`, `04` § 8).
export const PERMISSIONS = {
  head: [
    "school.configure",
    "classes.manage",
    "courses.configure",
    "roles.manage",
    "students.view",
    "students.edit",
    "students.import",
    "finance.configure_fees",
    "finance.set_exchange_rate",
    "finance.grant_discount",
    "finance.approve_cancellation",
    "finance.view_reports",
    "finance.import_prior_payments",
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
  study_director: [
    "classes.manage",
    "courses.configure",
    "grades.enter_any",
    "students.view",
    "students.edit",
    "announcements.publish",
  ],
  teacher: ["grades.enter"],
  accountant: [
    "students.view",
    "finance.configure_fees",
    "finance.set_exchange_rate",
    "finance.grant_discount",
    "finance.collect_payment",
    "finance.request_cancellation",
    "finance.approve_cancellation",
    "finance.close_register",
    "finance.view_reports",
    "finance.import_prior_payments",
  ],
} satisfies Record<string, Permission[]>;

type Role = keyof typeof PERMISSIONS;

// Nom que l'école de test donne à chacun : un rôle n'a pas de code.
const ROLE_NAMES: Record<Role, string> = {
  head: "Directeur",
  cashier: "Caissier",
  promoter: "Promoteur",
  study_director: "Directeur des études",
  teacher: "Enseignant",
  accountant: "Comptable",
};

function role(key: Role): Schemas["RoleSummary"] {
  return {
    id: `00000000-0000-7000-8000-00000000000${Object.keys(PERMISSIONS).indexOf(key)}`,
    name: ROLE_NAMES[key],
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
/** Ni cachet ni signature déposés (DOC.1) : lignes à signer à la main. */
export const NO_SIGNATURES: Schemas["DocumentSigners"] = {
  stamp: null,
  head_name: "",
  head_title: "",
  head_signature: null,
  signature: null,
};

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
      modules: ALL_MODULES,
      documents: NO_SIGNATURES,
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

/** Crédit à traiter (M14) : payé deux fois hors ligne, 30,00 $. */
export function studentCredit(
  overrides: Partial<Schemas["StudentCredit"]> = {},
): Schemas["StudentCredit"] {
  return {
    id: fakeId(70),
    enrollment: fakeId(80),
    student: { id: fakeId(30), full_name: "KAMBALE MUHINDO Josué", matricule: "ALPHA-2026-0412" },
    class_group: "3e Électricité A",
    origin: "offline_surplus",
    amount_minor: 3000,
    currency: "USD",
    used_minor: 0,
    remaining_minor: 3000,
    state: "to_process",
    created_at: "2026-10-19T09:51:00Z",
    voided_at: null,
    source_payment: fakeId(101),
    receipt_number: "ALPHA-C1-26-000101",
    cash_register_name: "Caisse 1",
    paid_at: "2026-10-19T09:51:00Z",
    discount_reason: null,
    discount_fee_type: null,
    ...overrides,
  };
}
