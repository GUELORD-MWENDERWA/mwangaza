import { useTranslation } from "@mwangaza/i18n";
import { Banner, PageHeader } from "@mwangaza/ui";

import { visibleMenu } from "../../lib/menu";
import { displayName } from "../../lib/people";
import { useCurrentMe } from "../../lib/queries";

/** Accueil de la Gestion jusqu'au tableau de bord (4.2). */
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
    </>
  );
}
