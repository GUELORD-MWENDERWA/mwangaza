// Interrupteur Réel / Démonstration et bandeau du mode démonstration (lot 5, ②bis, maquettes
// `console/tableau-de-bord` et `console/menu`).
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, cn } from "@mwangaza/ui";
import { useQueryClient } from "@tanstack/react-query";
import { matchPath, useLocation, useNavigate } from "react-router";

import { type ConsoleMode, setConsoleMode, useConsoleMode } from "../../lib/mode";
import { menuFor, useCan } from "../../lib/rights";

const MODES = ["live", "demo"] as const satisfies readonly ConsoleMode[];

/** Changer de mode : plus rien de l'autre mode en mémoire, et retour à la liste de la page ouverte
 *  (ou au tableau de bord si elle n'existe pas dans ce mode). */
export function useSwitchMode() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const can = useCan();
  const mode = useConsoleMode();
  return (next: ConsoleMode) => {
    if (next === mode) return;
    setConsoleMode(next);
    queryClient.removeQueries({ queryKey: ["console"] });
    const page = menuFor(can, next).find(
      (item) => item.to !== "/" && matchPath({ path: item.to, end: false }, pathname),
    );
    void navigate(page?.to ?? "/");
  };
}

export function ModeSwitch({ onSwitch }: { onSwitch?: () => void }) {
  const { t } = useTranslation();
  const mode = useConsoleMode();
  const switchMode = useSwitchMode();
  return (
    <div>
      <div
        role="radiogroup"
        aria-label={t("console.shell.mode.label")}
        className="grid grid-cols-2 gap-1 rounded-box bg-night-2 p-1 ring-1 ring-night-3 ring-inset"
      >
        {MODES.map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={mode === value}
            onClick={() => {
              switchMode(value);
              onSwitch?.();
            }}
            className={cn(
              "min-h-11 cursor-pointer rounded-field px-1.5 text-sm font-semibold transition-colors min-[900px]:min-h-9",
              mode !== value && "text-night-soft hover:text-white",
              mode === value && value === "live" && "bg-card text-night",
              mode === value && value === "demo" && "bg-warn text-white",
            )}
          >
            {t(`console.shell.mode.${value}`)}
          </button>
        ))}
      </div>
      <p className="px-1 pt-1.5 text-xs text-night-muted">{t(`console.shell.mode.${mode}Hint`)}</p>
    </div>
  );
}

/** Bandeau orange sur chaque page en démonstration ; rien en mode réel. */
export function DemoBanner() {
  const { t } = useTranslation();
  const mode = useConsoleMode();
  const switchMode = useSwitchMode();
  if (mode !== "demo") return null;
  return (
    <Banner
      tone="warn"
      className="rounded-none"
      role="note"
      action={
        <Button size="sm" variant="outline" onClick={() => switchMode("live")}>
          {t("console.shell.backToLive")}
        </Button>
      }
    >
      <b>{t("console.shell.demoBanner.title")}</b> {t("console.shell.demoBanner.text")}
    </Banner>
  );
}
