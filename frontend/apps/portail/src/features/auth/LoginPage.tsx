import { api, call, ensureCsrf } from "@mwangaza/api";
import { errorMessage, Trans, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CheckboxField,
  Field,
  Icon,
  Input,
  PasswordInput,
  usePlatform,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation } from "react-router";
import { z } from "zod";

import { lastSession, useSignedIn } from "../../lib/account";
import { AuthFrame } from "./AuthFrame";

/** Connexion (maquette `connexion`, M19) : numéro du tuteur principal et mot de passe. */
export function LoginPage() {
  const { t } = useTranslation();
  // Session finie (trace gardée jusqu'à la déconnexion) : numéro rempli, message, puis retour à
  // la page demandée.
  const [last] = useState(lastSession);
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [remember, setRemember] = useState(true);
  const signedIn = useSignedIn((last && from) || "/", remember);
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
    defaultValues: { phone: last?.phone ?? "", password: "" },
  });
  const login = useMutation({
    mutationFn: async (values: z.infer<typeof schema>) => {
      await ensureCsrf();
      return call(api.POST("/api/portal/auth/login/", { body: { ...values, remember } }));
    },
    onSuccess: signedIn,
    onError: () => form.resetField("password"),
  });
  const { errors } = form.formState;
  const platform = usePlatform();
  // Seule page du Portail dans les moteurs de recherche (WEB.1c, `infra/routes.caddy`) : titre
  // avec le nom pour la recherche, description, adresse canonique.
  useEffect(() => {
    document.title = t("portal.login.pageTitle", { name: platform.site_name || platform.name });
    return () => {
      document.title = platform.name;
    };
  }, [t, platform.site_name, platform.name]);

  return (
    <AuthFrame title={t("portal.login.title")} subtitle={t("portal.login.subtitle")}>
      <meta name="description" content={t("portal.login.pageDescription")} />
      <link rel="canonical" href={`${window.location.origin}/login`} />
      <Card>
        <CardContent>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={form.handleSubmit((values) => login.mutate(values))}
          >
            <h2 className="text-xl">{t("portal.login.heading")}</h2>
            {login.isError ? (
              <Banner tone="due">{errorMessage(login.error, t)}</Banner>
            ) : (
              last && <Banner>{t("portal.login.sessionEnded")}</Banner>
            )}
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
            <Field
              id="password"
              label={t("portal.login.password")}
              error={errors.password?.message}
            >
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
            <CheckboxField
              id="remember"
              label={t("portal.login.remember")}
              checked={remember}
              onCheckedChange={(checked) => setRemember(checked === true)}
            />
            <Button type="submit" size="lg" disabled={login.isPending}>
              {t("portal.login.submit")}
            </Button>
            <Link to="/forgot-password" className="self-center text-lake underline">
              {t("portal.login.forgot")}
            </Link>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-lamp-soft text-ink">
            <Icon name="key" size={20} />
          </span>
          <p className="flex-1">
            <Trans i18nKey="portal.login.firstTime" components={{ b: <b /> }} />
          </p>
          <Button asChild variant="outline" size="sm">
            <Link to="/activate">{t("portal.login.activate")}</Link>
          </Button>
        </CardContent>
      </Card>
    </AuthFrame>
  );
}
