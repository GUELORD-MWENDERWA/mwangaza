// Pointage à l'entrée sans réseau (lot 10, 6.3) : la liste des personnes (élèves inscrits et
// personnel, avec l'empreinte de leur carte) est gardée sur l'appareil (`db.reads`). Chaque lecture
// est décidée seule d'après cette liste : arrivé, en retard, déjà passé ou refusé. Un passage va
// dans la file (`attendance.scan`) avec son identifiant : rejoué, il n'est jamais écrit deux fois ;
// le serveur applique les mêmes règles.
import { api, call, type Schemas } from "@mwangaza/api";

import { uuidv7 } from "../../lib/ids";
import type { LocalDb } from "../../lib/sync/db";
import { isNetworkError, keep, kept } from "../../lib/sync/reads";
import { syncNow } from "../../lib/sync/session";

export const SCAN_OP = "attendance.scan";
export const TOKEN_PREFIX = "MWZ1:";
const ROSTER_ID = "attendance|roster";
const passagesId = (day: string) => `attendance|passages|${day}`;

export type RosterPerson = {
  /** Élève (`student`) ou membre du personnel (`member`). */
  kind: "student" | "member";
  id: string;
  name: string;
  /** Matricule d'un élève ; vide pour le personnel. */
  matricule: string;
  detail: string;
  cardHash: string;
  photo: string | null;
};

export type Roster = {
  version: string;
  lateAfter: string;
  matriculeCheck: boolean;
  people: RosterPerson[];
};

export type Outcome = "arrived" | "late" | "already" | "refused";
export type Passage = {
  id: string;
  personId: string;
  kind: "student" | "member";
  name: string;
  detail: string;
  photo: string | null;
  seenAt: string;
  outcome: Outcome;
};
export type Reading =
  | { outcome: "arrived" | "late" | "already"; person: RosterPerson; passage: Passage }
  | { outcome: "refused"; reason: "unknown" | "mistyped" };

