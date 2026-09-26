import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Skeleton } from "@mwangaza/ui";
import { Navigate, Outlet, useLocation, useOutletContext, useSearchParams } from "react-router";

import { errorMessage } from "../../lib/errors";
import { safeNext, stepPath } from "../../lib/login";
import { useLoginStep } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { AuthFrame } from "./AuthFrame";

/** Connexion en étapes (API de la 1.3) : chaque page n'est montrée qu'à son étape ; sinon, la
 *  page de l'étape en cours (après un rechargement, une étape expirée…). */
export function LoginLayout() {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const step = useLoginStep();
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));

  if (step.isPending) {
    return (
      <AuthFrame school={school}>
        <Skeleton label={t("common.loading")} />
      </AuthFrame>
    );
  }
  if (step.isError) {
    return (
      <AuthFrame school={school}>
        <Banner tone="due">{errorMessage(step.error, t)}</Banner>
        <Button variant="outline" onClick={() => void step.refetch()}>
          {t("common.retry")}
        </Button>
      </AuthFrame>
    );
  }
  const expected = stepPath(step.data, next);
  if (step.data === "done" || expected.split("?")[0] !== pathname) {
    return <Navigate to={expected} replace />;
  }
  return (
    <AuthFrame school={school} width={step.data === "totp_setup" ? 820 : 400}>
      <Outlet context={{ next } satisfies LoginContext} />
    </AuthFrame>
  );
}

type LoginContext = { next: string };

export function useLoginContext() {
  return useOutletContext<LoginContext>();
}
