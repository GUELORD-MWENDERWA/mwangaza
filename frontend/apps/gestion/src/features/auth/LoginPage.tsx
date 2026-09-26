import { api, call, ensureCsrf } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Field, Input, PasswordInput } from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "../../lib/errors";
import { useLoginContext } from "./LoginLayout";
import { useGoToStep } from "./useGoToStep";

/** Étape 1 : numéro de téléphone et mot de passe (maquette `connexion`). */
export function LoginPage() {
  const { t } = useTranslation();
  const { next } = useLoginContext();
  const goToStep = useGoToStep(next);
  const [forgot, setForgot] = useState(false);
  const schema = useMemo(
    () =>
      z.object({
        phone: z.string().trim().min(1, t("validation.phoneRequired")),
        password: z.string().min(1, t("validation.passwordRequired")),
      }),
    [t],
  );
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { phone: "", password: "" },
  });
  const login = useMutation({
    mutationFn: async (values: z.infer<typeof schema>) => {
      await ensureCsrf();
      return call(api.POST("/api/auth/login/", { body: values }));
    },
    onSuccess: ({ step }) => goToStep(step),
    onError: () => form.resetField("password"),
  });
  const { errors } = form.formState;

  return (
    <form
      noValidate
      className="flex flex-col gap-3"
      onSubmit={form.handleSubmit((values) => login.mutate(values))}
    >
      <h1>{t("auth.login.title")}</h1>
      <p className="text-ink-3">{t("auth.login.subtitle")}</p>
      {login.isError && <Banner tone="due">{errorMessage(login.error, t)}</Banner>}
      <Field id="phone" label={t("auth.login.phone")} error={errors.phone?.message}>
        {(control) => (
          <Input
            {...control}
            {...form.register("phone")}
            type="tel"
            inputMode="tel"
            autoComplete="username"
            placeholder={t("auth.login.phonePlaceholder")}
            autoFocus
          />
        )}
      </Field>
      <Field id="password" label={t("auth.login.password")} error={errors.password?.message}>
        {(control) => (
          <PasswordInput
            {...control}
            {...form.register("password")}
            autoComplete="current-password"
            showLabel={t("common.showPassword")}
            hideLabel={t("common.hidePassword")}
          />
        )}
      </Field>
      <div className="flex justify-end text-sm">
        <button
          type="button"
          className="cursor-pointer text-lake underline"
          aria-expanded={forgot}
          onClick={() => setForgot((shown) => !shown)}
        >
          {t("auth.login.forgot")}
        </button>
      </div>
      {forgot && <Banner tone="info">{t("auth.login.forgotHelp")}</Banner>}
      <Button type="submit" size="lg" disabled={login.isPending}>
        {t("auth.login.submit")}
      </Button>
    </form>
  );
}
