// Fiche d'un compte dans la console (5.4.1, maquette `console/comptes`) : noms et téléphone,
// mot de passe provisoire (personnel seulement : le portail le refuse), double authentification,
// désactiver / réactiver (après confirmation) ; écoles et rôles, familles du portail, derniers
// changements. Un compte de la plateforme ne se change que dans l'administration Django.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import {
  applyServerErrors,
  errorMessage,
  formatDateTime,
  formatDay,
  formatPhone,
  useTranslation,
} from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Code,
  ConfirmDialog,
  Field,
  Input,
  PageHeader,
  Skeleton,
  StatusPill,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useParams } from "react-router";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { Differences, History } from "../shell/History";
import { AccountPills, fullName } from "./AccountsPage";

type Detail = Schemas["ConsoleAccountDetail"];

const FIELDS = ["last_name", "middle_name", "first_name", "phone"] as const;
const SHOWN = new Set<string>(FIELDS);
type Confirm = "password" | "totp" | "deactivate";

function useSchema() {
  const { t } = useTranslation();
  const name = z.string().trim().max(100);
  return z.object({
    last_name: name.min(1, t("fieldErrors.required")),
    middle_name: name,
    first_name: name,
    phone: z.string().trim().min(1, t("fieldErrors.required")),
  });
}

type Values = z.infer<ReturnType<typeof useSchema>>;

const valuesOf = (account: Detail): Values => ({
  last_name: account.last_name,
  middle_name: account.middle_name,
  first_name: account.first_name,
  phone: account.phone,
});

export function AccountPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const account = useQuery({
    queryKey: [...keys.accounts, id],
    queryFn: () => call(api.GET("/api/console/accounts/{id}/", { params: { path: { id } } })),
  });
  if (account.isPending) return <Skeleton label={t("common.loading")} />;
  if (account.isError) {
    return (
      <>
        <Banner tone="due">{errorMessage(account.error, t)}</Banner>
        <Button variant="outline" className="w-fit" onClick={() => void account.refetch()}>
          {t("common.retry")}
        </Button>
      </>
    );
  }
  return <AccountForm key={account.data.id} account={account.data} />;
}

