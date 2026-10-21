// Emploi du temps (EDT.1a) : grilles horaires, classes et places, salles, règles générales ;
// EDT.1b : disponibilités des enseignants, contrôles avant le calcul. Droit `timetable.manage`,
// module `timetable` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type TimeGrid = Schemas["TimeGrid"];
export type ClassRow = Schemas["TimetableClass"];
export type Room = Schemas["Room"];
export type RoomKind = Schemas["RoomKindEnum"];
export type Rules = Schemas["TimetableRules"];
export type TeacherProfile = Schemas["TeacherProfile"];
export type Checks = Schemas["Checks"];
export type CheckIssue = Schemas["CheckIssue"];

export const ROOM_KINDS: RoomKind[] = [
  "classroom",
  "workshop",
  "lab",
  "computer",
  "sports",
  "other",
];

export function useGrids(enabled = true) {
  return useQuery({
    enabled,
    queryKey: [...keys.timetable, "grids"],
    queryFn: () => call(api.GET("/api/timetable/grids/")),
  });
}

export function useTimetableClasses() {
  return useQuery({
    queryKey: [...keys.timetable, "classes"],
    queryFn: () => call(api.GET("/api/timetable/classes/")),
  });
}

export function useRooms(enabled = true) {
  return useQuery({
    enabled,
    queryKey: [...keys.timetable, "rooms"],
    queryFn: () => call(api.GET("/api/timetable/rooms/")),
  });
}

export function useTimetableRules(enabled = true) {
  return useQuery({
    enabled,
    queryKey: [...keys.timetable, "rules"],
    queryFn: () => call(api.GET("/api/timetable/rules/")),
  });
}

export function useTeacherProfiles(enabled = true) {
  return useQuery({
    queryKey: [...keys.timetable, "teachers"],
    queryFn: () => call(api.GET("/api/timetable/teachers/")),
    enabled,
  });
}

export function useTimetableChecks() {
  return useQuery({
    queryKey: [...keys.timetable, "checks"],
    queryFn: () => call(api.GET("/api/timetable/checks/")),
  });
}

/** Écart entre les heures de cours d'une classe et les places de sa grille. */
export function gapOf(
  row: ClassRow,
): { tone: "ok" | "due" | "warn"; key: string; count: number } | null {
  if (row.capacity === null) return null;
  const over = row.course_hours - row.capacity;
  if (over > 0) return { tone: "due", key: "over", count: over };
  if (row.missing_hours > 0) return { tone: "warn", key: "missing", count: row.missing_hours };
  if (over === 0) return { tone: "ok", key: "full", count: 0 };
  return { tone: "ok", key: "free", count: -over };
}
