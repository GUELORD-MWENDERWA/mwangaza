import { useTranslation } from "@mwangaza/i18n";
import { Button, Toast } from "@mwangaza/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { syncNow, useSyncStatus } from "../../lib/sync/session";

/** Nouvelle version cherchée toutes les heures quand l'application reste ouverte. */
const CHECK_EVERY = 60 * 60 * 1000;

/** Service worker de l'application (`make build` ; aucun en développement) et nouvelle version
 *  en attente. Écrit ici plutôt qu'avec `virtual:pwa-register`, qui demanderait le paquet
 *  `workbox-window`. */
function useWaitingVersion() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  const accepted = useRef(false);

  useEffect(() => {
    if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const base = import.meta.env.BASE_URL;
    const watch = (worker: ServiceWorker | null) => {
      if (!worker) return;
      const check = () => {
        // Première installation (aucune version en service) : rien à proposer.
        if (worker.state === "installed" && navigator.serviceWorker.controller) setWaiting(worker);
      };
      check();
      worker.addEventListener("statechange", check);
    };
    void navigator.serviceWorker.register(`${base}sw.js`, { scope: base }).then((registration) => {
      watch(registration.waiting);
      registration.addEventListener("updatefound", () => watch(registration.installing));
      timer = setInterval(() => void registration.update(), CHECK_EVERY);
    });
    // La nouvelle version a pris la main : recharger, seulement si la personne l'a demandé.
    const reload = () => {
      if (accepted.current) window.location.reload();
    };
    navigator.serviceWorker.addEventListener("controllerchange", reload);
    return () => {
      clearInterval(timer);
      navigator.serviceWorker.removeEventListener("controllerchange", reload);
    };
  }, []);

  const install = useCallback(() => {
    accepted.current = true;
    waiting?.postMessage({ type: "SKIP_WAITING" });
  }, [waiting]);

  return { waiting: waiting !== null, install };
}

/** Nouvelle version de l'application (M8) : proposée, jamais imposée ; installée en rechargeant,
 *  seulement quand la file d'opérations est vide (sinon après leur synchronisation). */
export function UpdatePrompt() {
  const { t } = useTranslation();
  const { waiting, install } = useWaitingVersion();
  const { pending } = useSyncStatus();
  const [asked, setAsked] = useState(false);

  useEffect(() => {
    if (asked && pending === 0) install();
  }, [asked, pending, install]);

  if (!waiting) return null;
  return (
    <Toast
      icon="download"
      action={
        <Button
          size="sm"
          className="border-lamp bg-lamp text-night hover:border-lamp hover:bg-lamp hover:brightness-95"
          disabled={asked}
          onClick={() => {
            setAsked(true);
            void syncNow();
          }}
        >
          {t("shell.update.action")}
        </Button>
      }
    >
      <b>{t("shell.update.ready")}</b>
      <br />
      <span className="text-night-soft">
        {pending > 0 ? t("shell.update.afterSync", { count: pending }) : t("shell.update.text")}
      </span>
    </Toast>
  );
}
