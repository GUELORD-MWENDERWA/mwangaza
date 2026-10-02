import { ApiError } from "@mwangaza/api";
import { changeLanguage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Skeleton } from "@mwangaza/ui";
import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { stepPath } from "../../lib/login";
import { hasCode, useMe } from "../../lib/queries";
import { ConsoleFrame } from "../auth/LoginLayout";
import { useLogout } from "../auth/useGoToStep";

/** Console réservée au super-admin connecté (le serveur vérifie chaque point d'API). Pas
 *  connecté : la connexion, puis retour à la page demandée. L'interface prend la langue du
 *  compte. */
export function RequireAdmin() {
  const { t, i18n } = useTranslation();
  const me = useMe();
  const { pathname, search } = useLocation();
  const logout = useLogout();
  const language = me.data?.language;

  useEffect(() => {
    if (language && language !== i18n.language) void changeLanguage(language);
  }, [language, i18n.language]);

  if (me.isPending) {
    return (
      <ConsoleFrame>
        <Skeleton label={t("common.loading")} />
      </ConsoleFrame>
    );
  }
  if (hasCode(me.error, "not_authenticated")) {
    return <Navigate to={stepPath("password", `${pathname}${search}`)} replace />;
  }
  if (me.isError || !me.data.is_platform_admin) {
    return (
      <ConsoleFrame>
        {me.data ? (
          <>
            <h1>{t("console.denied.title")}</h1>
            <p className="text-ink-3">{t("console.denied.text")}</p>
            <Button variant="outline" onClick={() => void logout()}>
              {t("common.logout")}
            </Button>
          </>
        ) : (
          <>
            <Banner tone="due">
              {t("errors.unknown", {
                code: me.error instanceof ApiError ? me.error.code : "js",
              })}
            </Banner>
            <Button variant="outline" onClick={() => void me.refetch()}>
              {t("common.retry")}
            </Button>
          </>
        )}
      </ConsoleFrame>
    );
  }
  return <Outlet />;
}
