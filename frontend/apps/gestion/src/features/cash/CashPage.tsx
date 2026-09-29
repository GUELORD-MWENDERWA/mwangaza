// Caisse (F1-F2, F5, M13) : sans caisse ouverte, l'écran d'ouverture (maquette
// `caisse-ouverture`) ; sinon l'accueil de la caisse, qui devient l'encaissement quand un élève
// est choisi. Appareil mémorisé : la caisse lit et écrit la base de l'appareil, avec ou sans
// réseau (3.5.1) ; sinon, en ligne. Ouverture hors ligne : 3.5.2 ; clôture : 3.8.
import { api, call } from "@mwangaza/api";
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
import { type CurrentSession, useCashRegisters, useCurrentSession } from "./data";
import { saveSession, useLocalCash } from "./localData";
import { sampleReceipt, useReceiptPrinter } from "./Receipt";

export function CashPage() {
  const { db, prefix, persisted } = useSyncStatus();
  const [onlineOnly, setOnlineOnly] = useState(onlineOnlyChosen);
  if (!db || !prefix || onlineOnly) return <ServerCash />;
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
  return <DeviceCash db={db} prefix={prefix} />;
}

function ServerCash() {
  const { t } = useTranslation();
  const current = useCurrentSession();
  if (current.error)
    return <LoadError error={current.error} onRetry={() => void current.refetch()} />;
  if (!current.data) return <Skeleton label={t("common.loading")} />;
  const { session } = current.data;
  return session ? (
    <CashDesk current={current.data} session={session} />
  ) : (
    <OpenSession current={current.data} />
  );
}

/** Session lue en ligne quand le serveur répond, sinon la dernière gardée sur l'appareil. */
function DeviceCash({ db, prefix }: { db: LocalDb; prefix: string }) {
  const { t } = useTranslation();
  const local = useLocalCash(db);
  const current = useCurrentSession();
  useEffect(() => {
    if (current.data) void saveSession(db, current.data);
  }, [db, current.data]);
  const offline = hasCode(current.error, "network");
  if (current.error && !offline)
    return <LoadError error={current.error} onRetry={() => void current.refetch()} />;
  if (local.error) return <LoadError error={local.error} onRetry={() => location.reload()} />;
  if (!local.data) return <Skeleton label={t("common.loading")} />;
  const known = current.data ?? local.data.saved;
  if (!known)
    return offline ? (
      <NeedsNetwork onRetry={() => void current.refetch()} />
    ) : (
      <Skeleton label={t("common.loading")} />
    );
  if (!known.session)
    return current.data ? (
      <OpenSession current={known} />
    ) : (
      <NeedsNetwork onRetry={() => void current.refetch()} />
    );
  return (
    <CashDesk current={known} session={known.session} device={{ db, prefix, local: local.data }} />
  );
}

/** Caisse fermée et pas de réseau : l'ouverture hors ligne vient en 3.5.2. */
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

function OpenSession({ current }: { current: CurrentSession }) {
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

  if (registers.error)
    return <LoadError error={registers.error} onRetry={() => void registers.refetch()} />;
  if (!registers.data) return <Skeleton label={t("common.loading")} />;
  const active = registers.data.filter((register) => register.is_active);
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
            onClick={() => selected && open.mutate(selected.id)}
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
