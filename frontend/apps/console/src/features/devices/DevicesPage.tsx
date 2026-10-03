// Appareils de toutes les écoles (5.4.2, maquette `console/appareils`) : recherche, en service ou
// déconnectés, « Déconnecter » après confirmation (journal de l'école et de la plateforme).
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDateTime, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  Input,
  PageHeader,
  Segmented,
  Skeleton,
  Table,
  Tag,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { Pager } from "../shell/Pager";

type Device = Schemas["ConsoleDevice"];
const FILTERS = ["active", "revoked", "all"] as const;
type Filter = (typeof FILTERS)[number];

export function DevicesPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("active");
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<Device | null>(null);
  const query = useDeferredValue(search.trim());
  const devices = useQuery({
    queryKey: [...keys.devices, { query, filter, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/devices/", {
          params: {
            query: {
              search: query || undefined,
              state: filter === "all" ? undefined : filter,
              page,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const revoke = useMutation({
    mutationFn: (device: Device) =>
      call(api.POST("/api/console/devices/{id}/revoke/", { params: { path: { id: device.id } } })),
    onSuccess: () => {
      setConfirm(null);
      void queryClient.invalidateQueries({ queryKey: keys.devices });
    },
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const when = (value: string | null) =>
    value ? formatDateTime(value, i18n.language, timeZone) : "—";

  return (
    <>
      <PageHeader title={t("console.devices.title")} subtitle={t("console.devices.subtitle")} />
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          aria-label={t("console.devices.search")}
          placeholder={t("console.devices.search")}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <Segmented
          label={t("console.devices.filter")}
          value={filter}
          onValueChange={(value) => {
            setFilter(value);
            setPage(1);
          }}
          options={FILTERS.map((value) => ({
            value,
            label: t(`console.devices.filters.${value}`),
          }))}
        />
      </div>
      {revoke.isError && <Banner tone="due">{errorMessage(revoke.error, t)}</Banner>}
      {devices.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : devices.isError ? (
        <>
          <Banner tone="due">{errorMessage(devices.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void devices.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : (
        <Card>
          {devices.data.results.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("console.devices.none")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t("console.devices.device")}</th>
                  <th>{t("console.devices.school")}</th>
                  <th>{t("console.devices.account")}</th>
                  <th>{t("console.devices.lastSeen")}</th>
                  <th>{t("console.devices.createdAt")}</th>
                  <th className="relative">
                    <span className="sr-only">{t("console.schools.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {devices.data.results.map((device) => (
                  <tr key={device.id}>
                    <td>
                      <b>{device.label}</b> <Tag>{device.prefix}</Tag>
                    </td>
                    <td>
                      <Link to={`/schools/${device.school.id}`} className="hover:underline">
                        {device.school.name}
                      </Link>
                    </td>
                    <td>
                      <Link to={`/accounts/${device.user.id}`} className="hover:underline">
                        {device.user.name}
                      </Link>
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {when(device.last_seen_at)}
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {formatDay(device.created_at.slice(0, 10), i18n.language)}
                    </td>
                    <td className="whitespace-nowrap">
                      {device.revoked_at ? (
                        <span className="text-sm text-ink-3">
                          {t("console.devices.revokedOn", { date: when(device.revoked_at) })}
                        </span>
                      ) : (
                        <Button variant="destructive" size="sm" onClick={() => setConfirm(device)}>
                          {t("console.devices.disconnect")}
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
            previous={devices.data.previous}
            next={devices.data.next}
          />
        </Card>
      )}
      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm
            ? t("console.devices.confirm.title", {
                label: confirm.label,
                prefix: confirm.prefix,
                name: confirm.user.name,
                school: confirm.school.name,
              })
            : ""
        }
        confirmLabel={t("console.devices.disconnect")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => confirm && revoke.mutate(confirm)}
        pending={revoke.isPending}
        destructive
      >
        {confirm && t("console.devices.confirm.text", { prefix: confirm.prefix })}
      </ConfirmDialog>
    </>
  );
}
