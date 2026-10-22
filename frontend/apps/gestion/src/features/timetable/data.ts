// Emploi du temps (EDT.1a) : grilles horaires, classes et places, salles, règles générales ;
// EDT.1b : disponibilités des enseignants, contrôles avant le calcul ; EDT.1c : règles de
// l'horaire et ce que leur éditeur propose. Droit `timetable.manage`, module `timetable` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";
import type { Gesture } from "./editor";

export type TimeGrid = Schemas["TimeGrid"];
export type ClassRow = Schemas["TimetableClass"];
export type Room = Schemas["Room"];
export type RoomKind = Schemas["RoomKindEnum"];
export type Rules = Schemas["TimetableRules"];
export type TeacherProfile = Schemas["TeacherProfile"];
export type Checks = Schemas["Checks"];
export type CheckIssue = Schemas["CheckIssue"];
export type Rule = Schemas["TimetableRule"];
export type RuleKind = Schemas["TimetableRuleKindEnum"];
export type RuleStrength = Schemas["RuleStrengthEnum"];
export type RuleChoices = Schemas["RuleChoices"];
export type RuleCourse = Schemas["RuleCourse"];
export type Draft = Schemas["Draft"];
export type DraftState = Schemas["DraftState"];

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

export function useRules(enabled = true) {
  return useQuery({
    enabled,
    queryKey: [...keys.timetable, "constraints"],
    queryFn: () => call(api.GET("/api/timetable/constraints/")),
  });
}

export function useRuleChoices() {
  return useQuery({
    queryKey: [...keys.timetable, "constraint-choices"],
    queryFn: () => call(api.GET("/api/timetable/constraints/choices/")),
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

// Brouillons de l'horaire (EDT.2a). Liste et brouillon sous des clés distinctes : un geste remplace
// l'état du brouillon sans relire la liste.
export const draftListKey = [...keys.timetable, "draftList"];
export const draftKey = (id: string) => [...keys.timetable, "draft", id];

export function useTimetableCourses() {
  return useQuery({
    queryKey: [...keys.timetable, "courses"],
    queryFn: () => call(api.GET("/api/timetable/courses/")),
  });
}

export function useDrafts() {
  return useQuery({
    queryKey: draftListKey,
    queryFn: () => call(api.GET("/api/timetable/drafts/")),
  });
}

export function useDraft(id: string | undefined) {
  return useQuery({
    enabled: Boolean(id),
    queryKey: draftKey(id ?? ""),
    queryFn: () =>
      call(api.GET("/api/timetable/drafts/{id}/", { params: { path: { id: id ?? "" } } })),
  });
}

/** Envoie un geste de l'éditeur ; le serveur renvoie l'état du brouillon (conflits recalculés). */
export function sendGesture(id: string, gesture: Gesture): Promise<DraftState> {
  const entry = (entryId: string) => ({ params: { path: { id, entry: entryId } } });
  const draft = { params: { path: { id } } };
  switch (gesture.kind) {
    case "place": {
      const { course, weekday, first, length } = gesture;
      return call(
        api.POST("/api/timetable/drafts/{id}/entries/", {
          ...draft,
          body: { course, weekday, first, length },
        }),
      );
    }
    case "move":
      return call(
        api.PATCH("/api/timetable/drafts/{id}/entries/{entry}/", {
          ...entry(gesture.entry),
          body: { weekday: gesture.weekday, first: gesture.first },
        }),
      );
    case "room":
      return call(
        api.PATCH("/api/timetable/drafts/{id}/entries/{entry}/", {
          ...entry(gesture.entry),
          body: { room: gesture.room },
        }),
      );
    case "lock":
      return call(
        api.PATCH("/api/timetable/drafts/{id}/entries/{entry}/", {
          ...entry(gesture.entry),
          body: { locked: gesture.locked },
        }),
      );
    case "remove":
      return call(api.DELETE("/api/timetable/drafts/{id}/entries/{entry}/", entry(gesture.entry)));
    case "swap":
      return call(
        api.POST("/api/timetable/drafts/{id}/swap/", {
          ...draft,
          body: { entry: gesture.entry, other: gesture.other },
        }),
      );
    case "undo":
      return call(api.POST("/api/timetable/drafts/{id}/undo/", draft));
  }
}

// Calcul automatique (EDT.3b) : les 10 derniers calculs et le temps permis à l'école, relus toutes
// les 2 s seulement pendant un calcul.
export const runsKey = [...keys.timetable, "runs"];

export function useRuns() {
  return useQuery({
    queryKey: runsKey,
    queryFn: () => call(api.GET("/api/timetable/runs/")),
    refetchInterval: (query) =>
      query.state.data?.runs.some((run) => run.status === "queued" || run.status === "running")
        ? 2000
        : false,
  });
}