/** SHA-256 en hexadécimal du jeton lu (le serveur ne garde que cette empreinte). */
export async function tokenHash(token: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

// Algorithme de Damm : même table que le serveur (`schools/matricule.py`).
const DAMM = [
  [0, 3, 1, 7, 5, 9, 8, 6, 4, 2],
  [7, 0, 9, 2, 1, 5, 4, 8, 6, 3],
  [4, 2, 0, 6, 8, 7, 1, 3, 5, 9],
  [1, 7, 5, 0, 9, 8, 3, 4, 2, 6],
  [6, 1, 2, 3, 0, 4, 5, 9, 7, 8],
  [3, 6, 7, 4, 2, 0, 9, 5, 8, 1],
  [5, 8, 6, 9, 7, 2, 0, 1, 3, 4],
  [8, 9, 4, 5, 3, 6, 2, 0, 1, 7],
  [9, 4, 3, 8, 6, 1, 7, 2, 0, 5],
  [2, 5, 8, 1, 4, 3, 6, 7, 9, 0],
];

/** Matricule tapé dont la dernière clé est juste (chiffres seulement). */
export function checkOk(value: string): boolean {
  if (!/\d$/.test(value)) return false;
  let interim = 0;
  for (const char of value) if (/\d/.test(char)) interim = DAMM[interim]![Number(char)]!;
  return interim === 0;
}

/** Heure locale « HH:MM » d'un instant : comparée à l'heure limite de l'école. */
function localClock(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}:${String(date.getSeconds()).padStart(2, "0")}`;
}

/** Jour local « AAAA-MM-JJ ». */
export function localDay(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export type Input = { card: string } | { matricule: string };

/** Décision de l'appareil pour une lecture. `passed` : personnes déjà passées aujourd'hui. */
export async function read(
  roster: Roster,
  input: Input,
  passed: ReadonlyMap<string, Passage>,
  now = new Date(),
): Promise<Reading> {
  let person: RosterPerson | undefined;
  if ("card" in input) {
    const text = input.card.trim();
    if (!text.startsWith(TOKEN_PREFIX)) return { outcome: "refused", reason: "unknown" };
    const hash = await tokenHash(text.slice(TOKEN_PREFIX.length));
    person = roster.people.find((candidate) => candidate.cardHash === hash);
    if (!person) return { outcome: "refused", reason: "unknown" };
  } else {
    const typed = input.matricule.trim().toUpperCase();
    person = roster.people.find((candidate) => candidate.matricule.toUpperCase() === typed);
    if (!person) {
      const mistyped = roster.matriculeCheck && /\d$/.test(typed) && !checkOk(typed);
      return { outcome: "refused", reason: mistyped ? "mistyped" : "unknown" };
    }
  }
  const earlier = passed.get(person.id);
  if (earlier) return { outcome: "already", person, passage: earlier };
  const late = localClock(now) > `${roster.lateAfter}:00`;
  const passage: Passage = {
    id: uuidv7(now.getTime()),
    personId: person.id,
    kind: person.kind,
    name: person.name,
    detail: person.detail,
    photo: person.photo,
    seenAt: now.toISOString(),
    outcome: late ? "late" : "arrived",
  };
  return { outcome: passage.outcome as "late" | "arrived", person, passage };
}

type RosterPage = Schemas["Roster"];

/** Liste à jour : relue en ligne (rien n'est envoyé si la version n'a pas changé), sinon celle
 *  gardée sur l'appareil. `null` : jamais chargée (une connexion est nécessaire une fois). */
export async function loadRoster(db: LocalDb): Promise<{ roster: Roster | null; fresh: boolean }> {
  const saved = (await kept<Roster>(db.reads, ROSTER_ID))?.value ?? null;
  try {
    const people: RosterPerson[] = [];
    let first: RosterPage | null = null;
    let after: string | undefined;
    for (;;) {
      const page: RosterPage = await call(
        api.GET("/api/attendance/roster/", {
          params: { query: { ...(after ? { after } : { version: saved?.version }) } },
        }),
      );
      if (!first) {
        first = page;
        if (page.unchanged && saved) {
          return { roster: { ...saved, lateAfter: page.late_after }, fresh: true };
        }
      }
      for (const row of page.students)
        people.push({
          kind: "student",
          id: row.student,
          name: row.name,
          matricule: row.matricule,
          detail: row.class_name,
          cardHash: row.card_hash,
          photo: row.photo ?? null,
        });
      for (const row of page.staff)
        people.push({
          kind: "member",
          id: row.member,
          name: row.name,
          matricule: "",
          detail: "",
          cardHash: row.card_hash,
          photo: row.photo ?? null,
        });
      if (!page.next) break;
      after = page.next;
    }
    const roster: Roster = {
      version: first!.version,
      lateAfter: first!.late_after,
      matriculeCheck: first!.matricule_check,
      people,
    };
    await keep(db.reads, ROSTER_ID, roster);
    return { roster, fresh: true };
  } catch (error) {
    if (isNetworkError(error)) return { roster: saved, fresh: false };
    throw error;
  }
}

/** Passages de l'appareil pour un jour, plus récent en premier. */
export async function dayPassages(db: LocalDb, day: string): Promise<Passage[]> {
  return (await kept<Passage[]>(db.reads, passagesId(day)))?.value ?? [];
}

/** Garde le passage sur l'appareil et dans la file d'envoi (une seule transaction). */
export async function recordPassage(db: LocalDb, passage: Passage, cardHash: string) {
  const day = localDay(new Date(passage.seenAt));
  const known = await dayPassages(db, day);
  await db.transaction("rw", db.reads, db.outbox, async () => {
    await db.reads.put({
      id: passagesId(day),
      value: [passage, ...known].slice(0, 2000),
      readAt: Date.now(),
    });
    await db.outbox.add({
      op_id: uuidv7(),
      type: SCAN_OP,
      payload: {
        id: passage.id,
        seen_at: passage.seenAt,
        ...(cardHash
          ? { card_hash: cardHash }
          : passage.kind === "student"
            ? { student: passage.personId }
            : { member: passage.personId }),
      },
      created_at: new Date().toISOString(),
      status: "pending",
      error: null,
    });
  });
  void syncNow();
}

/** Nombre de passages refusés par le serveur (carte révoquée entre-temps…), à montrer. */
export async function rejectedScans(db: LocalDb) {
  const all = await db.outbox.where("status").equals("rejected").toArray();
  return all.filter((op) => op.type === SCAN_OP);
}
