// Demandes d'aide à la plateforme (SUP.1) : mes demandes, leur fil, écrire, répondre, fermer.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type SupportRequest = Schemas["SupportRequest"];
export type SupportRequestDetail = Schemas["SupportRequestDetail"];
export type SupportStatus = SupportRequest["status"];
export const PAGE_SIZE = 25;

/** Le navigateur et le système en quelques mots (« Chrome sur Android »), joints à la demande. */
export function deviceLabel(): string {
  const agent = navigator.userAgent;
  const browser = /Edg\//.test(agent)
    ? "Edge"
    : /Firefox\//.test(agent)
      ? "Firefox"
      : /Chrome\//.test(agent)
        ? "Chrome"
        : /Safari\//.test(agent)
          ? "Safari"
          : "";
  const system = /Android/.test(agent)
    ? "Android"
    : /iPhone|iPad/.test(agent)
      ? "iOS"
      : /Windows/.test(agent)
        ? "Windows"
        : /Mac OS/.test(agent)
          ? "macOS"
          : /Linux/.test(agent)
            ? "Linux"
            : "";
  return [browser, system].filter(Boolean).join(" · ");
}

export function useRequests(page: number) {
  return useQuery({
    queryKey: [...keys.supportRequests, "list", page],
    queryFn: () => call(api.GET("/api/help/requests/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
}

export function useRequest(id: string | undefined) {
  return useQuery({
    queryKey: [...keys.supportRequests, "one", id],
    enabled: Boolean(id),
    queryFn: () => call(api.GET("/api/help/requests/{id}/", { params: { path: { id: id! } } })),
  });
}

function useRefreshRequests() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: keys.supportRequests });
}

export function useOpenRequest() {
  const refresh = useRefreshRequests();
  return useMutation({
    mutationFn: (body: Schemas["SupportRequestCreateRequest"]) =>
      call(api.POST("/api/help/requests/", { body })),
    onSuccess: refresh,
  });
}

export function useReplyRequest(id: string) {
  const refresh = useRefreshRequests();
  return useMutation({
    mutationFn: (body: string) =>
      call(
        api.POST("/api/help/requests/{id}/reply/", { params: { path: { id } }, body: { body } }),
      ),
    onSuccess: refresh,
  });
}

export function useCloseRequest(id: string) {
  const refresh = useRefreshRequests();
  return useMutation({
    mutationFn: () =>
      call(api.POST("/api/help/requests/{id}/close/", { params: { path: { id } } })),
    onSuccess: refresh,
  });
}
