// Mon compte (M4) : actions de la double authentification qui demandent le code actuel de
// l'application ou un code de secours (le serveur le vérifie et compte les essais ratés).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, DialogClose, DialogContent, DialogRoot, Field, Input } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { errorMessage } from "../../lib/errors";
import { hasCode, keys } from "../../lib/queries";
import { RecoveryCodes } from "../auth/RecoveryCodes";

/** Champ « code actuel ou code de secours » d'une fenêtre ; erreur `invalid_code` sous le champ. */
function CurrentCodeForm({
  id,
  mutation,
}: {
  id: string;
  mutation: { mutate: (code: string) => void; error: Error | null; isError: boolean };
}) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [missing, setMissing] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = code.trim();
    setMissing(!value);
    if (value) mutation.mutate(value);
  }

  const fieldError = missing
    ? t("validation.codeRequired")
    : hasCode(mutation.error, "invalid_code")
      ? errorMessage(mutation.error, t)
      : undefined;
  return (
    <form id={id} noValidate onSubmit={submit} className="flex flex-col gap-3">
      {mutation.isError && !hasCode(mutation.error, "invalid_code") && (
        <Banner tone="due">{errorMessage(mutation.error, t)}</Banner>
      )}
      <Field id={`${id}-code`} label={t("auth.setup.currentCode")} error={fieldError}>
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
    </form>
  );
}

/** Nouveaux codes de secours : les anciens ne marchent plus. Les nouveaux sont montrés une seule
 *  fois ; la fenêtre ne se ferme pas d'un clic à côté tant qu'ils sont affichés. */
export function NewRecoveryCodesDialog({ phone }: { phone: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const generate = useMutation({
    mutationFn: (code: string) =>
      call(api.POST("/api/auth/totp/recovery-codes/", { body: { code } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.me }),
  });
  const codes = generate.data?.recovery_codes ?? null;

  function changeOpen(next: boolean) {
    setOpen(next);
    if (!next) generate.reset();
  }

  const keepOpen = (event: Event) => {
    if (codes) event.preventDefault();
  };
  return (
    <DialogRoot open={open} onOpenChange={changeOpen}>
      <Button size="sm" onClick={() => setOpen(true)}>
        {t("account.twoFactor.newCodes")}
      </Button>
      <DialogContent
        title={t("account.twoFactor.newCodes")}
        description={codes ? t("auth.setup.codesText") : t("account.twoFactor.newCodesText")}
        onInteractOutside={keepOpen}
        onEscapeKeyDown={keepOpen}
        footer={
          codes ? undefined : (
            <>
              <DialogClose asChild>
                <Button variant="outline">{t("common.cancel")}</Button>
              </DialogClose>
              <Button type="submit" form="new-codes" disabled={generate.isPending}>
                {t("account.twoFactor.generate")}
              </Button>
            </>
          )
        }
      >
        {codes ? (
          <RecoveryCodes codes={codes} phone={phone} onDone={() => changeOpen(false)} />
        ) : (
          <CurrentCodeForm id="new-codes" mutation={generate} />
        )}
      </DialogContent>
    </DialogRoot>
  );
}

/** Désactiver : seulement si aucun rôle du compte ne l'exige (bouton absent sinon ; le serveur
 *  refuse de toute façon avec `totp_still_required`). */
export function DisableTwoFactorDialog({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const disable = useMutation({
    mutationFn: (code: string) => call(api.POST("/api/auth/totp/disable/", { body: { code } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.me });
      setOpen(false);
      onDone();
    },
  });

  function changeOpen(next: boolean) {
    setOpen(next);
    if (!next) disable.reset();
  }

  return (
    <DialogRoot open={open} onOpenChange={changeOpen}>
      <Button variant="destructive-outline" size="sm" onClick={() => setOpen(true)}>
        {t("account.twoFactor.disable")}
      </Button>
      <DialogContent
        title={t("account.twoFactor.disable")}
        description={t("account.twoFactor.disableText")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button
              type="submit"
              form="disable-totp"
              variant="destructive"
              disabled={disable.isPending}
            >
              {t("account.twoFactor.disable")}
            </Button>
          </>
        }
      >
        <CurrentCodeForm id="disable-totp" mutation={disable} />
      </DialogContent>
    </DialogRoot>
  );
}
