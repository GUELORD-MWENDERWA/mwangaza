import { api, call, ensureCsrf } from "@mwangaza/api";
import { applyServerErrors, Trans, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, CardContent, Field, Icon, Input, PasswordInput } from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { useSignedIn } from "../../lib/account";
import { AuthFrame } from "./AuthFrame";
import { FamilyCodeInput } from "./FamilyCodeInput";

const FIELDS = ["phone", "code", "password"] as const;
const STEPS = ["step1", "step2", "step3"] as const;

/** Mot de passe oublié (maquette `mot-de-passe-oublie`, M19) : pas de SMS ; le secrétariat donne
 *  un nouveau code famille (« Nouveau code », une seule fois, 30 jours) ; connecté ensuite. */
export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const signedIn = useSignedIn();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(
    () =>
      z
        .object({
          phone: z.string().trim().min(1, t("validation.phoneRequired")),
          code: z.string().trim().min(1, t("validation.codeRequired")),
          password: z.string().min(10, t("validation.passwordMin")),
          confirm: z.string(),
        })
        .refine((values) => values.password === values.confirm, {
          path: ["confirm"],
          message: t("validation.passwordMismatch"),
        }),
    [t],
  );
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { phone: "", code: "", password: "", confirm: "" },
  });
  const reset = useMutation({
    mutationFn: async ({ phone, code, password }: z.infer<typeof schema>) => {
      await ensureCsrf();
      const body = { phone, code, password, remember: true };
      return call(api.POST("/api/portal/auth/reset/", { body }));
    },
    onMutate: () => setGeneral(null),
    onSuccess: signedIn,
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  const { errors } = form.formState;

  return (
    <AuthFrame title={t("portal.forgot.title")} subtitle={t("portal.forgot.subtitle")}>
      <Link to="/login" className="flex items-center gap-1.5 self-start text-lake underline">
        <Icon name="back" size={16} />
        {t("portal.forgot.back")}
      </Link>
      <Card>
        <CardContent>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={form.handleSubmit((values) => reset.mutate(values))}
          >
            <h2 className="text-xl">{t("portal.forgot.heading")}</h2>
            <p>
              <Trans i18nKey="portal.forgot.intro" components={{ b: <b /> }} />
            </p>
            <ol className="flex flex-col gap-2.5">
              {STEPS.map((step, index) => (
                <li key={step} className="flex items-start gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-lamp-soft font-bold">
                    {index + 1}
                  </span>
                  <span>
                    <Trans i18nKey={`portal.forgot.${step}`} components={{ b: <b /> }} />
                  </span>
                </li>
              ))}
            </ol>
            {general && <Banner tone="due">{general}</Banner>}
            <Field id="phone" label={t("portal.login.phone")} error={errors.phone?.message}>
              {(control) => (
                <Input
                  {...control}
                  {...form.register("phone")}
                  type="tel"
                  inputMode="tel"
                  autoComplete="username"
                  placeholder={t("portal.login.phonePlaceholder")}
                />
              )}
            </Field>
            <Field id="code" label={t("portal.forgot.code")} error={errors.code?.message}>
              {(control) => <FamilyCodeInput {...control} {...form.register("code")} />}
            </Field>
            <Field
              id="password"
              label={t("portal.forgot.password")}
              help={t("portal.activate.passwordHint")}
              error={errors.password?.message}
            >
              {(control) => (
                <PasswordInput
                  {...control}
                  {...form.register("password")}
                  autoComplete="new-password"
                  showLabel={t("common.showPassword")}
                  hideLabel={t("common.hidePassword")}
                />
              )}
            </Field>
            <Field id="confirm" label={t("portal.forgot.confirm")} error={errors.confirm?.message}>
              {(control) => (
                <PasswordInput
                  {...control}
                  {...form.register("confirm")}
                  autoComplete="new-password"
                  placeholder={t("portal.forgot.confirmPlaceholder")}
                  showLabel={t("common.showPassword")}
                  hideLabel={t("common.hidePassword")}
                />
              )}
            </Field>
            <Button type="submit" size="lg" disabled={reset.isPending}>
              {t("portal.forgot.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthFrame>
  );
}
