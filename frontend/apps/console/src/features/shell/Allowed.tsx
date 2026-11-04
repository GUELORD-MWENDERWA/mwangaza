// Pages de la console selon les droits du membre (EQ.2, maquette `console/equipe`) : une page hors
// de ses rôles montre un message au lieu d'une erreur 403, et l'accueil mène à sa première page.
import { useTranslation } from "@mwangaza/i18n";
import { Button, buttonVariants } from "@mwangaza/ui";
import type { ReactNode } from "react";
import { Link, Navigate } from "react-router";

import { useConsoleMode } from "../../lib/mode";
import { RIGHTS, type Right, menuFor, useCan } from "../../lib/rights";
import { DashboardPage } from "../dashboard/DashboardPage";
import { useSwitchMode } from "./ModeSwitch";

function NoRight({ home = true }: { home?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <h1>{t("console.noRight.title")}</h1>
      <p className="text-ink-3">{t("console.noRight.text")}</p>
      {home && (
        <Link to="/" className={`${buttonVariants({ variant: "outline" })} w-fit`}>
          {t("console.noRight.home")}
        </Link>
      )}
    </div>
  );
}

/** Page qui n'existe qu'en mode réel, ouverte en démonstration (adresse tapée, lien gardé). */
function LiveOnly() {
  const { t } = useTranslation();
  const switchMode = useSwitchMode();
  return (
    <div className="flex flex-col gap-3">
      <h1>{t("console.shell.liveOnly.title")}</h1>
      <p className="text-ink-3">{t("console.shell.liveOnly.text")}</p>
      <Button variant="outline" className="w-fit" onClick={() => switchMode("live")}>
        {t("console.shell.backToLive")}
      </Button>
    </div>
  );
}

/** La page, si le membre a l'un de ces droits ; `live` : en mode réel seulement. */
export function Allowed({
  rights,
  live = false,
  children,
}: {
  rights: readonly Right[];
  live?: boolean;
  children: ReactNode;
}) {
  const can = useCan();
  const mode = useConsoleMode();
  if (!can(...rights)) return <NoRight />;
  return live && mode === "demo" ? <LiveOnly /> : children;
}

/** Tableau de bord ; sans « voir les écoles », la première page du menu du membre. */
export function Home() {
  const can = useCan();
  const mode = useConsoleMode();
  if (can(RIGHTS.schoolsView)) return <DashboardPage />;
  const first = menuFor(can, mode)[0];
  return first ? <Navigate to={first.to} replace /> : <NoRight home={false} />;
}
