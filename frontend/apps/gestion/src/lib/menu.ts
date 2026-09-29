// Menu de la Gestion (maquettes, `maquettes/outils/maquettes.py`, MENU) : chaque entrée n'apparaît
// qu'avec un de ses droits (`04` § 8). Entrées V1.1 et V1.2 (notes, présences, paie) : absentes
// en V1.0. Écran pas encore construit (`SCREENS` de `routes.tsx`) : « bientôt disponible ».
import type { fr } from "@mwangaza/i18n";
import type { IconName } from "@mwangaza/ui";

import { can, type Permission } from "./permissions";
import type { Me } from "./queries";

export type MenuKey = keyof typeof fr.shell.menu;
export type SectionKey = keyof typeof fr.shell.sections;

export type MenuItem = {
  key: MenuKey;
  path: string;
  icon: IconName;
  permissions: readonly Permission[];
  /** Tâche du plan qui construit l'écran. */
  task: string;
};

export const MENU: { section: SectionKey; items: MenuItem[] }[] = [
  {
    section: "steering",
    items: [
      {
        key: "dashboard",
        path: "dashboard",
        icon: "home",
        permissions: ["finance.view_reports"],
        task: "4.2",
      },
    ],
  },
  {
    section: "schooling",
    items: [
      {
        key: "students",
        path: "students",
        icon: "students",
        permissions: ["students.view"],
        task: "2.2",
      },
    ],
  },
  {
    section: "finance",
    items: [
      {
        key: "cash",
        path: "cash",
        icon: "cash",
        permissions: ["finance.collect_payment"],
        task: "3.1",
      },
      {
        key: "unpaid",
        path: "unpaid",
        icon: "alert",
        permissions: ["finance.view_reports"],
        task: "4.1",
      },
      {
        key: "fees",
        path: "fees",
        icon: "tag",
        permissions: [
          "finance.configure_fees",
          "finance.set_exchange_rate",
          "finance.grant_discount",
        ],
        task: "2.5",
      },
      {
        key: "cancellations",
        path: "cancellations",
        icon: "undo",
        permissions: ["finance.request_cancellation", "finance.approve_cancellation"],
        task: "3.8",
      },
      {
        key: "closings",
        path: "cash-closings",
        icon: "lock",
        permissions: ["finance.view_reports"],
        task: "3.8",
      },
      {
        key: "credits",
        path: "credits",
        icon: "credit",
        permissions: ["finance.view_reports", "finance.approve_cancellation"],
        task: "3.6",
      },
    ],
  },
  {
    section: "communication",
    items: [
      {
        key: "announcements",
        path: "announcements",
        icon: "megaphone",
        permissions: ["announcements.publish"],
        task: "4.3",
      },
      {
        key: "parentRequests",
        path: "parent-requests",
        icon: "inbox",
        permissions: ["students.edit"],
        task: "4.4",
      },
    ],
  },
  {
    section: "settings",
    items: [
      {
        key: "schoolSettings",
        path: "settings",
        icon: "settings",
        permissions: ["school.configure"],
        task: "1.7",
      },
      {
        key: "organisation",
        path: "organisation",
        icon: "school",
        permissions: ["classes.manage"],
        task: "1.7",
      },
      {
        key: "staff",
        path: "staff",
        icon: "userplus",
        permissions: ["roles.manage"],
        task: "1.7",
      },
      {
        key: "roles",
        path: "roles",
        icon: "shield",
        permissions: ["roles.manage"],
        task: "1.7",
      },
      {
        key: "devices",
        path: "devices",
        icon: "sync",
        // Appareils de l'école : `roles.manage` ; cet appareil et sa file : qui se synchronise.
        permissions: ["roles.manage", "students.view", "finance.collect_payment"],
        task: "3.7",
      },
      {
        key: "audit",
        path: "audit",
        icon: "journal",
        permissions: ["audit.view"],
        task: "1.7",
      },
    ],
  },
];

export const MENU_ITEMS = MENU.flatMap(({ items }) => items);

/** Sections du menu et leurs entrées permises au compte (une section vide n'apparaît pas). */
export function visibleMenu(me: Me) {
  return MENU.map(({ section, items }) => ({
    section,
    items: items.filter((item) => can(me, item.permissions)),
  })).filter(({ items }) => items.length > 0);
}
