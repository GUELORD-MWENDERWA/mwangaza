// Annonces aux familles (H4) : liste paginée, familles touchées, publication, archivage.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Announcement = Schemas["Announcement"];
export type Audience = Schemas["AudienceEnum"];
export const PAGE_SIZE = 50;

export function useAnnouncements(page: number) {
  return useQuery({
    queryKey: [...keys.announcements, page],
    queryFn: () => call(api.GET("/api/announcements/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
}

/** Familles qu'une annonce toucherait : « Publier pour 156 familles ». */
export function useRecipients(audience: Audience, classGroups: string[]) {
  const enabled = audience !== "class_groups" || classGroups.length > 0;
  return useQuery({
    queryKey: [...keys.announcements, "recipients", audience, classGroups],
    queryFn: () =>
      call(
        api.GET("/api/announcements/recipients/", {
          params: { query: { audience, class_groups: classGroups } },
        }),
      ),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export type NewAnnouncement = {
  title: string;
  body: string;
  audience: Audience;
  class_groups: string[];
  attachment: File | null;
};

export function usePublish() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (announcement: NewAnnouncement) => {
      const body = new FormData();
      body.append("title", announcement.title);
      body.append("body", announcement.body);
      body.append("audience", announcement.audience);
      if (announcement.audience === "class_groups") {
        for (const id of announcement.class_groups) body.append("class_groups", id);
      }
      if (announcement.attachment) body.append("attachment", announcement.attachment);
      const options = { body: body as unknown as Schemas["AnnouncementCreateRequest"] };
      return call(api.POST("/api/announcements/", options));
    },
    onSuccess: () => client.invalidateQueries({ queryKey: keys.announcements }),
  });
}

export function useArchive() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      call(api.POST("/api/announcements/{id}/archive/", { params: { path: { id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.announcements }),
  });
}
