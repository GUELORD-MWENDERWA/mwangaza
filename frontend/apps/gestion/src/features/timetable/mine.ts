// « Mon horaire » (EDT.4b) : l'horaire publié de l'enseignant et de sa classe de titulaire, lu en
// ligne puis gardé sur l'appareil (`reads`), relu à chaque ouverture de l'application : sans
// réseau, la dernière copie s'affiche avec l'heure de sa lecture.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { canOpen, MENU_ITEMS } from "../../lib/menu";
import type { Me } from "../../lib/queries";
import type { LocalDb } from "../../lib/sync/db";
import { readOrKept } from "../../lib/sync/reads";
import { useSyncStatus } from "../../lib/sync/session";

export type MyTimetable = Schemas["MyTimetable"];

const MINE_ID = "timetable|mine";
export const myTimetableKey = ["timetable", "mine"] as const;

const readMine = (db: LocalDb | null) =>
  readOrKept(db?.reads ?? null, MINE_ID, () => call(api.GET("/api/timetable/mine/")));

export function useMyTimetable() {
  const { db } = useSyncStatus();
  return useQuery({ queryKey: myTimetableKey, queryFn: () => readMine(db) });
}

/** À l'ouverture de l'application : l'horaire part sur l'appareil sans attendre qu'on ouvre la
 *  page (lecture sans réseau, spec § 10). Une requête par ouverture, rien sans l'entrée du menu. */
export function useKeepMyTimetable(me: Me) {
  const { db } = useSyncStatus();
  const queryClient = useQueryClient();
  const item = MENU_ITEMS.find((entry) => entry.key === "myTimetable");
  const allowed = Boolean(item && canOpen(me, item) && !me.support);
  useEffect(() => {
    if (allowed && db) {
      void queryClient.prefetchQuery({ queryKey: myTimetableKey, queryFn: () => readMine(db) });
    }
  }, [allowed, db, queryClient]);
}
