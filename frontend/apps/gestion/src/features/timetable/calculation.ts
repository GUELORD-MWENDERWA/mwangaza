// Calcul automatique de l'horaire (EDT.3b, spec § 7) : ce que l'écran dit d'un calcul. Le serveur
// rend des codes et des chiffres (EDT.3a) ; ici, les phrases et l'écran qui corrige.
import type { Schemas } from "@mwangaza/api";
import type { TFunction } from "@mwangaza/i18n";

export type Run = Schemas["Run"];
export type RunStatus = Schemas["RunStatusEnum"];
export type RunScope = Schemas["ScopeEnum"];
type Blocking = Schemas["RunBlocking"];
type Unmet = Schemas["RunUnmet"];
type Described = { subject: string; text: string } | undefined;

export const isActive = (run: Run | undefined) =>
  run?.status === "queued" || run?.status === "running";

export const STATUS_TONE: Record<RunStatus, "ok" | "due" | "warn" | "info" | "gray"> = {
  queued: "info",
  running: "info",
  done: "ok",
  infeasible: "due",
  timeout: "warn",
  error: "due",
  cancelled: "gray",
};

const TIME_CHOICES = [30, 60, 120, 180];

/** Temps proposés : jusqu'au maximum de l'école (console), lui compris. */
export function timeChoices(max: number): number[] {
  const shown = TIME_CHOICES.filter((seconds) => seconds <= max);
  return shown.includes(max) ? shown : [...shown, max];
}

export const defaultTime = (max: number) => Math.min(60, max);

/** 0:23, 1:00, 3:00. */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** Où corriger : un écran, ou « tout recalculer » (le reste de l'horaire, gardé, bloque). */
export type Fix =
  | { to: string; label: "rule" | "teacher" | "class" | "grid" | "editor" }
  | { to: null; label: "all" };

export type Reason = { subject: string; text: string; fix?: Fix };

const number = (values: Blocking["values"] | undefined, key: string) => Number(values?.[key] ?? 0);

/** Une règle qui bloque, en phrase, avec l'écran qui la corrige. `rule` : la phrase de la règle
 *  (sujet, consigne), absente si elle a été supprimée depuis. */
export function blockingReason(
  row: Blocking,
  draft: string,
  rule: (id: string) => Described,
  t: TFunction,
): Reason {
  const subject = row.subject ?? "";
  const values = row.values;
  const classFix: Fix = { to: `/courses?class=${row.class_group}`, label: "class" };
  const teacherFix: Fix = { to: "/teaching-loads", label: "teacher" };
  switch (row.code) {
    case "rule": {
      const described = rule(row.rule);
      const fix: Fix = { to: `/timetable-checks?rule=${row.rule}`, label: "rule" };
      return described
        ? {
            subject: described.subject,
            text: t("timetable.calculation.blocking.rule", {
              rule: described.text.replace(/\.$/, ""),
            }),
            fix,
          }
        : { subject, text: t("timetable.calculation.blocking.ruleGone"), fix };
    }
    case "absence":
      return {
        subject,
        text: t("timetable.calculation.blocking.absence", {
          due: number(values, "due"),
          available: number(values, "available"),
        }),
        fix: teacherFix,
      };
    case "teacher_day":
      return {
        subject,
        text: t("timetable.calculation.blocking.teacher_day", {
          max: number(values, "max"),
          due: number(values, "due"),
        }),
        fix: teacherFix,
      };
    case "course_day":
      return {
        subject,
        text: t("timetable.calculation.blocking.course_day", {
          max: number(values, "max"),
          hours: number(values, "hours"),
        }),
        fix: classFix,
      };
    case "unit":
      return { subject, text: t("timetable.calculation.blocking.unit"), fix: classFix };
    case "no_gaps":
      return {
        subject,
        text: t("timetable.calculation.blocking.no_gaps"),
        fix: { to: "/time-grid", label: "grid" },
      };
    case "locks":
      return {
        subject,
        text: t("timetable.calculation.blocking.locks"),
        fix: { to: `/timetable?draft=${draft}&class=${row.class_group}`, label: "editor" },
      };
    case "frozen":
      return {
        subject: t("timetable.calculation.blocking.frozenSubject"),
        text: t("timetable.calculation.blocking.frozen"),
        fix: { to: null, label: "all" },
      };
    default:
      return { subject, text: t("timetable.calculation.blocking.other") };
  }
}

/** Un souhait non tenu : la règle en phrase, ou un réglage de l'école. */
export function unmetReason(
  row: Unmet,
  rule: (id: string) => Described,
  t: TFunction,
): { subject: string; text: string } {
  if (row.code === "rule") {
    return rule(row.rule ?? "") ?? { subject: t("timetable.calculation.unmet.ruleGone"), text: "" };
  }
  if (row.code === "morning" || row.code === "moved") {
    return {
      subject: t(`timetable.calculation.unmet.${row.code}`),
      text: t(`timetable.calculation.unmet.${row.code}Text`),
    };
  }
  return { subject: t("timetable.calculation.unmet.other"), text: "" };
}
