// Caisse (F1-F2, F5, M13) : sans caisse ouverte, l'écran d'ouverture (maquette
// `caisse-ouverture`) ; sinon l'accueil de la caisse, qui devient l'encaissement quand un élève
// est choisi. Appareil mémorisé : la caisse lit et écrit la base de l'appareil, avec ou sans
// réseau, ouverture et clôture comprises (3.5, 3.8.2) ; sinon, en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatTime, useTranslation } from "@mwangaza/i18n";
import { formatRate } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  List,
  PageHeader,
  Skeleton,
  StateCard,
  StatusPill,
  Tag,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { errorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { fullName } from "../../lib/people";
import { hasCode, keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import type { LocalDb } from "../../lib/sync/db";
import { requestPersistence, useSyncStatus } from "../../lib/sync/session";
import { chooseOnlineOnly, onlineOnlyChosen } from "../shell/SyncMenu";
import { LoadError } from "../status/StatusPages";
import { CashDesk } from "./CashDesk";
import { ClosedView, type Slip } from "./Closing";
import {
  type CashRegister,
  type CurrentSession,
  useCashRegisters,
  useCurrentSession,
} from "./data";
import { closedHere, openOffline, saveSession, useLocalCash } from "./localData";
import { sampleReceipt, useReceiptPrinter } from "./Receipt";

export function CashPage() {
  const { db, prefix, persisted } = useSyncStatus();
  const [onlineOnly, setOnlineOnly] = useState(onlineOnlyChosen);
  // Caisse clôturée : la session n'est plus là, le bordereau s'imprime ici (3.8.2).
  const [slip, setSlip] = useState<Slip | null>(null);
  if (slip) return <ClosedView slip={slip} onDone={() => setSlip(null)} />;
  if (!db || !prefix || onlineOnly) return <ServerCash onClosed={setSlip} />;
  // M8 : sans stockage persistant, le navigateur peut effacer la base, et la caisse avec.
  if (persisted === false)
    return (
      <StorageRefused
        onOnlineOnly={() => {
          chooseOnlineOnly();
          setOnlineOnly(true);
        }}
      />
    );
  return <DeviceCash db={db} prefix={prefix} onClosed={setSlip} />;
}

function ServerCash({ onClosed }: { onClosed: (slip: Slip) => void }) {
  const { t } = useTranslation();
  const current = useCurrentSession();
  if (current.error)
    return <LoadError error={current.error} onRetry={() => void current.refetch()} />;
  if (!current.data) return <Skeleton label={t("common.loading")} />;
  const { session } = current.data;
  return session ? (
    <CashDesk current={current.data} session={session} onClosed={onClosed} />
  ) : (
    <OpenSession current={current.data} />
  );
}

/** Session gardée sur l'appareil (lue en ligne, ou ouverture acceptée par le serveur), sinon
 *  celle ouverte ici et pas encore acceptée. */
function DeviceCash({
  db,
  prefix,
  onClosed,
}: {
  db: LocalDb;
  prefix: string;
  onClosed: (slip: Slip) => void;
}) {
  const { t } = useTranslation();
  const local = useLocalCash(db);
  const current = useCurrentSession();
  const { data, dataUpdatedAt, refetch } = current;
  useEffect(() => {
    if (data) void saveSession(db, data, dataUpdatedAt);
  }, [db, data, dataUpdatedAt]);
  const opening = local.data?.queued.filter((op) => op.type === "cash_session.open").at(-1);
  const accepted = opening?.status === "sent";
  // Ouverture acceptée : la session du serveur est relue (une lecture partie avant est annulée).
  useEffect(() => {
    if (accepted) void refetch();
  }, [accepted, refetch]);
  const offline = hasCode(current.error, "network");
  if (current.error && !offline)
    return <LoadError error={current.error} onRetry={() => void refetch()} />;
  if (local.error) return <LoadError error={local.error} onRetry={() => location.reload()} />;
  if (!local.data) return <Skeleton label={t("common.loading")} />;
  const known = local.data.saved ?? data;
  if (!known)
    return offline ? (
      <NeedsNetwork onRetry={() => void refetch()} />
    ) : (
      <Skeleton label={t("common.loading")} />
    );
  const refused = opening?.status === "rejected";
  // Clôturée ici (3.8.2) : la caisse revient à l'ouverture, même sans réseau.
  const closed = closedHere(local.data.queued);
  const session = [known.session, refused ? undefined : opening?.session].find(
    (item) => item && !closed.has(item.id),
  );
  if (!session)
    return (
      <OpenSession
        current={known}
        device={{
          db,
          registers: local.data.config?.cash_registers ?? [],
          refused: refused ? opening.error : null,
        }}
      />
    );
  return (
    <CashDesk
      current={known}
      session={session}
      device={{ db, prefix, local: local.data }}
      onClosed={onClosed}
    />
  );
}

/** Caisse jamais ouverte sur cet appareil et pas de réseau : ni taux ni caisses connus. */
function NeedsNetwork({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="wifioff"
      tone="warn"
      title={t("cash.offline.closedTitle")}
      actions={
        <Button variant="outline" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      }
    >
      {t("cash.offline.closedText")}
    </StateCard>
  );
}

function StorageRefused({ onOnlineOnly }: { onOnlineOnly: () => void }) {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="database"
      tone="warn"
      title={t("shell.storage.title")}
      tag={<Tag>{t("cash.offline.storageTag")}</Tag>}
      actions={
        <>
          <Button onClick={() => void requestPersistence()}>{t("common.retry")}</Button>
          <Button variant="ghost" onClick={onOnlineOnly}>
            {t("shell.storage.onlineOnly")}
          </Button>
        </>
      }
    >
      {t("shell.storage.text")}
    </StateCard>
  );
}

/** Taux absent ou repris d'une année précédente : à signaler (M13). */
export function RateBanner({ current }: { current: CurrentSession }) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  if (school.enabled_currencies.length < 2) return null;
  if (current.rate === null) return <Banner tone="warn">{t("cash.open.rateMissing")}</Banner>;
  if (!current.rate_is_fallback) return null;
  return (
    <Banner tone="warn">{t("cash.open.rateFallback", { rate: formatRate(current.rate) })}</Banner>
  );
}

