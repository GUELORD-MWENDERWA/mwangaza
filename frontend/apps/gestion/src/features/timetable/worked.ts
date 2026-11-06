// Heures prestées (EDT.6) : le mois calculé à la demande, les exceptions notées, les fiches.
import { api, call, type Schemas } from "@mwangaza/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type WorkedMonth = Schemas["WorkedMonth"];
export type LessonException = Schemas["LessonException"];
export type ExceptionKind = Schemas["LessonExceptionKindEnum"];
export type ExceptionBody = Schemas["LessonExceptionWriteRequest"];

const workedKey = [...keys.timetable, "worked"];

export function useWorkedMonth(month: string) {
  return useQuery({
    queryKey: [...workedKey, "month", month],
    queryFn: () => call(api.GET("/api/timetable/worked/", { params: { query: { month } } })),
  });
}

export function useExceptions(month: string, kind: ExceptionKind | "", page: number) {
  return useQuery({
    queryKey: [...workedKey, "exceptions", month, kind, page],
    queryFn: () =>
      call(
        api.GET("/api/timetable/worked/exceptions/", {
          params: { query: { month, page, ...(kind ? { kind } : {}) } },
        }),
      ),
  });
}

/** Les heures de l'horaire publié d'un enseignant un jour donné (à cocher). */
export function useDayLessons(date: string, teacher: string) {
  return useQuery({
    enabled: Boolean(date && teacher),
    queryKey: [...workedKey, "day", date, teacher],
    queryFn: () =>
      call(api.GET("/api/timetable/worked/day/", { params: { query: { date, teacher } } })),
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: workedKey });
}

export function useRecordException() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: ExceptionBody) =>
      call(api.POST("/api/timetable/worked/exceptions/", { body })),
    onSuccess: refresh,
  });
}

export function useCancelException() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      call(
        api.POST("/api/timetable/worked/exceptions/{id}/cancel/", {
          params: { path: { id } },
          body: { reason },
        }),
      ),
    onSuccess: refresh,
  });
}

export const sheetUrl = (month: string, teacher: string) =>
  `/api/timetable/worked/sheet/?month=${month}&teacher=${teacher}&output=pdf`;
export const exportUrl = (month: string) => `/api/timetable/worked/export/?month=${month}`;

export function shiftMonth(month: string, delta: number): string {
  const [year, number] = month.split("-").map(Number) as [number, number];
  const date = new Date(Date.UTC(year, number - 1 + delta, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}