function AccountForm({ account }: { account: Detail }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [password, setPassword] = useState<string | null>(null);
  const locked = account.is_platform_admin;
  const staff = account.memberships.some((membership) => membership.is_active);
  const form = useForm<Values>({
    resolver: zodResolver(useSchema()),
    defaultValues: valuesOf(account),
  });
  const path = { params: { path: { id: account.id } } };
  const saved = (data: Detail) => {
    queryClient.setQueryData([...keys.accounts, account.id], data);
    // La liste ; pas cette fiche, déjà à jour.
    void queryClient.invalidateQueries({
      queryKey: keys.accounts,
      predicate: (query) => query.queryKey[2] !== account.id,
    });
    form.reset(valuesOf(data));
  };
  const failed = (error: unknown) => {
    setConfirm(null);
    setGeneral(errorMessage(error, t));
  };
  const save = useMutation({
    mutationFn: (body: Values) => call(api.PATCH("/api/console/accounts/{id}/", { ...path, body })),
    onSuccess: saved,
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  const access = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/console/accounts/{id}/", {
          ...path,
          body: { is_active: !account.is_active },
        }),
      ),
    onSuccess: (data) => {
      setConfirm(null);
      saved(data);
    },
    onError: failed,
  });
  const newPassword = useMutation({
    mutationFn: () => call(api.POST("/api/console/accounts/{id}/new-password/", path)),
    onSuccess: (data) => {
      setConfirm(null);
      setPassword(data.temporary_password);
      void queryClient.invalidateQueries({ queryKey: keys.accounts });
    },
    onError: failed,
  });
  const resetTotp = useMutation({
    mutationFn: () => call(api.POST("/api/console/accounts/{id}/reset-totp/", path)),
    onSuccess: (data) => {
      setConfirm(null);
      saved(data);
    },
    onError: failed,
  });
  const actions = {
    password: newPassword,
    totp: resetTotp,
    deactivate: access,
  };
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const name = fullName(account);
  const when = (value: string | null | undefined) =>
    value ? formatDateTime(value, i18n.language, timeZone) : t("console.accounts.never");
  const errors = form.formState.errors;

  return (
    <>
      <PageHeader
        title={name}
        subtitle={formatPhone(account.phone)}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AccountPills account={account} />
          </div>
        }
      />
      {locked && <Banner tone="info">{t("console.accounts.platformBanner")}</Banner>}
      {!account.is_active && <Banner tone="due">{t("console.accounts.inactiveBanner")}</Banner>}
      {general && <Banner tone="due">{general}</Banner>}
      {save.isSuccess && !form.formState.isDirty && (
        <Banner tone="ok" role="status">
          {t("console.accounts.saved")}
        </Banner>
      )}
      {password && (
        <Banner tone="warn">
          <p>{t("console.accounts.temporaryPassword", { name })}</p>
          <Code className="mt-2 inline-block text-lg">{password}</Code>
          <p className="mt-2 text-sm">{t("console.accounts.temporaryPasswordOnce")}</p>
        </Banner>
      )}
      <div className="grid items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <form
            noValidate
            onSubmit={form.handleSubmit((values) => {
              setGeneral(null);
              save.reset();
              save.mutate(values);
            })}
          >
            <Card>
              <CardHeader>
                <CardTitle>{t("console.accounts.identityTitle")}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
                {FIELDS.map((field) => (
                  <Field
                    key={field}
                    id={`account-${field}`}
                    label={t(`console.accounts.fields.${field}`)}
                    help={field === "phone" ? t("console.accounts.phoneHelp") : undefined}
                    error={errors[field]?.message}
                  >
                    {(control) => (
                      <Input
                        {...control}
                        disabled={locked}
                        inputMode={field === "phone" ? "tel" : undefined}
                        maxLength={field === "phone" ? 20 : 100}
                        {...form.register(field)}
                      />
                    )}
                  </Field>
                ))}
              </CardContent>
              {!locked && (
                <CardFooter>
                  <Button type="submit" disabled={save.isPending}>
                    {t("console.schools.save")}
                  </Button>
                </CardFooter>
              )}
            </Card>
          </form>
          {!locked && (
            <Card>
              <CardHeader>
                <CardTitle>{t("console.accounts.accessTitle")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>{t("console.accounts.forgotten")}</span>
                  {staff ? (
                    <Button variant="outline" size="sm" onClick={() => setConfirm("password")}>
                      {t("console.accounts.givePassword")}
                    </Button>
                  ) : (
                    <span className="text-sm text-ink-3">{t("console.accounts.portalOnly")}</span>
                  )}
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    {t("console.accounts.totp")}
                    {account.totp_enabled ? (
                      <StatusPill tone="ok">{t("console.accounts.totpOn")}</StatusPill>
                    ) : (
                      <StatusPill>{t("console.accounts.totpOff")}</StatusPill>
                    )}
                  </span>
                  {account.totp_enabled && (
                    <Button variant="outline" size="sm" onClick={() => setConfirm("totp")}>
                      {t("console.accounts.resetTotp")}
                    </Button>
                  )}
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>
                    {account.is_active
                      ? t("console.accounts.activeEverywhere")
                      : t("console.accounts.inactive")}
                  </span>
                  {account.is_active ? (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setConfirm("deactivate")}
                    >
                      {t("console.accounts.deactivate")}
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={access.isPending}
                      onClick={() => access.mutate()}
                    >
                      {t("console.accounts.reactivate")}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("console.accounts.schools")}</CardTitle>
            </CardHeader>
            {account.memberships.length === 0 && (
              <CardContent className="text-[.9rem] text-ink-3">
                {t("console.accounts.noSchool")}
              </CardContent>
            )}
            <ul className="m-0 list-none p-0">
              {account.memberships.map((membership) => (
                <li
                  key={membership.id}
                  className="flex flex-col gap-0.5 border-t border-line px-4 py-2.5 text-[.9rem] first:border-t-0"
                >
                  <span>
                    <b>{membership.school.name}</b>
                    {membership.roles.length > 0 && ` · ${membership.roles.join(", ")}`}
                    {!membership.is_active && (
                      <StatusPill tone="due" className="ml-2">
                        {t("console.accounts.inactiveHere")}
                      </StatusPill>
                    )}
                  </span>
                  <span className="text-[.82rem] text-ink-3">
                    {t("console.accounts.lastLoginAt", { date: when(membership.last_login_at) })}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.accounts.familiesTitle")}</CardTitle>
            </CardHeader>
            {account.families.length === 0 && (
              <CardContent className="text-[.9rem] text-ink-3">
                {t("console.accounts.noFamily")}
              </CardContent>
            )}
            <ul className="m-0 list-none p-0">
              {account.families.map((family) => (
                <li
                  key={family.id}
                  className="flex flex-col gap-0.5 border-t border-line px-4 py-2.5 text-[.9rem] first:border-t-0"
                >
                  <span>
                    <b>{family.school.name}</b> · {t("console.accounts.family")}{" "}
                    <Code>{family.code}</Code>
                    {family.portal_suspended_at && (
                      <StatusPill tone="due" className="ml-2">
                        {t("console.accounts.portalSuspended")}
                      </StatusPill>
                    )}
                  </span>
                  {family.activated_at && (
                    <span className="text-[.82rem] text-ink-3">
                      {t("console.accounts.activatedOn", {
                        date: formatDay(family.activated_at.slice(0, 10), i18n.language),
                      })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          <History
            changes={account.history}
            details={(change) =>
              change.action === "account.changed" && (
                <Differences
                  change={change}
                  label={(field) =>
                    SHOWN.has(field)
                      ? t(`console.accounts.fields.${field as (typeof FIELDS)[number]}`)
                      : null
                  }
                  shown={(field, value) => (field === "phone" ? formatPhone(value) : value)}
                />
              )
            }
          />
        </div>
      </div>
      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={confirm ? t(`console.accounts.confirm.${confirm}.title`, { name }) : ""}
        confirmLabel={confirm ? t(`console.accounts.confirm.${confirm}.action`) : ""}
        cancelLabel={t("common.cancel")}
        onConfirm={() => confirm && actions[confirm].mutate()}
        pending={confirm ? actions[confirm].isPending : false}
        destructive={confirm === "deactivate"}
      >
        {confirm && t(`console.accounts.confirm.${confirm}.text`)}
      </ConfirmDialog>
    </>
  );
}
