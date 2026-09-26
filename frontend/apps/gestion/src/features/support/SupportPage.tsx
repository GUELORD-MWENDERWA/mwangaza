import { api, call } from "@mwangaza/api";
import { Trans, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Brand,
  Button,
  Card,
  CardContent,
  Field,
  Icon,
  SchoolBadge,
  Textarea,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useLogout } from "../../lib/session";

export const REASON_MAX = 200;

/** Session support « en tant qu'école » (A3, maquette `session-support`) : le super-admin,
 *  connecté à l'adresse de l'école avec la double authentification, ouvre une session d'une heure
 *  avec un motif. Lien « Ouvrir en tant qu'école » de l'administration Django. */
export function SupportPage() {
  const me = useCurrentMe();
  if (!me.is_platform_admin || me.support) return <Navigate to="/" replace />;
  return <OpenSupportSession />;
}

function OpenSupportSession() {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const logout = useLogout();
  const schema = useMemo(
    () =>
      z.object({
        reason: z
          .string()
          .trim()
          .min(1, t("validation.reasonRequired"))
          .max(REASON_MAX, t("validation.reasonMax")),
      }),
    [t],
  );
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { reason: "" } });
  const [general, setGeneral] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      call(api.POST("/api/support/", { body: values })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.me });
      navigate("/", { replace: true });
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["reason"], form.setError, t)),
  });

  return (
    <main className="grid min-h-screen place-items-center bg-surface p-4">
      <div className="flex w-full max-w-[560px] flex-col gap-4">
        <Brand className="self-center" />
        <Card>
          <form
            noValidate
            onSubmit={form.handleSubmit((values) => {
              setGeneral(null);
              open.mutate(values);
            })}
          >
            <CardContent className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <SchoolBadge
                  code={school.code}
                  name={school.name}
                  color={school.primary_color}
                  textColor={school.text_color}
                  logo={school.logo}
                />
                <div>
                  <b>{school.name}</b>
                  <br />
                  <span className="text-sm text-ink-3">{window.location.host}</span>
                </div>
              </div>
              <h1 className="text-lg">{t("support.title")}</h1>
              <p className="text-sm text-ink-3">{t("support.subtitle")}</p>
              <Banner tone="info" className="text-sm">
                <Trans i18nKey="support.rules" components={{ b: <b /> }} />
              </Banner>
              {general && <Banner tone="due">{general}</Banner>}
              {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
              <Field
                id="reason"
                label={t("support.reason")}
                required
                help={t("support.reasonHelp")}
                error={form.formState.errors.reason?.message}
              >
                {(control) => (
                  <Textarea
                    {...control}
                    {...form.register("reason")}
                    rows={3}
                    maxLength={REASON_MAX}
                    placeholder={t("support.reasonPlaceholder")}
                    autoFocus
                  />
                )}
              </Field>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <button
                  type="button"
                  className="cursor-pointer text-sm text-lake underline"
                  onClick={() => logout.mutate()}
                  disabled={logout.isPending}
                >
                  {t("common.logout")}
                </button>
                <Button type="submit" disabled={open.isPending}>
                  <Icon name="shield" size={16} />
                  {t("support.submit")}
                </Button>
              </div>
            </CardContent>
          </form>
        </Card>
      </div>
    </main>
  );
}
