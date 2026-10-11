import { ApiError } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Skeleton, usePlatform } from "@mwangaza/ui";
import { useEffect } from "react";
import { Outlet } from "react-router";

import { hasCode, useSchool } from "../../lib/queries";
import { SchoolContext } from "../../lib/school";
import { ErrorState, NoSchool, StandaloneStatus, Stopped, Suspended } from "../status/StatusPages";
import { OfflineStart } from "./PinUnlock";

/** L'école de l'adresse, lue avant tout écran (nom, couleur, logo, fuseau). École suspendue ou
 *  inconnue : le serveur refuse tout à cette adresse, on le dit sans rien afficher d'autre. Sans
 *  réseau : déverrouillage par PIN d'un compte mémorisé ici (B5). */
export function SchoolGate() {
  const { t } = useTranslation();
  const school = useSchool();
  const name = school.data?.name;
  const platform = usePlatform().name;

  useEffect(() => {
    document.title = [name, platform].filter(Boolean).join(" · ");
  }, [name, platform]);

  if (school.isPending) {
    return (
      <StandaloneStatus>
        <Skeleton label={t("common.loading")} />
      </StandaloneStatus>
    );
  }
  if (school.isError) {
    const { error } = school;
    const retry = () => void school.refetch();
    if (hasCode(error, "network")) return <OfflineStart onRetry={retry} />;
    return (
      <StandaloneStatus>
        {hasCode(error, "school_suspended") ? (
          <Suspended />
        ) : hasCode(error, "school_stopped") ? (
          <Stopped />
        ) : hasCode(error, "school_not_found") ? (
          <NoSchool />
        ) : (
          <ErrorState
            status={error instanceof ApiError ? error.status : undefined}
            onRetry={retry}
          />
        )}
      </StandaloneStatus>
    );
  }
  return (
    <SchoolContext value={school.data}>
      <Outlet />
    </SchoolContext>
  );
}
