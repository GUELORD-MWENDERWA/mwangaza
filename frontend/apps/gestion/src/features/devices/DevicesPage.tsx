// Appareils et synchronisation (F5, B5, 3.7.2) : les appareils mémorisés de l'école, qu'un
// responsable (`roles.manage`) révoque ; cet appareil, ses données et sa file d'attente, pour
// tout compte qui se synchronise. Révoqué, un appareil perd sa session tout de suite et efface
// ses données à sa prochaine connexion (`attachDevice`) ou synchronisation.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatTime, formatVisit, useTranslation } from "@mwangaza/i18n";
import { formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Icon,
  List,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { errorMessage } from "../../lib/errors";
import { useOnline } from "../../lib/online";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import type { LocalDb, QueuedOperation } from "../../lib/sync/db";
import { syncNow, useSyncStatus } from "../../lib/sync/session";
import { useLive } from "../cash/localData";
import { receiptNumber } from "../cash/offline";
import { Pagination } from "../shell/Pagination";

type SchoolDevice = Schemas["SchoolDevice"];

/** En ligne : un contact il y a moins de 3 min (la synchronisation tourne toutes les 60 s). */
const ONLINE_WITHIN = 3 * 60_000;

export function DevicesPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const school = useCurrentSchool();
  const manage = can(me, ["roles.manage"]);
  return (
    <>
      <PageHeader
        title={t("devices.title")}
        subtitle={t("devices.subtitle", { school: school.name })}
      />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        {manage && <SchoolDevices />}
        <div className="flex flex-col gap-4">
          <ThisDevice />
        </div>
      </div>
    </>
  );
}