/** Appareil mémorisé : caisses de la configuration de l'appareil (occupées ou libres si le
 *  serveur répond), ouverture par la file ; `refused` : dernière ouverture refusée. */
type DeviceOpening = {
  db: LocalDb;
  registers: Schemas["CashRegister"][];
  refused: Schemas["Error"] | null;
};

function OpenSession({ current, device }: { current: CurrentSession; device?: DeviceOpening }) {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const school = useCurrentSchool();
  const registers = useCashRegisters();
  const queryClient = useQueryClient();
  const [chosen, setChosen] = useState<string | null>(null);
  // Donné par l'appareil : un deuxième envoi (double clic, réseau) rend la même session.
  const [sessionId] = useState(uuidv7);
  const printer = useReceiptPrinter();
  const open = useMutation({
    mutationFn: (register: string) =>
      call(api.POST("/api/cash-sessions/", { body: { id: sessionId, cash_register: register } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.cashSession }),
    // Une caisse prise entre-temps : la liste se met à jour.
    onError: () => void registers.refetch(),
  });

  const submit = (register: CashRegister) => {
    if (!device) return open.mutate(register.id);
    const { id, name, code, is_active } = register;
    const { last_name, middle_name, first_name } = me;
    void openOffline(device.db, {
      id: sessionId,
      cash_register: { id, name, code, is_active },
      cashier: { id: me.id, last_name, middle_name, first_name },
      opened_at: new Date().toISOString(),
      closed_at: null,
    });
  };

  const list =
    registers.data ?? device?.registers.map((register) => ({ ...register, open_session: null }));
  if (!list && registers.error)
    return <LoadError error={registers.error} onRetry={() => void registers.refetch()} />;
  if (!list) return <Skeleton label={t("common.loading")} />;
  const active = list.filter((register) => register.is_active);
  const free = active.filter((register) => !register.open_session);
  const selected = free.find((register) => register.id === chosen) ?? free[0];
  const header = (
    <PageHeader
      title={t("cash.open.title")}
      subtitle={t("cash.open.hello", { name: me.first_name || fullName(me) })}
    />
  );
  if (active.length === 0)
    return (
      <>
        {header}
        <StateCard icon="cash" tone="lake" title={t("cash.open.none")}>
          {t("cash.open.noneHelp")}
        </StateCard>
      </>
    );

  return (
    <>
      {header}
      <RateBanner current={current} />
      {open.error && <Banner tone="due">{errorMessage(open.error, t)}</Banner>}
      {device?.refused && (
        <Banner tone="due">{t("cash.open.refused", { reason: device.refused.detail })}</Banner>
      )}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[900px]:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>{t("cash.open.registers")}</CardTitle>
          </CardHeader>
          <CardContent>
            <fieldset className="flex flex-col gap-3">
              <legend className="sr-only">{t("cash.open.registers")}</legend>
              {active.map((register) => {
                const busy = register.open_session;
                const on = register.id === selected?.id;
                return (
                  <label
                    key={register.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-[12px] border px-4 py-3.5",
                      on ? "border-2 border-lake bg-lake-50" : "border-line",
                      busy && "cursor-not-allowed opacity-55",
                    )}
                  >
                    <input
                      type="radio"
                      name="cash-register"
                      className="size-5 shrink-0 accent-lake"
                      checked={on}
                      disabled={Boolean(busy)}
                      onChange={() => setChosen(register.id)}
                    />
                    <Tag>{register.code}</Tag>
                    <span className="min-w-0 flex-1">
                      <b className="block">{register.name}</b>
                      <span className="text-sm text-ink-3">
                        {busy
                          ? t("cash.open.busySince", {
                              time: formatTime(busy.opened_at, i18n.language, school.timezone),
                              name: fullName(busy.cashier),
                            })
                          : t("cash.open.freeHelp")}
                      </span>
                    </span>
                    <StatusPill tone={busy ? "warn" : "ok"}>
                      {t(busy ? "cash.open.busy" : "cash.open.free")}
                    </StatusPill>
                  </label>
                );
              })}
            </fieldset>
          </CardContent>
        </Card>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("cash.open.before")}</CardTitle>
            </CardHeader>
            <CardContent>
              <List>
                {school.enabled_currencies.length > 1 && (
                  <div>
                    <span>{t("cash.open.rate")}</span>
                    <b className="tabular-nums">
                      {current.rate
                        ? t("fees.rate.value", { rate: formatRate(current.rate) })
                        : "—"}
                    </b>
                  </div>
                )}
                <div>
                  <span>{t("cash.open.printer")}</span>
                  <span className="flex items-center gap-2">
                    {t(`settings.receipt.printers.${school.receipt.printer}`)}
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={t("cash.open.testLabel")}
                      onClick={() =>
                        printer.print({
                          payment: sampleReceipt(school, me, selected?.name ?? "", t),
                          test: true,
                        })
                      }
                    >
                      {t("cash.open.test")}
                    </Button>
                  </span>
                </div>
              </List>
            </CardContent>
          </Card>
          {printer.area}
          <Button
            size="xl"
            disabled={!selected || open.isPending}
            onClick={() => selected && submit(selected)}
          >
            <Icon name="cash" size={22} />
            {t("cash.open.submit", { code: selected?.code ?? "" })}
          </Button>
          <p className="text-sm text-ink-3">{t("cash.open.responsible")}</p>
        </div>
      </div>
    </>
  );
}
