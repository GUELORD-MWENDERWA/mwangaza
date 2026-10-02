import { api, call } from "@mwangaza/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type PortalFilter = "not_activated" | "all";

/** Familles qui ont activé leur compte du portail : école, puis chaque classe de l'année (H7). */
export function useActivation() {
  return useQuery({
    queryKey: [...keys.families, "activation"],
    queryFn: () => call(api.GET("/api/families/activation/")),
  });
}

/** Familles des élèves actifs d'une classe, dans l'ordre de la liste de classe. */
export function useClassFamilies(classGroup: string, portal: PortalFilter, page: number) {
  return useQuery({
    queryKey: [...keys.families, "class", classGroup, portal, page],
    queryFn: () =>
      call(
        api.GET("/api/families/", {
          params: {
            query: {
              class_group: classGroup,
              ...(portal === "all" ? {} : { portal }),
              ...(page > 1 ? { page } : {}),
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** Lettres d'une classe (familles qui peuvent encore activer leur compte), deux par A4. */
export function invitationLettersUrl(classGroup: string) {
  return `/api/families/letters/?${new URLSearchParams({ class_group: classGroup })}`;
}

export function familyLetterUrl(familyId: string) {
  return `/api/families/${familyId}/letter/`;
}

/** Liens qui ouvrent l'application avec le message déjà écrit, vers le tuteur principal. */
export function shareLinks(phone: string, text: string) {
  const body = encodeURIComponent(text);
  return {
    whatsapp: `https://wa.me/${phone.replace(/\D/g, "")}?text=${body}`,
    sms: `sms:${phone}?body=${body}`,
  };
}
