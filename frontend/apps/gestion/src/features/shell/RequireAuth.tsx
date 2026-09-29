import { ApiError } from "@mwangaza/api";
import { changeLanguage, useTranslation } from "@mwangaza/i18n";
import { Skeleton } from "@mwangaza/ui";
import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { stepPath } from "../../lib/login";
import { hasCode, useMe } from "../../lib/queries";
import { ErrorState, SessionExpired, StandaloneStatus } from "../status/StatusPages";
import { OfflineStart } from "./PinUnlock";

/** Écrans réservés à un compte connecté. Pas connecté : la connexion, puis retour à la page
 *  demandée. Session fermée pendant le travail : « Votre session a expiré ». Sans réseau :
 *  déverrouillage par PIN (B5). L'interface prend la langue du compte. */
export function RequireAuth() {
  const { t, i18n } = useTranslation();
  const me = useMe();
  const { pathname, search } = useLocation();
  const language = me.data?.language;

  useEffect(() => {
    if (language && language !== i18n.language) void changeLanguage(language);
  }, [language, i18n.language]);

  if (me.data) {
    if (hasCode(me.error, "not_authenticated")) {
      return (
        <StandaloneStatus>
          <SessionExpired />
        </StandaloneStatus>
      );
    }
    return <Outlet />;
  }
  if (me.isPending) {
    return (
      <StandaloneStatus>
        <Skeleton label={t("common.loading")} />
      </StandaloneStatus>
    );
  }
  if (hasCode(me.error, "not_authenticated")) {
    return <Navigate to={stepPath("password", `${pathname}${search}`)} replace />;
  }
  const retry = () => void me.refetch();
  if (hasCode(me.error, "network")) return <OfflineStart onRetry={retry} />;
  return (
    <StandaloneStatus>
      <ErrorState
        status={me.error instanceof ApiError ? me.error.status : undefined}
        onRetry={retry}
      />
    </StandaloneStatus>
  );
}
