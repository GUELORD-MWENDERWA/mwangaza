import { useTranslation } from "@mwangaza/i18n";
import type { ReactNode } from "react";

import type { MenuItem } from "../../lib/menu";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { ComingSoon, Forbidden } from "../status/StatusPages";

/** Écran d'une entrée du menu : refusé sans un de ses droits (lien recopié, favori), sinon
 *  l'écran, ou « bientôt disponible » tant que sa tâche n'est pas faite. Le serveur vérifie de
 *  toute façon. */
export function MenuScreen({ item, children }: { item: MenuItem; children?: ReactNode }) {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const page = t(`shell.menu.${item.key}`);
  if (!can(me, item.permissions)) return <Forbidden page={page} />;
  return children ?? <ComingSoon page={page} />;
}
