import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, CodeInput, Field, Icon, Input } from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { hasCode } from "../../lib/queries";
import { useLoginContext } from "./LoginLayout";
import { useGoToStep, useLogout } from "./useGoToStep";

/** Étape `totp` : code de l'application, ou code de secours. Toujours demandée sur la console
 *  (pas d'appareil de confiance). */
export function CodePage() {
  const { t } = useTranslation();
  const { next } = useLoginContext();
  const goToStep = useGoToStep(next);
  const cancel = useLogout(next);
  const [recovery, setRecovery] = useState(false);
  const [code, setCode] = useState("");
  const [missing, setMissing] = useState(false);
  const verify = useMutation({
    mutationFn: () =>
      call(api.POST("/api/auth/login/totp/", { body: { code: code.trim(), trust_device: false } })),
    onSuccess: ({ step }) => goToStep(step),
    onError: (error) => {
      setCode("");
      if (hasCode(error, "login_expired", "wrong_step")) goToStep("password");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const complete = recovery ? code.trim().length > 0 : code.length === 6;
    setMissing(!complete);
    if (complete) verify.mutate();
  }

  function switchMode() {
    setRecovery((value) => !value);
    setCode("");
    setMissing(false);
    verify.reset();
  }

  const fieldError = missing
    ? t(recovery ? "validation.recoveryRequired" : "validation.codeLength")
    : hasCode(verify.error, "invalid_code")
      ? errorMessage(verify.error, t)
      : undefined;
  const generalError =
    verify.isError && !hasCode(verify.error, "invalid_code") ? errorMessage(verify.error, t) : null;

  return (
    <form noValidate className="flex flex-col gap-3" onSubmit={submit}>
      <button
        type="button"
        onClick={() => void cancel()}
        className="flex w-fit cursor-pointer items-center gap-1 text-sm text-lake underline"
      >
        <Icon name="back" size={14} />
        {t("common.back")}
      </button>
      <h1>{t(recovery ? "auth.code.recoveryTitle" : "auth.code.title")}</h1>
      <p className="text-ink-3">
        {t(recovery ? "auth.code.recoverySubtitle" : "auth.code.subtitle")}
      </p>
      {generalError && <Banner tone="due">{generalError}</Banner>}
      {recovery ? (
        <Field id="recovery-code" label={t("auth.code.recoveryLabel")} error={fieldError}>
          {(control) => (
            <Input
              {...control}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              placeholder={t("auth.code.recoveryPlaceholder")}
              className="font-mono tracking-[.08em]"
              autoFocus
            />
          )}
        </Field>
      ) : (
        <Field id="code" label={t("auth.code.label")} error={fieldError}>
          {(control) => <CodeInput {...control} value={code} onValueChange={setCode} autoFocus />}
        </Field>
      )}
      <Button type="submit" size="lg" disabled={verify.isPending}>
        {t("auth.code.submit")}
      </Button>
      <button
        type="button"
        onClick={switchMode}
        className="w-fit cursor-pointer text-left text-sm text-lake underline"
      >
        {t(recovery ? "auth.code.useApp" : "auth.code.useRecovery")}
      </button>
    </form>
  );
}
