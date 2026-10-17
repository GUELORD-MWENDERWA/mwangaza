// Démarrage sans réseau (B5, maquette `deverrouillage-pin`) : l'école et le compte ne répondent
// pas, un compte mémorisé dans ce navigateur a un code PIN → l'application rouvre avec ce qu'il
// gardait. Sinon, la page « Hors ligne ».
import { changeLanguage, formatVisit, useTranslation } from "@mwangaza/i18n";
import { Avatar, Banner, Button, cn, initials, Skeleton } from "@mwangaza/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ComponentProps, useEffect, useRef, useState } from "react";

import { allDevices, type LocalDevice } from "../../lib/device";
import { displayName } from "../../lib/people";
import { PIN_LENGTH, pinState, tryPin, type PinState } from "../../lib/pin";
import { keys, type Me, type School } from "../../lib/queries";
import { dexieStore, LocalDb } from "../../lib/sync/db";
import { Offline, StandaloneStatus } from "../status/StatusPages";

type Account = {
  device: LocalDevice & { me: Me; school: School };
  lastSyncAt: string | null;
  pending: number;
};

/** Les comptes de ce navigateur qui ont un PIN, le dernier ouvert d'abord, avec l'état de leur
 *  synchronisation. */
async function offlineAccounts(): Promise<Account[]> {
  const devices = (await allDevices())
    .filter((device): device is Account["device"] => !!(device.pin && device.me && device.school))
    .sort((a, b) => (b.seenAt ?? 0) - (a.seenAt ?? 0));
  return Promise.all(
    devices.map(async (device) => {
      const db = new LocalDb(device.id);
      try {
        const [meta, pending] = await Promise.all([
          dexieStore(db).meta(),
          db.outbox.where("status").equals("pending").count(),
        ]);
        return { device, lastSyncAt: meta.lastSyncAt, pending };
      } finally {
        db.close();
      }
    }),
  );
}

