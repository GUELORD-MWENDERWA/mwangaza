import { useTranslation } from "@mwangaza/i18n";
import { PageHeader } from "@mwangaza/ui";

import { displayName } from "../../lib/people";
import { useCurrentMe } from "../../lib/queries";
import { SetupChecklist } from "../dashboard/SetupChecklist";

/** Accueil de la Gestion : premier écran après la connexion. Le directeur d'une école neuve y
 *  trouve la liste « Mise en route » sans avoir à chercher le tableau de bord (4.20.2). */
export function HomePage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  return (
    <>
      <PageHeader
        title={t("shell.home.title", { name: displayName(me) })}
        subtitle={t("shell.home.subtitle")}
      />
      <SetupChecklist />
    </>
  );
}