function SchoolDevices() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<SchoolDevice | null>(null);
  const devices = useQuery({
    queryKey: [...keys.schoolDevices, page],
    queryFn: () => call(api.GET("/api/devices/", { params: { query: page > 1 ? { page } : {} } })),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
  const revoke = useMutation({
    mutationFn: (device: SchoolDevice) =>
      call(api.POST("/api/devices/{id}/revoke/", { params: { path: { id: device.id } } })),
    onSuccess: () => {
      setTarget(null);
      void queryClient.invalidateQueries({ queryKey: keys.schoolDevices });
    },
  });
  const list = devices.data?.results ?? [];
  // Heure de la lecture (relue toutes les 60 s), pas celle du rendu.
  const now = devices.dataUpdatedAt;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("devices.school.title")}</CardTitle>
      </CardHeader>
      {devices.isPending ? (
        <CardContent>
          <Skeleton label={t("common.loading")} />
        </CardContent>
      ) : devices.isError ? (
        <CardContent>
          <Banner tone="due">{errorMessage(devices.error, t)}</Banner>
        </CardContent>
      ) : list.length === 0 ? (
        <CardContent className="text-ink-3">{t("devices.school.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("devices.school.columns.prefix")}</th>
              <th>{t("devices.school.columns.device")}</th>
              <th>{t("devices.school.columns.state")}</th>
              <th>{t("devices.school.columns.lastSeen")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.map((device) => {
              const seen = device.last_seen_at ? Date.parse(device.last_seen_at) : 0;
              const online = now - seen < ONLINE_WITHIN;
              return (
                <tr key={device.id}>
                  <td>
                    <Tag>{device.prefix}</Tag>
                  </td>
                  <td>
                    <b className="block">{device.label}</b>
                    <span className="text-sm text-ink-3">{device.user_name}</span>
                  </td>
                  <td>
                    <StatusPill tone={online ? "ok" : "gray"}>
                      {t(online ? "devices.school.online" : "devices.school.offline")}
                    </StatusPill>
                  </td>
                  <td className="text-sm whitespace-nowrap">
                    {device.last_seen_at &&
                      formatVisit(device.last_seen_at, i18n.language, school.timezone, (time) =>
                        t("common.today", { time }),
                      )}
                  </td>
                  <td className="text-right">
                    {device.is_current ? (
                      <StatusPill tone="info">{t("devices.school.current")}</StatusPill>
                    ) : (
                      <Button
                        variant="destructive-outline"
                        size="sm"
                        onClick={() => setTarget(device)}
                      >
                        {t("devices.school.revoke")}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      )}
      <Pagination
        page={page}
        hasPrevious={Boolean(devices.data?.previous)}
        hasNext={Boolean(devices.data?.next)}
        onPage={setPage}
        summary={t("devices.school.total", { count: devices.data?.count ?? 0 })}
      />
      <ConfirmDialog
        open={target !== null}
        onOpenChange={(open) => !open && setTarget(null)}
        title={t("devices.school.confirmTitle", { prefix: target?.prefix, label: target?.label })}
        confirmLabel={t("devices.school.revoke")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => target && revoke.mutate(target)}
        pending={revoke.isPending}
      >
        <p className="text-sm text-ink-2">{t("devices.school.confirmText")}</p>
        <Banner tone="warn">{t("devices.school.confirmWarning")}</Banner>
        {revoke.isError && <Banner tone="due">{errorMessage(revoke.error, t)}</Banner>}
      </ConfirmDialog>
    </Card>
  );
}

function ThisDevice() {
  const { t } = useTranslation();
  const sync = useSyncStatus();
  if (!sync.db || !sync.prefix)
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("devices.local.titleNone")}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-ink-2">{t("devices.local.none")}</CardContent>
      </Card>
    );
  return <LocalDevice db={sync.db} prefix={sync.prefix} />;
}

type Summary = {
  students: number;
  charges: number;
  payments: number;
  receiptSeq: number;
  yearStartsOn: string | null;
  /** En attente et refusées, les plus récentes d'abord. */
  queue: QueuedOperation[];
};

async function readSummary(db: LocalDb): Promise<Summary> {
  let students = 0;
  let charges = 0;
  let payments = 0;
  await db.enrollments.each((enrollment) => {
    students += 1;
    charges += enrollment.charges?.length ?? 0;
    payments += enrollment.payments?.length ?? 0;
  });
  const [meta, config, queue] = await Promise.all([
    db.meta.get("sync"),
    db.config.get("config"),
    db.outbox.where("status").anyOf("pending", "rejected").reverse().sortBy("seq"),
  ]);
  return {
    students,
    charges,
    payments,
    receiptSeq: meta?.receiptSeq ?? 0,
    yearStartsOn: config?.value.academic_year?.starts_on ?? null,
    queue,
  };
}

function LocalDevice({ db, prefix }: { db: LocalDb; prefix: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const online = useOnline();
  const sync = useSyncStatus();
  const { data } = useLive(db, readSummary);
  const count = new Intl.NumberFormat(i18n.language);
  const lastReceipt =
    data?.yearStartsOn && data.receiptSeq > 0
      ? receiptNumber(school.code, prefix, data.yearStartsOn, data.receiptSeq)
      : t("devices.local.noReceipt");
  const rows: [string, ReactNode][] = [
    [
      t("devices.local.lastSync"),
      sync.lastSyncAt
        ? formatVisit(sync.lastSyncAt, i18n.language, school.timezone, (time) =>
            t("common.today", { time }),
          )
        : t("devices.local.never"),
    ],
    [t("devices.local.pending"), sync.pending],
    [
      t("devices.local.rejected"),
      sync.rejected > 0 && <span className="text-due">{sync.rejected}</span>,
    ],
    [
      t("devices.local.data"),
      data &&
        t("devices.local.dataValue", {
          students: count.format(data.students),
          charges: count.format(data.charges),
          payments: count.format(data.payments),
        }),
    ],
    [
      t("devices.local.storage"),
      sync.persisted !== null && (
        <StatusPill tone={sync.persisted ? "ok" : "warn"}>
          {t(sync.persisted ? "shell.sync.granted" : "shell.sync.refused")}
        </StatusPill>
      ),
    ],
    [t("devices.local.lastReceipt"), <span className="tabular-nums">{lastReceipt}</span>],
    [t("devices.local.version"), __APP_VERSION__],
  ];
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t("devices.local.title", { prefix })}</CardTitle>
          <StatusPill tone={online ? "ok" : "warn"}>
            {t(online ? "common.online" : "common.offline")}
          </StatusPill>
        </CardHeader>
        <CardContent className="py-1">
          <List>
            {rows.map(([label, value]) =>
              value === false ? null : (
                <div key={label}>
                  <span className="text-sm text-ink-2">{label}</span>
                  <b className="text-right text-sm">{value}</b>
                </div>
              ),
            )}
          </List>
        </CardContent>
        <CardFooter>
          <span className="text-sm text-ink-3">{t("devices.local.retry")}</span>
          <Button size="sm" disabled={!online || sync.running} onClick={() => void syncNow()}>
            <Icon name="sync" />
            {t("shell.sync.now")}
          </Button>
        </CardFooter>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("devices.queue.title")}</CardTitle>
        </CardHeader>
        <CardContent className="py-1">
          {!data ? (
            <div className="py-3">
              <Skeleton label={t("common.loading")} />
            </div>
          ) : data.queue.length === 0 ? (
            <p className="py-3 text-sm text-ink-3">{t("devices.queue.empty")}</p>
          ) : (
            <List>
              {data.queue.map((operation) => (
                <QueueRow key={operation.op_id} operation={operation} />
              ))}
            </List>
          )}
        </CardContent>
      </Card>
    </>
  );
}

type QueueType = "payment" | "reprint" | "cashOpen" | "creditUse" | "cancellation" | "other";

const TYPES: Record<string, QueueType> = {
  "payment.create": "payment",
  "payment.reprint": "reprint",
  "cash_session.open": "cashOpen",
  "credit.use": "creditUse",
  "cancellation.request": "cancellation",
};

function QueueRow({ operation }: { operation: QueuedOperation }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const receipt = operation.type === "payment.create" ? operation.receipt : undefined;
  const rejected = operation.status === "rejected";
  return (
    <div>
      <div className="min-w-0">
        <p>
          <b className="tabular-nums">
            {formatTime(operation.created_at, i18n.language, school.timezone)}
          </b>
          {" · "}
          {t(`devices.queue.types.${TYPES[operation.type] ?? "other"}`)}
        </p>
        {receipt && (
          <span className="text-sm text-ink-3 tabular-nums">
            {receipt.receipt_number} ·{" "}
            {formatAmount(receipt.received_amount_minor, receipt.received_currency)}
          </span>
        )}
      </div>
      <StatusPill tone={rejected ? "due" : "warn"}>
        {t(rejected ? "devices.queue.rejected" : "devices.queue.pending")}
      </StatusPill>
    </div>
  );
}
