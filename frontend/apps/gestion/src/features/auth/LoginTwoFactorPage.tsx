import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Skeleton } from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";

import { errorMessage } from "../../lib/errors";
import { useLoginContext } from "./LoginLayout";
import { TwoFactorSetup } from "./TwoFactorSetup";
import { useCancelLogin } from "./useCancelLogin";
import { useGoToStep } from "./useGoToStep";

/** Étape `totp_setup` : un rôle du compte exige la double authentification (B4) ; impossible
 *  d'entrer dans l'application avant la fin. */
export function LoginTwoFactorPage() {
  const { t } = useTranslation();
  const { next } = useLoginContext();
  const goToStep = useGoToStep(next);
  const cancel = useCancelLogin(next);
  // Une seule clé par visite de la page (le serveur la garde dans la session jusqu'à l'activation).
  const key = useQuery({
    queryKey: ["totp-setup", "login"],
    queryFn: () => call(api.POST("/api/auth/totp/setup/", { body: {} })),
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="text-ink-3">{t("auth.setup.required")}</span>
        <button
          type="button"
          className="cursor-pointer text-lake underline"
          onClick={() => void cancel()}
        >
          {t("common.logout")}
        </button>
      </div>
      <h1>{t("auth.setup.title")}</h1>
      <p className="text-ink-3">{t("auth.setup.subtitle")}</p>
      {key.isPending && <Skeleton label={t("common.loading")} />}
      {key.isError && (
        <>
          <Banner tone="due">{errorMessage(key.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void cancel()}>
            {t("common.back")}
          </Button>
        </>
      )}
      {key.data && (
        <TwoFactorSetup totpKey={key.data} onDone={goToStep} onExpired={() => void key.refetch()} />
      )}
    </div>
  );
}
