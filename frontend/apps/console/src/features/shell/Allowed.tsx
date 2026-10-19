// Pages de la console selon les droits du membre (EQ.2, maquette `console/equipe`) : une page hors
// de ses rôles montre un message au lieu d'une erreur 403, et l'accueil mène à sa première page.
import { useTranslation } from "@mwangaza/i18n";
import { buttonVariants } from "@mwangaza/ui";
import type { ReactNode } from "react";
import { Link, Navigate } from "react-router";

import { RIGHTS, type Right, menuFor, useCan } from "../../lib/rights";
import { DashboardPage } from "../dashboard/DashboardPage";

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

/** La page, si le membre a l'un de ces droits. */
export function Allowed({ rights, children }: { rights: readonly Right[]; children: ReactNode }) {
  const can = useCan();
  return can(...rights) ? children : <NoRight />;
}

/** Tableau de bord ; sans « voir les écoles », la première page du menu du membre. */
export function Home() {
  const can = useCan();
  if (can(RIGHTS.schoolsView)) return <DashboardPage />;
  const first = menuFor(can)[0];
  return first ? <Navigate to={first.to} replace /> : <NoRight home={false} />;
}
