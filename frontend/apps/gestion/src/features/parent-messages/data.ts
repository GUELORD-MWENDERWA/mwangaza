// Messages des parents (8.8) : un fil par élève ; ouvrir un fil le marque lu pour l'école.
import { api, call, type Schemas } from "@mwangaza/api";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type Thread = Schemas["Thread"];
export type ThreadDetail = Schemas["ThreadDetail"];
const KEY = ["parent-threads"] as const;

export function useThreads(page: number) {
  return useQuery({
    queryKey: [...KEY, page],
    queryFn: () => call(api.GET("/api/parent-threads/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
}

export function useThread(id: string | null) {
  return useQuery({
    queryKey: [...KEY, "detail", id],
    queryFn: () =>
      call(api.GET("/api/parent-threads/{id}/", { params: { path: { id: id ?? "" } } })),
    enabled: id !== null,
  });
}

export function useReply(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: string) =>
      call(
        api.POST("/api/parent-threads/{id}/reply/", { params: { path: { id } }, body: { body } }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
