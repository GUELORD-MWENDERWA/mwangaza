// Dérogations de bulletin (8.4.6) : accordées par le préfet, jamais modifiées ; « lever » est le
// seul changement.
import { api, call, type Schemas } from "@mwangaza/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type Waiver = Schemas["FeeWaiver"];
export type NewWaiver = Schemas["FeeWaiverInputRequest"];
const KEY = ["fee-waivers"] as const;

export function useWaivers(onlyActive: boolean) {
  return useQuery({
    queryKey: [...KEY, onlyActive],
    queryFn: () =>
      call(api.GET("/api/fee-waivers/", { params: { query: onlyActive ? { active: true } : {} } })),
  });
}

export function useGrant() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewWaiver) => call(api.POST("/api/fee-waivers/", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useLift() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      call(api.POST("/api/fee-waivers/{id}/lift/", { params: { path: { id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
