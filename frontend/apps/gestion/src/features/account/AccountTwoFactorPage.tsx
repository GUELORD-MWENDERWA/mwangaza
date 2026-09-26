import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  Field,
  Input,
  PageHeader,
  Skeleton,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { errorMessage } from "../../lib/errors";
import { hasCode, keys, useCurrentMe } from "../../lib/queries";
import { TwoFactorSetup } from "../auth/TwoFactorSetup";

/** Activer la double authentification depuis Mon compte, ou changer de téléphone (M1, M4) :
 *  déjà activée, le code actuel (ou un code de secours) est demandé avant la nouvelle clé. */
export function AccountTwoFactorPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Le compte au moment d'arriver sur la page (il change après l'activation).
  const [changing] = useState(me.totp_enabled);
  const [code, setCode] = useState("");
  const [missing, setMissing] = useState(false);
  // Première activation : une clé demandée tout de suite, une seule par visite de la page.
  const firstKey = useQuery({
    queryKey: ["totp-setup", "account"],
    queryFn: () => call(api.POST("/api/auth/totp/setup/", { body: {} })),
    enabled: !changing,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });
  // Changer de téléphone : la clé après le code actuel.
  const setup = useMutation({
    mutationFn: (current: string) =>
      call(api.POST("/api/auth/totp/setup/", { body: { code: current } })),
  });
  const totpKey = changing ? setup.data : firstKey.data;
  const keyError = changing ? setup.error : firstKey.error;

  function askKey(event: FormEvent) {
    event.preventDefault();
    const value = code.trim();
    setMissing(!value);
    if (value) setup.mutate(value);
  }

  async function done() {
    await queryClient.invalidateQueries({ queryKey: keys.me });
    navigate("/account");
  }

  const title = changing ? t("auth.setup.changeTitle") : t("auth.setup.title");
  const subtitle = changing
    ? t("auth.setup.changeSubtitle")
    : me.totp_required
      ? t("auth.setup.subtitle")
      : t("auth.setup.optionalSubtitle");
  const askingCode = changing && !setup.data;
  const fieldError = missing
    ? t("validation.codeRequired")
    : hasCode(setup.error, "invalid_code")
      ? errorMessage(setup.error, t)
      : undefined;

  return (
    <>
      <PageHeader
        crumbs={<Link to="/account">{t("account.title")}</Link>}
        title={title}
        subtitle={subtitle}
      />
      {askingCode ? (
        <Card className="max-w-[480px]">
          <form noValidate onSubmit={askKey}>
            <CardContent className="flex flex-col gap-3">
              {setup.isError && !hasCode(setup.error, "invalid_code") && (
                <Banner tone="due">{errorMessage(setup.error, t)}</Banner>
              )}
              <Field id="current-code" label={t("auth.setup.currentCode")} error={fieldError}>
                {(control) => (
                  <Input
                    {...control}
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    autoComplete="one-time-code"
                    maxLength={20}
                    autoFocus
                  />
                )}
              </Field>
              <div className="flex flex-wrap justify-between gap-3">
                <Button asChild variant="outline">
                  <Link to="/account">{t("common.cancel")}</Link>
                </Button>
                <Button type="submit" disabled={setup.isPending}>
                  {t("auth.setup.askKey")}
                </Button>
              </div>
            </CardContent>
          </form>
        </Card>
      ) : totpKey ? (
        <TwoFactorSetup
          totpKey={totpKey}
          phone={me.phone}
          onDone={() => void done()}
          onExpired={() => {
            setCode("");
            setup.reset();
            if (!changing) void firstKey.refetch();
          }}
        />
      ) : keyError ? (
        <>
          <Banner tone="due">{errorMessage(keyError, t)}</Banner>
          <Button asChild variant="outline" className="w-fit">
            <Link to="/account">{t("common.back")}</Link>
          </Button>
        </>
      ) : (
        <Skeleton label={t("common.loading")} />
      )}
    </>
  );
}
