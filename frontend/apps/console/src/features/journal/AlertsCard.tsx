// Alertes sur l'écran de cet appareil (S.3.2) : chaque usage d'un compte super-admin et chaque
// session support ouverte, même console fermée. Chaque appareil s'abonne à part ; le journal
// tient lieu de centre de notifications.
import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, Icon, StatusPill } from "@mwangaza/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { disablePush, enablePush, pushState, type PushState } from "../../lib/alerts";
import { keys } from "../../lib/queries";

const STATE_PILLS = {
  on: "ok",
  off: "gray",
  denied: "due",
  unsupported: "gray",
} as const satisfies Record<PushState, string>;

type WorkerMessage = { type?: string; path?: string };

/** Alerte reçue console ouverte : le journal se recharge ; clic sur l'alerte : son écran. */
export function useAlertMessages() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const onMessage = (event: MessageEvent<WorkerMessage>) => {
      if (event.data?.type === "notification") {
        void queryClient.invalidateQueries({ queryKey: keys.journal });
        void queryClient.invalidateQueries({ queryKey: keys.supportSessions });
      } else if (event.data?.type === "open") {
        void navigate(event.data.path || "/journal");
      }
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, [queryClient, navigate]);
}

export function AlertsCard() {
  const { t } = useTranslation();
  const settings = useQuery({
    queryKey: keys.alerts,
    queryFn: () => call(api.GET("/api/console/alerts/")),
    staleTime: Infinity,
  });
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    void pushState()
      .then(setState)
      .catch(() => setState("unsupported"));
  }, []);

  const publicKey = settings.data?.vapid_public_key ?? "";
  const run = (pending: Promise<PushState>) => {
    setBusy(true);
    setError(null);
    pending
      .then(setState)
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const help =
    state === "unsupported"
      ? t("console.journal.alerts.unsupported")
      : state === "denied"
        ? t("console.journal.alerts.denied")
        : settings.data && !publicKey
          ? t("console.journal.alerts.notConfigured")
          : t("console.journal.alerts.intro");
  const canChange = Boolean(publicKey) && !busy;
  return (
    <Card className="flex flex-wrap items-center gap-x-4 gap-y-3 p-4">
      <div className="min-w-0 flex-1 basis-72">
        <div className="flex flex-wrap items-center gap-2">
          <b>{t("console.journal.alerts.title")}</b>
          {state && (
            <StatusPill tone={STATE_PILLS[state]}>
              {t(`console.journal.alerts.states.${state}`)}
            </StatusPill>
          )}
        </div>
        <p className="mt-1 text-sm text-ink-2">{help}</p>
      </div>
      {state === "on" && (
        <Button
          variant="outline"
          size="sm"
          disabled={!canChange}
          onClick={() => run(disablePush().then(() => "off" as const))}
        >
          {t("console.journal.alerts.disable")}
        </Button>
      )}
      {state === "off" && (
        <Button size="sm" disabled={!canChange} onClick={() => run(enablePush(publicKey))}>
          <Icon name="bell" size={16} />
          {t("console.journal.alerts.enable")}
        </Button>
      )}
      {error !== null && (
        <Banner tone="due" className="basis-full">
          {errorMessage(error, t)}
        </Banner>
      )}
    </Card>
  );
}
