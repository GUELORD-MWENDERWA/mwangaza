// Règles de l'emploi du temps (EDT.1c, spec § 5) : paramètres de départ de chaque kind, et la
// phrase qui dit une règle à l'écran (sujet en gras, puis la consigne). Le serveur vérifie tout
// (schéma par kind) ; ici, seulement l'affichage et la saisie.
import type { TFunction } from "@mwangaza/i18n";

import type { Room, RuleChoices, RuleCourse, RuleKind } from "./data";

export const RULE_KINDS: RuleKind[] = [
  "fixed_lesson",
  "course_not_slot",
  "course_part_of_day",
  "parallel_courses",
  "joint_courses",
  "room_unavailable",
  "spread_over_week",
  "teacher_compact",
  "teacher_free_day",
];
export const CATEGORIES = ["main", "option", "practical", "general"] as const;

export type Scope = "all" | "category" | "name" | "course";
export type Target = { scope: Scope; value: string };
export type Params = {
  course?: string;
  courses?: string[];
  room?: string | null;
  teacher?: string | null;
  target?: Target;
  weekday?: number | null;
  first?: number;
  last?: number | boolean;
  lessons?: number[];
  part?: "morning" | "afternoon";
  start?: string;
  end?: string;
  no_consecutive_days?: boolean;
};

export type Lookup = {
  courses: Map<string, RuleCourse>;
  teachers: Map<string, string>;
  rooms: Map<string, Room>;
};

export function lookupOf(choices: RuleChoices | undefined, rooms: Room[] | undefined): Lookup {
  return {
    courses: new Map((choices?.courses ?? []).map((course) => [course.id, course])),
    teachers: new Map((choices?.teachers ?? []).map((teacher) => [teacher.id, teacher.name])),
    rooms: new Map((rooms ?? []).map((room) => [room.id, room])),
  };
}

export function emptyParams(kind: RuleKind): Params {
  switch (kind) {
    case "fixed_lesson":
      return { course: "", weekday: 1, first: 1, last: 1, room: null };
    case "course_not_slot":
      return { target: { scope: "name", value: "" }, weekday: null, lessons: [], last: false };
    case "course_part_of_day":
      return { target: { scope: "category", value: "main" }, part: "morning", weekday: null };
    case "parallel_courses":
    case "joint_courses":
      return { courses: [] };
    case "room_unavailable":
      return { room: "", weekday: 6 };
    case "spread_over_week":
      return { target: { scope: "all", value: "" }, no_consecutive_days: true };
    case "teacher_compact":
      return { teacher: null };
    case "teacher_free_day":
      return { teacher: "", weekday: 3 };
  }
}

/** Assez rempli pour l'envoyer ; le serveur dit le reste. */
export function isComplete(kind: RuleKind, params: Params): boolean {
  const target = params.target;
  if (target && target.scope !== "all" && !target.value) return false;
  switch (kind) {
    case "fixed_lesson":
      return Boolean(params.course);
    case "course_not_slot":
      return params.weekday != null || Boolean(params.lessons?.length) || params.last === true;
    case "parallel_courses":
    case "joint_courses":
      return (params.courses?.length ?? 0) >= 2;
    case "room_unavailable":
      return Boolean(params.room) && Boolean(params.start) === Boolean(params.end);
    case "teacher_free_day":
      return Boolean(params.teacher);
    default:
      return true;
  }
}

/** Nom du jour, en minuscules en français (« lundi ») : 1er janvier 2024 = un lundi. */
export function dayName(weekday: number, language: string): string {
  const date = new Date(Date.UTC(2024, 0, weekday));
  return new Intl.DateTimeFormat(language, { weekday: "long", timeZone: "UTC" }).format(date);
}

/** « à la 2e heure » ou « de la 2e à la 7e heure ». */
export function hoursText(first: number, last: number, t: TFunction): string {
  const nth = (count: number) => t("timetable.constraints.nth", { count });
  return first === last
    ? t("timetable.constraints.atHour", { hour: nth(first) })
    : t("timetable.constraints.fromTo", { first: nth(first), last: nth(last) });
}

export const courseLabel = (course: RuleCourse) => `${course.name} · ${course.class_name}`;

function list(items: string[], language: string, type: "conjunction" | "disjunction"): string {
  return new Intl.ListFormat(language, { style: "long", type }).format(items);
}

