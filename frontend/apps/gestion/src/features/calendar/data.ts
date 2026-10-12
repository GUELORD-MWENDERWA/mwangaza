// Calendrier de l'école (5.7) : événements à venir ou passés (liste paginée, lue par tout le
// personnel), ajout, correction et suppression (droit `announcements.publish`).
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type SchoolEvent = Schemas["SchoolEvent"];
export type EventKind = Schemas["EventKindEnum"];
export type EventAudience = Schemas["EventAudienceEnum"];
export const KINDS: EventKind[] = ["meeting", "exam", "holiday", "activity", "other"];
export const PAGE_SIZE = 50;

export function useEvents(past: boolean, page: number) {
  return useQuery({
    queryKey: [...keys.calendar, past, page],
    queryFn: () => call(api.GET("/api/calendar-events/", { params: { query: { past, page } } })),
    placeholderData: keepPreviousData,
  });
}

export type EventValues = {
  title: string;
  description: string;
  kind: EventKind;
  audience: EventAudience;
  starts_on: string;
  ends_on: string;
  start_time: string;
};

/** Champs vides (fin, heure) : `null` pour le serveur (une journée, toute la journée). */
function body(values: EventValues) {
  return { ...values, ends_on: values.ends_on || null, start_time: values.start_time || null };
}

export function useSaveEvent(id: string | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (values: EventValues) =>
      id
        ? call(
            api.PATCH("/api/calendar-events/{id}/", {
              params: { path: { id } },
              body: body(values),
            }),
          )
        : call(api.POST("/api/calendar-events/", { body: body(values) })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.calendar }),
  });
}

export function useDeleteEvent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE("/api/calendar-events/{id}/", { params: { path: { id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.calendar }),
  });
}
