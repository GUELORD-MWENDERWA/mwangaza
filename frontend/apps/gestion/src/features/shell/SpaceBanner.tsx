import { useTranslation } from "@mwangaza/i18n";
import { Banner } from "@mwangaza/ui";

import { useCurrentSchool } from "../../lib/school";

/** Bandeau permanent d'un espace de démonstration ou d'essai (4.18) : rien de ce qu'on y voit
 *  n'est une vraie donnée. Rien dans un espace réel. */
export function SpaceBanner() {
  const { t } = useTranslation();
  const { environment } = useCurrentSchool();
  if (environment === "live") return null;
  return (
    <Banner tone="warn" className="rounded-none" role="note">
      <b>{t(`space.${environment}`)}</b>
    </Banner>
  );
}
