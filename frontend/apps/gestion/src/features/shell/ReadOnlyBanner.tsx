import { useTranslation } from "@mwangaza/i18n";
import { Banner } from "@mwangaza/ui";
import { Link } from "react-router";

import { can } from "../../lib/permissions";
import type { Me } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";

/** Bandeau de l'école en lecture seule (ABO.3, maquette `gestion/mon-abonnement`) : tous les rôles
 *  le voient sur chaque écran ; le lien vers « Mon abonnement » seulement avec le droit de le lire. */
export function ReadOnlyBanner({ me }: { me: Me }) {
  const { t } = useTranslation();
  const { read_only } = useCurrentSchool();
  if (!read_only) return null;
  return (
    <Banner tone="warn" className="rounded-none" role="status">
      {t("subscription.readOnly")}{" "}
      {can(me, ["billing.view"]) && (
        <Link className="font-bold underline" to="/subscription">
          {t("subscription.readOnlyLink")}
        </Link>
      )}
    </Banner>
  );
}
