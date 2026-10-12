// Annonces de l'école à son personnel (5.7) : liste paginée, lue par tout compte de l'école.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type StaffAnnouncement = Schemas["StaffAnnouncement"];
export const PAGE_SIZE = 50;

export function useStaffNews(page: number) {
  return useQuery({
    queryKey: [...keys.staffNews, page],
    queryFn: () => call(api.GET("/api/staff-announcements/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
}
