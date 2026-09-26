import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Field, PasswordInput } from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { hasCode } from "../../lib/queries";
import { useLoginContext } from "./LoginLayout";
import { useGoToStep } from "./useGoToStep";

export function passwordSchema(
  t: (key: "validation.passwordMin" | "validation.passwordMismatch") => string,
) {
  return z
    .object({
      new_password: z.string().min(10, t("validation.passwordMin")),
      confirm: z.string(),
    })
    .refine((values) => values.new_password === values.confirm, {
      path: ["confirm"],
      message: t("validation.passwordMismatch"),
    });
}

/** Étape `new_password` : le mot de passe provisoire donné par l'école est remplacé. */
export function NewPasswordPage() {
  const { t } = useTranslation();
  const { next } = useLoginContext();
  const goToStep = useGoToStep(next);
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(() => passwordSchema(t), [t]);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm: "" },
  });
  const save = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      call(api.POST("/api/auth/password/", { body: { new_password: values.new_password } })),
    onSuccess: ({ step }) => goToStep(step),
    onError: (error) => {
      if (hasCode(error, "login_expired", "wrong_step")) goToStep("password");
      setGeneral(applyServerErrors(error, ["new_password"], form.setError, t));
    },
  });
  const { errors } = form.formState;

  return (
    <form
      noValidate
      className="flex flex-col gap-3"
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        save.mutate(values);
      })}
    >
      <h1>{t("auth.newPassword.title")}</h1>
      <p className="text-ink-3">{t("auth.newPassword.subtitle")}</p>
      {general && <Banner tone="due">{general}</Banner>}
      <Field
        id="new-password"
        label={t("auth.newPassword.new")}
        help={t("auth.newPassword.help")}
        error={errors.new_password?.message}
      >
        {(control) => (
          <PasswordInput
            {...control}
            {...form.register("new_password")}
            autoComplete="new-password"
            showLabel={t("common.showPassword")}
            hideLabel={t("common.hidePassword")}
            autoFocus
          />
        )}
      </Field>
      <Field
        id="confirm-password"
        label={t("auth.newPassword.confirm")}
        error={errors.confirm?.message}
      >
        {(control) => (
          <PasswordInput
            {...control}
            {...form.register("confirm")}
            autoComplete="new-password"
            placeholder={t("auth.newPassword.confirmPlaceholder")}
            showLabel={t("common.showPassword")}
            hideLabel={t("common.hidePassword")}
          />
        )}
      </Field>
      <Button type="submit" size="lg" disabled={save.isPending}>
        {t("auth.newPassword.submit")}
      </Button>
    </form>
  );
}
