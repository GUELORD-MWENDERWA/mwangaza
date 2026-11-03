// Demandes de modules (ABO.4, maquette `console/demandes-modules`) : ce que les écoles ont demandé
// depuis « Mon abonnement ». Une demande n'active ni ne facture rien : la plateforme fait l'avenant
// (onglet Contrats), puis la marque « traitée ».
import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, Skeleton, StatusPill, Table } from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Pager } from "../shell/Pager";
import { useDay } from "./shared";

const KEY = ["console", "billing", "module-requests"];

export function ModuleRequestsTab({ manage }: { manage: boolean }) {
  const { t } = useTranslation();
  const day = useDay();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const requests = useQuery({
    queryKey: [...KEY, page],
    queryFn: () =>
      call(api.GET("/api/console/billing/module-requests/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
  const handle = useMutation({
    mutationFn: (id: string) =>
      call(
        api.POST("/api/console/billing/module-requests/{id}/handled/", {
          params: { path: { id } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  });
  return (
    <Card>
      {requests.isPending && <Skeleton label={t("console.billing.loading")} />}
      {handle.error && (
        <Banner tone="due" className="m-4">
          {errorMessage(handle.error, t)}
        </Banner>
      )}
      {requests.data && !requests.data.results.length && (
        <p className="p-4 text-ink-3">{t("console.billing.requests.empty")}</p>
      )}
      {!!requests.data?.results.length && (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("console.billing.requests.date")}</th>
              <th>{t("console.billing.school")}</th>
              <th>{t("console.billing.requests.module")}</th>
              <th>{t("console.billing.requests.note")}</th>
              <th>{t("console.billing.state")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {requests.data.results.map((r) => (
              <tr key={r.id}>
                <td data-label={t("console.billing.requests.date")}>{day(r.created_at)}</td>
                <td data-label={t("console.billing.school")}>
                  <b>{r.school}</b>
                </td>
                <td data-label={t("console.billing.requests.module")}>
                  {t(`console.schools.modules.${r.module}`)}
                </td>
                <td data-label={t("console.billing.requests.note")}>{r.note}</td>
                <td data-label={t("console.billing.state")}>
                  <StatusPill tone={r.status === "open" ? "warn" : "ok"}>
                    {t(`console.billing.requests.status.${r.status}`)}
                  </StatusPill>
                </td>
                <td>
                  {manage && r.status === "open" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={handle.isPending}
                      onClick={() => handle.mutate(r.id)}
                    >
                      {t("console.billing.requests.markHandled")}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Pager
        page={page}
        onPage={setPage}
        previous={requests.data?.previous}
        next={requests.data?.next}
      />
    </Card>
  );
}
