// Suivi des présences (lot 10, 6.5 · 6.6) : le jour à l'entrée, absents, personnel, journal des
// corrections et justifications des parents. Tout est calculé par le serveur (rien n'est stocké).
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type Day = Schemas["Day"];
export type Absence = Schemas["Absence"];
export type StaffDay = Schemas["StaffDay"];
export type Correction = Schemas["Correction"];
export type Justification = Schemas["Justification"];
export type DayStatus = Schemas["DayStatusEnum"];
export type AbsenceState = Schemas["AbsenceStateEnum"];

export const followKeys = { all: ["attendance", "follow"] as const };

/** Aujourd'hui (jour local), `AAAA-MM-JJ`. */
export function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Jour voisin (`delta` = ±1) ; `AAAA-MM-JJ` lu à midi pour éviter tout décalage d'heure d'été. */
export function shiftDay(day: string, delta: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + delta);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function useDay(date: string) {
  return useQuery({
    queryKey: [...followKeys.all, "day", date],
    queryFn: () => call(api.GET("/api/attendance/day/", { params: { query: { date } } })),
  });
}

export function useAbsences(
  date: string,
  filter: { classGroup: string; state: "" | AbsenceState },
  page: number,
) {
  return useQuery({
    queryKey: [...followKeys.all, "absences", date, filter, page],
    queryFn: () =>
      call(
        api.GET("/api/attendance/absences/", {
          params: {
            query: {
              date,
              ...(filter.classGroup ? { class_group: filter.classGroup } : {}),
              ...(filter.state ? { state: filter.state } : {}),
              ...(page > 1 ? { page } : {}),
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useStaffDay(date: string, page: number) {
  return useQuery({
    queryKey: [...followKeys.all, "staff", date, page],
    queryFn: () =>
      call(
        api.GET("/api/attendance/staff/", {
          params: { query: { date, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useCorrections(page: number) {
  return useQuery({
    queryKey: [...followKeys.all, "corrections", page],
    queryFn: () =>
      call(
        api.GET("/api/attendance/corrections/", {
          params: { query: page > 1 ? { page } : {} },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useJustifications(status: "" | Justification["status"], page: number) {
  return useQuery({
    queryKey: [...followKeys.all, "justifications", status, page],
    queryFn: () =>
      call(
        api.GET("/api/attendance/justifications/", {
          params: { query: { ...(status ? { status } : {}), ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: followKeys.all });
}

/** « Présent, carte oubliée » : une ligne de plus au journal, jamais un passage modifié. */
export function useCorrect() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: Schemas["CorrectionWriteRequest"]) =>
      call(api.POST("/api/attendance/corrections/", { body })),
    onSuccess: () => void refresh(),
  });
}

export function useDecide() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (input: { id: string; accept: boolean; note: string }) =>
      call(
        api.POST("/api/attendance/justifications/{id}/decide/", {
          params: { path: { id: input.id } },
          body: { accept: input.accept, note: input.note },
        }),
      ),
    onSuccess: () => void refresh(),
  });
}

/** L'école note le mot d'un parent venu à l'école (acceptée d'emblée). */
export function useRecordJustification() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (input: {
      student: string;
      startsOn: string;
      endsOn: string;
      reason: string;
      document: File | null;
    }) => {
      const body = new FormData();
      body.append("student", input.student);
      body.append("starts_on", input.startsOn);
      body.append("ends_on", input.endsOn);
      body.append("reason", input.reason);
      if (input.document) body.append("document", input.document);
      return call(
        api.POST("/api/attendance/justifications/", {
          body: body as unknown as Schemas["SchoolJustificationRequest"],
        }),
      );
    },
    onSuccess: () => void refresh(),
  });
}

export function exportUrl(from: string, to: string, classGroup: string): string {
  const query = new URLSearchParams({ date_from: from, date_to: to });
  if (classGroup) query.set("class_group", classGroup);
  return `/api/attendance/export/?${query.toString()}`;
}
