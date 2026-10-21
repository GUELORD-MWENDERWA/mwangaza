// Menu de la Gestion (maquettes, `maquettes/outils/maquettes.py`, MENU) : chaque entrée n'apparaît
// qu'avec un de ses droits (`04` § 8). Entrées V1.1 et V1.2 (notes, présences, paie) : absentes
// en V1.0. Écran pas encore construit (`SCREENS` de `routes.tsx`) : « bientôt disponible ».
import type { Schemas } from "@mwangaza/api";
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
  /** Vide : tout le personnel de l'école (annonces au personnel, calendrier). */
  permissions: readonly Permission[];
  /** Tâche du plan qui construit l'écran. */
  task: string;
  /** Seulement pour le titulaire d'une classe de l'année en cours (« Ma classe », NB.3). */
  homeroom?: boolean;
  /** Module de l'école sans lequel l'écran ne sert à rien, en plus du droit (passage de classe :
   *  droit des élèves, décisions de la délibération). */
  module?: Schemas["ModulesEnum"];
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
      {
        key: "courses",
        path: "courses",
        icon: "book",
        permissions: ["courses.configure"],
        task: "8.1",
      },
      {
        key: "teachingLoads",
        path: "teaching-loads",
        icon: "clock",
        permissions: ["courses.configure"],
        task: "8.1",
      },
      {
        key: "timeGrid",
        path: "time-grid",
        icon: "calendar",
        permissions: ["timetable.manage"],
        task: "EDT.1a",
      },
      {
        key: "rooms",
        path: "rooms",
        icon: "school",
        permissions: ["timetable.manage"],
        task: "EDT.1a",
      },
      {
        key: "timetableChecks",
        path: "timetable-checks",
        icon: "check",
        permissions: ["timetable.manage"],
        task: "EDT.1b",
      },
      {
        key: "timetable",
        path: "timetable",
        icon: "calendar",
        permissions: ["timetable.manage"],
        task: "EDT.2a",
      },
      {
        key: "grades",
        path: "grades",
        icon: "edit",
        permissions: ["grades.enter", "grades.enter_any"],
        task: "8.2.1",
      },
      {
        key: "homeroom",
        path: "homeroom",
        icon: "users",
        permissions: ["grades.enter", "grades.enter_any", "grades.validate"],
        task: "NB.3",
        homeroom: true,
      },
      {
        key: "gradeValidation",
        path: "grade-validation",
        icon: "shield",
        permissions: ["grades.validate"],
        task: "8.2.2",
      },
      {
        key: "reportCards",
        path: "report-cards",
        icon: "print",
        permissions: ["grades.enter_any", "grades.validate"],
        task: "8.3.2",
      },
      {
        key: "gradeSheets",
        path: "grade-sheets",
        icon: "file",
        permissions: ["grades.enter", "grades.enter_any", "grades.validate"],
        task: "8.3.6",
      },
      {
        key: "conduct",
        path: "conduct",
        icon: "alert",
        permissions: ["discipline.record", "discipline.override"],
        task: "8.5.1a",
      },
      {
        key: "conductScale",
        path: "conduct-scale",
        icon: "tag",
        permissions: ["discipline.configure"],
        task: "8.5.1a",
      },
      {
        key: "application",
        path: "application",
        icon: "tag",
        permissions: ["grades.enter", "grades.enter_any", "grades.validate"],
        task: "8.5.1c",
      },
      {
        key: "resits",
        path: "resits",
        icon: "tag",
        permissions: ["grades.enter", "grades.enter_any", "grades.validate"],
        task: "8.4.1",
      },
      {
        key: "deliberation",
        path: "deliberation",
        icon: "tag",
        // Membres du conseil (NB.5) : direction des études, titulaire, enseignants de la classe.
        permissions: ["grades.enter", "grades.enter_any", "grades.validate"],
        task: "8.4.2",
      },
      {
        key: "situations",
        path: "situations",
        icon: "print",
        permissions: ["grades.validate"],
        task: "8.4.4",
      },
      {
        key: "promotion",
        path: "promotion",
        icon: "users",
        permissions: ["students.edit"],
        module: "academics",
        task: "8.4.5",
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
      { key: "staffNews", path: "staff-news", icon: "bell", permissions: [], task: "5.7" },
      { key: "calendar", path: "calendar", icon: "calendar", permissions: [], task: "5.7" },
      {
        key: "announcements",
        path: "announcements",
        icon: "megaphone",
        permissions: ["announcements.publish"],
        task: "4.3",
      },
      {
        key: "summons",
        path: "summons",
        icon: "file",
        permissions: ["announcements.publish"],
        task: "5.7",
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

/** L'entrée est-elle permise au compte ? Sans droit demandé : à tout le personnel. */
export function canOpen(me: Me, item: MenuItem): boolean {
  if (item.module && !me.school?.modules.includes(item.module)) return false;
  if (item.homeroom && !me.school?.homeroom) return false;
  return item.permissions.length === 0 || can(me, item.permissions);
}

/** Sections du menu et leurs entrées permises au compte (une section vide n'apparaît pas). */
export function visibleMenu(me: Me) {
  return MENU.map(({ section, items }) => ({
    section,
    items: items.filter((item) => canOpen(me, item)),
  })).filter(({ items }) => items.length > 0);
}
