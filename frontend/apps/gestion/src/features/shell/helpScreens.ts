// Table écran → article d'aide (AIDE.2) : premier segment de l'adresse → clé de l'article
// (`backend/apps/core/help/<langue>/gestion/<clé>.md`). Écran sans article : la liste de l'aide.
import type { ScreenTable } from "@mwangaza/help";

export const HELP_SCREENS: ScreenTable = {
  students: "enroll-student",
  families: "enroll-student",
  timetable: "timetable",
  "my-timetable": "timetable",
  "time-grid": "timetable",
  grades: "enter-grades",
  "grade-sheets": "enter-grades",
  homeroom: "enter-grades",
  "report-cards": "print-class-report-cards",
  cash: "take-payment",
  unpaid: "follow-unpaid",
  fees: "set-fees",
  expenses: "record-expense",
  budget: "follow-budget",
  cancellations: "cancel-payment",
  "cash-closings": "close-cash-register",
  settings: "school-settings",
  organisation: "school-settings",
  roles: "manage-roles",
  staff: "manage-roles",
  devices: "work-offline",
  support: "contact-support",
  help: "contact-support",
};