export function OfflineStart({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  const accounts = useQuery({
    queryKey: ["offline-accounts"],
    queryFn: offlineAccounts,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  if (accounts.isPending) {
    return (
      <StandaloneStatus>
        <Skeleton label={t("common.loading")} />
      </StandaloneStatus>
    );
  }
  if (!accounts.data?.length) {
    return (
      <StandaloneStatus>
        <Offline onRetry={onRetry} prepare />
      </StandaloneStatus>
    );
  }
  return <PinUnlock accounts={accounts.data} onRetry={onRetry} />;
}

function PinUnlock({ accounts, onRetry }: { accounts: Account[]; onRetry: () => void }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [account, setAccount] = useState(accounts[0]!);
  const [choosing, setChoosing] = useState(false);
  const [pin, setPin] = useState("");
  const [state, setState] = useState<PinState>(() => pinState(account.device));
  const [left, setLeft] = useState<number | null>(null);
  const [checking, setChecking] = useState(false);
  const { me, school } = account.device;

  useEffect(() => {
    if (me.language !== i18n.language) void changeLanguage(me.language);
  }, [me.language, i18n.language]);

  async function submit(value: string) {
    setChecking(true);
    const attempt = await tryPin(me.id, value).finally(() => setChecking(false));
    type("");
    if (attempt.outcome === "ok") {
      // L'application s'ouvre avec l'école et le compte gardés ; relus au retour du réseau.
      if (!queryClient.getQueryData(keys.school)) queryClient.setQueryData(keys.school, school);
      queryClient.setQueryData(keys.me, me);
    } else if (attempt.outcome === "wrong") {
      setLeft(attempt.left);
    } else {
      setState(attempt.outcome);
    }
  }

  // Chiffres tapés vite au clavier : chacun part de la valeur du précédent, pas du dernier rendu.
  const typed = useRef("");
  function type(value: string) {
    typed.current = value;
    setPin(value);
  }

  function press(digit: string) {
    if (checking || state !== "ok" || typed.current.length >= PIN_LENGTH) return;
    const next = typed.current + digit;
    type(next);
    if (next.length === PIN_LENGTH) void submit(next);
  }

  const erase = () => type(typed.current.slice(0, -1));

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (/^\d$/.test(event.key)) press(event.key);
      else if (event.key === "Backspace") erase();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function choose(next: Account) {
    setAccount(next);
    setState(pinState(next.device));
    type("");
    setLeft(null);
    setChoosing(false);
  }

  const when =
    account.lastSyncAt &&
    formatVisit(account.lastSyncAt, i18n.language, school.timezone, (time) =>
      t("common.today", { time }),
    );

  return (
    <main className="grid min-h-screen place-items-center bg-night p-4">
      <div className="flex w-full max-w-[400px] flex-col items-center gap-3.5 rounded-card border border-line bg-card p-5 text-center shadow-sm min-[480px]:p-7">
        <Banner tone="warn" icon="wifioff" className="w-full text-left">
          {t("unlock.offline")}
        </Banner>
        {choosing ? (
          <>
            <h1 className="text-lg font-bold">{t("unlock.chooseTitle")}</h1>
            <ul className="flex w-full flex-col gap-2">
              {accounts.map((item) => (
                <li key={item.device.user}>
                  <button
                    type="button"
                    onClick={() => choose(item)}
                    className="flex w-full cursor-pointer items-center gap-3 rounded-box border border-line bg-card px-3 py-2.5 text-left hover:bg-surface"
                  >
                    <Avatar text={personInitials(item.device.me)} />
                    <b>{displayName(item.device.me)}</b>
                  </button>
                </li>
              ))}
            </ul>
            <Button variant="ghost" size="sm" onClick={() => setChoosing(false)}>
              {t("common.back")}
            </Button>
          </>
        ) : (
          <>
            <Avatar text={personInitials(me)} className="size-[72px] text-xl" />
            <h1 className="text-lg font-bold">{t("unlock.hello", { name: me.first_name })}</h1>
            <p className="text-sm text-ink-3">
              {school.name}
              <br />
              {when ? t("shell.sync.lastSync", { when }) : t("shell.sync.never")}
              {account.pending > 0 && ` · ${t("unlock.pending", { count: account.pending })}`}
            </p>
            {state === "ok" ? (
              <>
                <p className="font-bold">{t("unlock.enterPin")}</p>
                <div className="flex justify-center gap-3" aria-live="polite">
                  <span className="sr-only">{t("unlock.typed", { count: pin.length })}</span>
                  {Array.from({ length: PIN_LENGTH }, (_, i) => (
                    <i
                      key={i}
                      aria-hidden="true"
                      className={cn(
                        "size-4 rounded-full border-2 border-ink-3",
                        i < pin.length && "border-ink bg-ink",
                      )}
                    />
                  ))}
                </div>
                {left !== null && (
                  <p role="alert" className="text-sm font-bold text-due">
                    {t("unlock.wrong", { count: left })}
                  </p>
                )}
                <div className="grid w-full grid-cols-3 gap-2.5">
                  {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((digit) => (
                    <Key key={digit} onClick={() => press(digit)} disabled={checking}>
                      {digit}
                    </Key>
                  ))}
                  <span />
                  <Key onClick={() => press("0")} disabled={checking}>
                    0
                  </Key>
                  <Key onClick={erase} disabled={checking} aria-label={t("unlock.erase")}>
                    ⌫
                  </Key>
                </div>
              </>
            ) : (
              <>
                <p role="alert" className="text-md text-due">
                  {t(`unlock.${state}`)}
                </p>
                <Button variant="outline" onClick={onRetry}>
                  {t("common.retry")}
                </Button>
              </>
            )}
            {accounts.length > 1 && (
              <Button variant="ghost" size="sm" onClick={() => setChoosing(true)}>
                {t("unlock.changeUser")}
              </Button>
            )}
          </>
        )}
      </div>
    </main>
  );
}

function Key(props: ComponentProps<"button">) {
  return (
    <button
      type="button"
      className="grid h-[58px] cursor-pointer place-items-center rounded-[12px] border border-line bg-card text-xl font-bold hover:bg-surface disabled:opacity-60"
      {...props}
    />
  );
}

const personInitials = (me: Me) => initials(me.last_name, me.first_name, me.middle_name);