export function targetLabel(target: Target | undefined, lookup: Lookup, t: TFunction): string {
  if (!target || target.scope === "all") return t("timetable.constraints.allCourses");
  if (target.scope === "category") {
    return t(`timetable.constraints.categories.${target.value as (typeof CATEGORIES)[number]}`);
  }
  if (target.scope === "name") return target.value;
  const course = lookup.courses.get(target.value);
  return course ? courseLabel(course) : t("timetable.constraints.missing");
}

/** La règle en une phrase : le sujet (cours, salle, enseignant), puis la consigne. */
export function describe(
  rule: { kind: RuleKind; params: Record<string, unknown> },
  lookup: Lookup,
  t: TFunction,
  language: string,
): { subject: string; text: string } {
  const params = rule.params as Params;
  const missing = t("timetable.constraints.missing");
  const day = (weekday: number) => dayName(weekday, language);
  const teacher = (id: string | null | undefined) =>
    id ? (lookup.teachers.get(id) ?? missing) : t("timetable.constraints.allTeachers");
  const room = (id: string | null | undefined) => (id ? lookup.rooms.get(id)?.name : undefined);
  const courses = (params.courses ?? []).map((id) => lookup.courses.get(id));
  const known = courses.filter((course): course is RuleCourse => Boolean(course));

  switch (rule.kind) {
    case "fixed_lesson": {
      const course = lookup.courses.get(params.course ?? "");
      const where = room(params.room);
      const text = t("timetable.constraints.text.fixed_lesson", {
        day: day(params.weekday ?? 1),
        hours: hoursText(params.first ?? 1, Number(params.last ?? 1), t),
      });
      return {
        subject: course ? courseLabel(course) : missing,
        text: where ? `${text} ${t("timetable.constraints.text.inRoom", { room: where })}` : text,
      };
    }
    case "course_not_slot": {
      const hours = [
        ...(params.lessons ?? []).map((count) => t("timetable.constraints.nth", { count })),
        ...(params.last === true ? [t("timetable.constraints.lastHour")] : []),
      ];
      const key =
        hours.length === 0 ? "notSlotDay" : params.weekday ? "notSlotDayHours" : "notSlotHours";
      return {
        subject: targetLabel(params.target, lookup, t),
        text: t(`timetable.constraints.text.${key}`, {
          day: params.weekday ? day(params.weekday) : "",
          hours: list(hours, language, "disjunction"),
        }),
      };
    }
    case "course_part_of_day":
      return {
        subject: targetLabel(params.target, lookup, t),
        text: params.weekday
          ? t(`timetable.constraints.text.${params.part ?? "morning"}Day`, {
              day: day(params.weekday),
            })
          : t(`timetable.constraints.text.${params.part ?? "morning"}`),
      };
    case "parallel_courses":
      return {
        subject: known.length
          ? `${list(
              known.map((course) => course.name),
              language,
              "conjunction",
            )} · ${known[0]?.class_name}`
          : missing,
        text: t("timetable.constraints.text.parallel_courses"),
      };
    case "joint_courses":
      return {
        subject: known.length
          ? `${known[0]?.name} · ${list(
              known.map((course) => course.class_name),
              language,
              "conjunction",
            )}`
          : missing,
        text: t("timetable.constraints.text.joint_courses", {
          teacher: teacher(known[0]?.teacher ?? ""),
        }),
      };
    case "room_unavailable":
      return {
        subject: room(params.room) ?? missing,
        text: params.start
          ? t("timetable.constraints.text.roomHours", {
              day: day(params.weekday ?? 1),
              start: params.start,
              end: params.end,
            })
          : t("timetable.constraints.text.roomDay", { day: day(params.weekday ?? 1) }),
      };
    case "spread_over_week":
      return {
        subject: targetLabel(params.target, lookup, t),
        text: t(
          params.no_consecutive_days
            ? "timetable.constraints.text.spreadNotInRow"
            : "timetable.constraints.text.spread",
        ),
      };
    case "teacher_compact":
      return {
        subject: teacher(params.teacher),
        text: t("timetable.constraints.text.teacher_compact"),
      };
    case "teacher_free_day":
      return {
        subject: teacher(params.teacher),
        text: params.weekday
          ? t("timetable.constraints.text.freeDay", { day: day(params.weekday) })
          : t("timetable.constraints.text.anyFreeDay"),
      };
  }
}
