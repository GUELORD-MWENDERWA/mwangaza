import { useTranslation } from "@mwangaza/i18n";
import { Banner, PageHeader } from "@mwangaza/ui";

import { visibleMenu } from "../../lib/menu";
import { displayName } from "../../lib/people";
import { useCurrentMe } from "../../lib/queries";
import { SetupChecklist } from "../dashboard/SetupChecklist";

/** Accueil de la Gestion : premier écran après la connexion. Le directeur d'une école neuve y
 *  trouve la liste « Mise en route » sans avoir à chercher le tableau de bord (4.20.2). */
export function HomePage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const empty = visibleMenu(me).length === 0;
  return (
    <>
      <PageHeader
        title={t("shell.home.title", { name: displayName(me) })}
        subtitle={empty ? undefined : t("shell.home.subtitle")}
      />
      {empty && <Banner tone="info">{t("shell.home.empty")}</Banner>}
      <SetupChecklist />
    </>
  );
}
