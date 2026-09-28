import { formatVisit, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  SyncIndicator,
} from "@mwangaza/ui";
import { useEffect, useState } from "react";

import { useOnline } from "../../lib/online";
import { can } from "../../lib/permissions";
import type { Me } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import {
  requestPersistence,
  startSync,
  syncNow,
  useSyncStatus,
  type SyncStatus,
} from "../../lib/sync/session";

/** Synchronisation de l'appareil mémorisé tant que la coquille est ouverte : droits des
 *  endpoints de `/api/sync/` (03 § 5.3), jamais en session support. */
export function useSyncSession(me: Me) {
  const enabled = !me.support && can(me, ["students.view", "finance.collect_payment"]);
  useEffect(() => (enabled ? startSync(me.id) : undefined), [enabled, me.id]);
}

function useIndicator(online: boolean, sync: SyncStatus) {
  const { t } = useTranslation();
  const ok = (label: string) => ({ tone: "ok" as const, label });
  if (!sync.device) {
    return online ? ok(t("common.online")) : { tone: "warn" as const, label: t("common.offline") };
  }
  if (sync.rejected > 0) {
    return { tone: "due" as const, label: t("shell.sync.rejected", { count: sync.rejected }) };
  }
  if (!online) {
    const label = sync.pending
      ? t("shell.sync.offlinePending", { count: sync.pending })
      : t("common.offline");
    return { tone: "warn" as const, label };
  }
  if (sync.running) return ok(t("shell.sync.running"));
  if (sync.pending) return ok(t("shell.sync.onlinePending", { count: sync.pending }));
  return ok(t(sync.failed || !sync.lastSyncAt ? "shell.sync.notSynced" : "shell.sync.upToDate"));
}

/** Indicateur du haut (03 § 5.4) : en ligne ou non, opérations en attente ou refusées ; avec un
 *  appareil mémorisé, il ouvre le détail et « Synchroniser maintenant ». */
export function SyncMenu({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const online = useOnline();
  const sync = useSyncStatus();
  const { tone, label } = useIndicator(online, sync);
  const indicator = <SyncIndicator tone={tone} label={label} className={className} />;
  if (!sync.device) return indicator;

  const when =
    sync.lastSyncAt &&
    formatVisit(sync.lastSyncAt, i18n.language, school.timezone, (time) =>
      t("common.today", { time }),
    );
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="cursor-pointer rounded-full">
        {indicator}
        <span className="sr-only">{t("shell.sync.details")}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72 max-w-[calc(100vw-32px)]">
        <div className="flex flex-col gap-1 px-2.5 py-1.5 text-sm text-ink-2">
          <p>{when ? t("shell.sync.lastSync", { when }) : t("shell.sync.never")}</p>
          <p>{t("shell.sync.pending", { count: sync.pending })}</p>
          {sync.rejected > 0 && (
            <p className="text-due">{t("shell.sync.rejectedHint", { count: sync.rejected })}</p>
          )}
          {sync.persisted !== null && (
            <p>
              {t("shell.sync.storage", {
                state: t(sync.persisted ? "shell.sync.granted" : "shell.sync.refused"),
              })}
            </p>
          )}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={!online || sync.running} onSelect={() => void syncNow()}>
          {t("shell.sync.now")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

const ONLINE_ONLY = "mwangaza.onlineOnly";

function onlineOnlyChosen() {
  try {
    return sessionStorage.getItem(ONLINE_ONLY) === "1";
  } catch {
    return false;
  }
}

/** Stockage persistant refusé (M8) : sans lui, le navigateur peut effacer la base de l'appareil
 *  et la caisse ne peut pas travailler sans internet (la caisse hors ligne le bloque en 3.5).
 *  « Continuer en ligne seulement » le cache tant que l'onglet reste ouvert. */
export function StorageBanner() {
  const { t } = useTranslation();
  const { device, persisted } = useSyncStatus();
  const [hidden, setHidden] = useState(onlineOnlyChosen);
  if (!device || persisted !== false || hidden) return null;

  function onlineOnly() {
    try {
      sessionStorage.setItem(ONLINE_ONLY, "1");
    } catch {
      // Stockage refusé : caché pour cet écran seulement.
    }
    setHidden(true);
  }

  return (
    <Banner tone="warn" role="region" aria-label={t("shell.storage.title")}>
      <b>{t("shell.storage.title")}</b>
      <p className="mt-0.5">{t("shell.storage.text")}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => void requestPersistence()}>
          {t("common.retry")}
        </Button>
        <Button size="sm" variant="ghost" onClick={onlineOnly}>
          {t("shell.storage.onlineOnly")}
        </Button>
      </div>
    </Banner>
  );
}
