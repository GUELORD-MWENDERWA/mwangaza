import { useTranslation } from "@mwangaza/i18n";
import {
  Brand,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  isIos,
  useInstallPrompt,
  useJustInstalled,
  usePlatform,
} from "@mwangaza/ui";
import { useEffect, useState, type ReactNode } from "react";

import {
  canSkip,
  countDismissal,
  dismissals,
  installRequired,
  NO_PROMPT_DELAY_MS,
  skipInstall,
} from "./installGate";

const BENEFITS = ["offline", "fast", "notifications", "icon"] as const;
const IOS_STEPS = ["share", "addToHome", "add"] as const;

/** Écran « Installe l'application » (4.24), avant la connexion : le personnel travaille dans
 *  l'application installée (hors-ligne, notifications, icône), pas dans un onglet. Un navigateur
 *  ne peut ni se fermer ni lancer l'application installée : une fois installée, on dit d'ouvrir
 *  l'icône. Issue de secours pour qu'un appareil qui ne sait pas installer ne bloque pas la caisse. */
export function InstallGate({ children }: { children: ReactNode }) {
  const [skipped, setSkipped] = useState(() => !installRequired());
  if (skipped) return children;
  return (
    <InstallScreen
      onSkip={() => {
        skipInstall();
        setSkipped(true);
      }}
    />
  );
}

function InstallScreen({ onSkip }: { onSkip: () => void }) {
  const { t } = useTranslation();
  const platform = usePlatform().name;
  const install = useInstallPrompt();
  const installed = useJustInstalled();
  const ios = isIos();
  const [dismissed, setDismissed] = useState(dismissals);
  const [waited, setWaited] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setWaited(true), NO_PROMPT_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  const skippable = !installed && canSkip({ dismissed, ios, waited: waited && !install });

  return (
    <main className="grid min-h-screen place-items-center bg-surface p-4">
      <div className="flex w-full max-w-[520px] flex-col gap-4">
        <Brand className="self-center" />
        <Card>
          <CardHeader>
            <CardTitle>
              {installed
                ? t("installGate.doneTitle", { platform })
                : t("installGate.title", { platform })}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {installed ? (
              <>
                <p>{t("installGate.openIcon", { platform })}</p>
                <p className="text-[.88rem] text-ink-3">{t("installGate.closeTab")}</p>
              </>
            ) : (
              <>
                <p>{t("installGate.intro", { platform })}</p>
                <ul className="flex flex-col gap-2.5">
                  {BENEFITS.map((key) => (
                    <li key={key} className="flex items-center gap-2.5">
                      <Icon name="check" size={18} className="shrink-0 text-ok" />
                      {t(`installGate.benefits.${key}`)}
                    </li>
                  ))}
                </ul>
                {install ? (
                  <Button
                    size="lg"
                    onClick={() =>
                      void install().then((accepted) => {
                        if (!accepted) setDismissed(countDismissal());
                      })
                    }
                  >
                    {t("installGate.install")}
                  </Button>
                ) : ios ? (
                  <ol className="flex flex-col gap-2.5">
                    {IOS_STEPS.map((key, index) => (
                      <li key={key} className="flex items-center gap-2.5">
                        <span className="grid size-6 shrink-0 place-items-center rounded-full bg-gray-50 text-[.8rem] font-bold">
                          {index + 1}
                        </span>
                        {t(`installGate.iosSteps.${key}`)}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-[.88rem] text-ink-3">{t("installGate.browserMenu")}</p>
                )}
                <p className="text-[.88rem] text-ink-3">{t("installGate.alreadyInstalled")}</p>
              </>
            )}
            {skippable && (
              <Button variant="ghost" onClick={onSkip}>
                {t("installGate.skip")}
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
