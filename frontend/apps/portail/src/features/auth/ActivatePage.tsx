import { api, call, ensureCsrf } from "@mwangaza/api";
import { applyServerErrors, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, CardContent, Field, Input, PasswordInput } from "@mwangaza/ui";
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

/** Activation du compte famille (maquette `activation`, H1) : numéro donné à l'école, code
 *  famille de la fiche d'inscription, mot de passe choisi ; connecté ensuite. */
export function ActivatePage() {
  const { t } = useTranslation();
  // « Installer » proposé une fois, juste après l'activation (M19).
  // Le guide d'abord, puis « Installer » s'il est proposé (M20, M19).
  const signedIn = useSignedIn("/guide?first=1");
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(
    () =>
      z.object({
        phone: z.string().trim().min(1, t("validation.phoneRequired")),
        code: z.string().trim().min(1, t("validation.codeRequired")),
        password: z.string().min(10, t("validation.passwordMin")),
      }),
    [t],
  );
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { phone: "", code: "", password: "" },
  });
  const activate = useMutation({
    mutationFn: async (values: z.infer<typeof schema>) => {
      await ensureCsrf();
      return call(api.POST("/api/portal/auth/activate/", { body: { ...values, remember: true } }));
    },
    onMutate: () => setGeneral(null),
    onSuccess: signedIn,
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  const { errors } = form.formState;

  return (
    <AuthFrame title={t("portal.activate.title")} subtitle={t("portal.activate.subtitle")}>
      <Card>
        <CardContent>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={form.handleSubmit((values) => activate.mutate(values))}
          >
            <h2 className="text-[1.4rem]">{t("portal.activate.heading")}</h2>
            {general && <Banner tone="due">{general}</Banner>}
            <Field
              id="phone"
              label={t("portal.login.phone")}
              help={t("portal.activate.phoneHint")}
              error={errors.phone?.message}
            >
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
            <Field
              id="code"
              label={t("portal.activate.code")}
              help={t("portal.activate.codeHint")}
              error={errors.code?.message}
            >
              {(control) => <FamilyCodeInput {...control} {...form.register("code")} />}
            </Field>
            <Field
              id="password"
              label={t("portal.activate.password")}
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
            <Button type="submit" size="lg" disabled={activate.isPending}>
              {t("portal.activate.submit")}
            </Button>
            <p className="text-ink-3">
              {t("portal.activate.hasAccount")}{" "}
              <Link to="/login" className="text-lake underline">
                {t("portal.activate.login")}
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center gap-4">
          <div
            aria-hidden="true"
            className="flex w-[150px] shrink-0 flex-col gap-1 rounded-card border border-line p-2.5 text-[.62rem] leading-tight"
          >
            <span className="uppercase">{t("portal.activate.form")}</span>
            <span className="text-ink-3">……… ………</span>
            <span className="mt-1 rounded border-2 border-lamp px-1.5 py-1 font-bold">
              {t("portal.activate.code")}
              <br />
              K7M4-P9TX
            </span>
          </div>
          <p>{t("portal.activate.where")}</p>
        </CardContent>
      </Card>
    </AuthFrame>
  );
}
