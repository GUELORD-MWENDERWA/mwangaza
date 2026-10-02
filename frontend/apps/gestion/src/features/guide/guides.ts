// Guides de première connexion (I3, maquette `guide-premiere-connexion`, M20) : un par rôle
// système concerné. Chaque étape ouvre un écran et y met en valeur un vrai élément, repéré par
// `data-guide="…"` ; elle ne fait rien à la place de l'utilisateur.
import { can, type Permission } from "../../lib/permissions";
import type { Me } from "../../lib/queries";

export type GuideKey = "cashier" | "accountant";

export interface GuideStep {
  /** Textes : `guide.<guide>.<key>.title` et `.text`. */
  key: string;
  path: string;
  target: string;
  /** Étape montrée si l'utilisateur a l'un de ces droits (rôle modifié par l'école). */
  permissions: readonly Permission[];
}

const COLLECT = ["finance.collect_payment"] as const;

export const GUIDES: Record<GuideKey, readonly GuideStep[]> = {
  cashier: [
    { key: "open", path: "/cash", target: "cash-start", permissions: COLLECT },
    { key: "search", path: "/cash", target: "cash-search", permissions: COLLECT },
    { key: "amount", path: "/cash", target: "cash-amount", permissions: COLLECT },
    { key: "collect", path: "/cash", target: "cash-collect", permissions: COLLECT },
    { key: "close", path: "/cash", target: "cash-close", permissions: ["finance.close_register"] },
  ],
  accountant: [
    { key: "rate", path: "/fees", target: "fees-rate", permissions: ["finance.set_exchange_rate"] },
    { key: "fees", path: "/fees", target: "fees-types", permissions: ["finance.configure_fees"] },
    {
      key: "discount",
      path: "/students",
      target: "students-search",
      permissions: ["finance.grant_discount"],
    },
    {
      key: "cancellations",
      path: "/cancellations",
      target: "cancellations-list",
      permissions: ["finance.approve_cancellation"],
    },
    {
      key: "closings",
      path: "/cash-closings",
      target: "closings-list",
      permissions: ["finance.view_reports"],
    },
    {
      key: "unpaid",
      path: "/unpaid",
      target: "unpaid-list",
      permissions: ["finance.view_reports"],
    },
  ],
};

/** Guide du compte dans l'école : rôle système caissier, sinon comptable ; aucun pendant une
 *  session support. */
export function guideFor(me: Me): GuideKey | null {
  if (me.support) return null;
  const codes = (me.school?.roles ?? []).map((role) => role.code);
  if (codes.includes("cashier")) return "cashier";
  if (codes.includes("accountant")) return "accountant";
  return null;
}

/** Étapes que les droits du compte permettent d'ouvrir. */
export function guideSteps(me: Me, guide: GuideKey): GuideStep[] {
  return GUIDES[guide].filter((step) => can(me, step.permissions));
}

export interface GuideProgress {
  step: number;
  done: boolean;
}

/** Progression par utilisateur et par appareil (M20) ; stockage indisponible : rien de gardé. */
const storageKey = (userId: string, guide: GuideKey) => `mwangaza.guide.${userId}.${guide}`;

export function readProgress(userId: string, guide: GuideKey): GuideProgress | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(storageKey(userId, guide)) ?? "null");
    if (typeof value !== "object" || value === null) return null;
    const { step, done } = value as Partial<GuideProgress>;
    return { step: Number.isInteger(step) ? step! : 0, done: done === true };
  } catch {
    return null;
  }
}

export function saveProgress(userId: string, guide: GuideKey, progress: GuideProgress) {
  try {
    localStorage.setItem(storageKey(userId, guide), JSON.stringify(progress));
  } catch {
    // Navigation privée, stockage plein : le guide reviendra à la prochaine ouverture.
  }
}
