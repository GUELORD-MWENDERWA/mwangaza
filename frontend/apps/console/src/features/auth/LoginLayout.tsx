import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Brand, Button, LegalNotice, Skeleton } from "@mwangaza/ui";
import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation, useOutletContext, useSearchParams } from "react-router";

import { safeNext, stepPath } from "../../lib/login";
import { useLoginStep } from "../../lib/queries";
import { ConsoleTag } from "../shell/ConsoleTag";

/** Cadre des écrans hors console : fond bleu nuit, carte blanche au centre, marque et « Console ». */
export function ConsoleFrame({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-night px-4 py-8">
      <main className="flex w-full max-w-[420px] flex-col gap-4 rounded-dialog bg-white p-7 shadow-float">
        <div className="flex items-center gap-3">
          <Brand />
          <ConsoleTag />
        </div>
        {children}
      </main>
      <LegalNotice
        label={t("common.legalNotice")}
        closeLabel={t("common.close")}
        className="text-sm text-night-soft"
      />
    </div>
  );
}

/** Connexion en étapes (API de la 1.3) : chaque page n'est montrée qu'à son étape ; sinon, la
 *  page de l'étape en cours (après un rechargement, une étape expirée…). */
export function LoginLayout() {
  const { t } = useTranslation();
  const step = useLoginStep();
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));

  if (step.isPending) {
    return (
      <ConsoleFrame>
        <Skeleton label={t("common.loading")} />
      </ConsoleFrame>
    );
  }
  if (step.isError) {
    return (
      <ConsoleFrame>
        <Banner tone="due">{errorMessage(step.error, t)}</Banner>
        <Button variant="outline" onClick={() => void step.refetch()}>
          {t("common.retry")}
        </Button>
      </ConsoleFrame>
    );
  }
  const expected = stepPath(step.data, next);
  if (step.data === "done" || expected.split("?")[0] !== pathname) {
    return <Navigate to={expected} replace />;
  }
  return (
    <ConsoleFrame>
      <Outlet context={{ next } satisfies LoginContext} />
    </ConsoleFrame>
  );
}

type LoginContext = { next: string };

export function useLoginContext() {
  return useOutletContext<LoginContext>();
}
