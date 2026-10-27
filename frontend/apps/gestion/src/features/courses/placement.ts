// Séances d'un cours dans l'horaire (EDT.1b) : « 2+2+1 », somme = heures du cours ; vide =
// calculé. Mêmes règles que le serveur (`timetable/placement.py`).
import type { Schemas } from "@mwangaza/api";

type RoomKind = Schemas["RoomKindEnum"] | Schemas["BlankEnum"];

const MAX_SESSION = 12;

/** « 2+2+1 » → [2, 2, 1] ; vide → [] ; illisible → null. */
export function parsePattern(text: string): number[] | null {
  const compact = text.replace(/\s/g, "");
  if (compact === "") return [];
  const parts = compact.split("+");
  if (!parts.every((part) => /^\d+$/.test(part))) return null;
  const values = parts.map(Number);
  return values.every((value) => value >= 1 && value <= MAX_SESSION) ? values : null;
}

/** Séances calculées : des blocs de 2 heures à partir de 4 heures, sinon des heures seules ; un
 *  cours pratique (atelier), des blocs de 4 heures au plus, à parts égales (comme le serveur). */
export function proposedPattern(hours: number, practical = false): string {
  if (hours <= 0) return "";
  if (practical) {
    const count = Math.ceil(hours / 4);
    const base = Math.floor(hours / count);
    const extra = hours % count;
    return Array.from({ length: count }, (_, index) => base + (index < extra ? 1 : 0)).join("+");
  }
  const parts =
    hours >= 4
      ? [...Array<number>(Math.floor(hours / 2)).fill(2), ...(hours % 2 ? [1] : [])]
      : Array<number>(hours).fill(1);
  return parts.join("+");
}

export type PatternProblem = { key: "bad" } | { key: "hours"; sum: number } | null;

/** Ce qui empêchera l'enregistrement, dit avant l'envoi. */
export function patternProblem(text: string, hours: number): PatternProblem {
  const pattern = parsePattern(text);
  if (pattern === null) return { key: "bad" };
  const sum = pattern.reduce((total, value) => total + value, 0);
  if (pattern.length > 0 && sum !== hours) return { key: "hours", sum };
  return null;
}

export type Part = "any" | "morning";

/** Placement d'un cours en cours de saisie ; `room` : "" (salle de la classe), « room:<id> » ou
 *  « kind:<type> ». */
export type PlacementDraft = {
  lesson_pattern: string;
  max_per_day: string;
  room: string;
  can_span_break: boolean | null;
  preferred_part: Part;
};

type Placement = {
  lesson_pattern: string;
  max_per_day: number | null;
  room: string | null;
  room_kind: RoomKind;
  can_span_break: boolean | null;
  preferred_part: Part;
};

export const EMPTY_PLACEMENT: PlacementDraft = {
  lesson_pattern: "",
  max_per_day: "",
  room: "",
  can_span_break: null,
  preferred_part: "any",
};

export const placementDraft = (placement: Placement): PlacementDraft => ({
  lesson_pattern: placement.lesson_pattern,
  max_per_day: placement.max_per_day ? String(placement.max_per_day) : "",
  room: placement.room
    ? `room:${placement.room}`
    : placement.room_kind
      ? `kind:${placement.room_kind}`
      : "",
  can_span_break: placement.can_span_break,
  preferred_part: placement.preferred_part,
});

export const placementBody = (draft: PlacementDraft) => ({
  lesson_pattern: draft.lesson_pattern.replace(/\s/g, ""),
  max_per_day: Number(draft.max_per_day) || null,
  room_id: draft.room.startsWith("room:") ? draft.room.slice(5) : null,
  room_kind: (draft.room.startsWith("kind:") ? draft.room.slice(5) : "") as RoomKind,
  can_span_break: draft.can_span_break,
  preferred_part: draft.preferred_part,
});
