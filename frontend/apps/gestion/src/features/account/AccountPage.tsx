// Mon compte (M4) : identité (modifiée par l'école), langue, mot de passe, double
// authentification, code PIN de cet appareil (B5), appareils connectés, écoles du compte,
// déconnexion. Pas d'e-mail tant qu'il ne sert à rien (`04`).
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDate, formatVisit, LANGUAGES, type Language, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  List,
  PageHeader,
  PasswordInput,
  Segmented,
  Skeleton,
  StatusPill,
  Tag,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { localDevice } from "../../lib/device";
import { applyServerErrors, errorMessage } from "../../lib/errors";
import { rolesLabel } from "../../lib/people";
import { PIN_LENGTH, setPin, weakPin } from "../../lib/pin";
import { hasCode, keys, useCurrentMe, type Me } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useLogout } from "../../lib/session";
import { passwordSchema } from "../auth/NewPasswordPage";
import { SignatureField } from "../settings/SignatureField";
import { DisableTwoFactorDialog, NewRecoveryCodesDialog } from "./TwoFactorDialogs";

type Device = Schemas["Device"];

/** Alerte quand il reste 2 codes de secours ou moins (M4). */
export const LOW_RECOVERY_CODES = 2;

export function AccountPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const logout = useLogout();
  return (
    <>
      <PageHeader title={t("account.title")} subtitle={t("account.subtitle")} />
      <div className="grid items-start gap-4 min-[1280px]:grid-cols-2">
        <div className="flex flex-col gap-4">
          <IdentityCard me={me} />
          {me.school && !me.support && <SignatureCard signature={me.school.documents.signature} />}
          <PasswordCard />
          <DevicesCard />
        </div>
        <div className="flex flex-col gap-4">
          <TwoFactorCard me={me} />
          <PinCard me={me} />
          <SchoolsCard me={me} />
          {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
          <Button
            variant="destructive-outline"
            size="lg"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            <Icon name="logout" />
            {t("common.logout")}
          </Button>
        </div>
      </div>
    </>
  );
}

/** Ma signature dans cette école (DOC.1) : posée sur les reçus, convocations et bordereaux que
 *  je donne ; sans elle, je signe à la main. Au journal de l'école. */
function SignatureCard({ signature }: { signature: string | null }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("account.signature.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <SignatureField
          label={t("account.signature.label")}
          help={t("account.signature.help")}
          image={signature}
          send={(body) =>
            call(api.POST("/api/me/signature/", { body: body as unknown as { image: string } }))
          }
          remove={() => call(api.DELETE("/api/me/signature/"))}
          onSaved={(data) => queryClient.setQueryData(keys.me, data)}
        />
      </CardContent>
    </Card>
  );
}

function IdentityCard({ me }: { me: Me }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (language: Language) => call(api.PATCH("/api/me/", { body: { language } })),
    onSuccess: (data) => queryClient.setQueryData(keys.me, data),
  });
  const language = save.isPending ? save.variables : me.language;
  const readOnly = "bg-surface";
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("account.identity.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 min-[600px]:grid-cols-3">
        <Field id="last-name" label={t("account.identity.lastName")}>
          {(control) => <Input {...control} value={me.last_name} readOnly className={readOnly} />}
        </Field>
        <Field id="middle-name" label={t("account.identity.middleName")}>
          {(control) => <Input {...control} value={me.middle_name} readOnly className={readOnly} />}
        </Field>
        <Field id="first-name" label={t("account.identity.firstName")}>
          {(control) => <Input {...control} value={me.first_name} readOnly className={readOnly} />}
        </Field>
        <Field
          id="phone"
          label={t("account.identity.phone")}
          help={t("account.identity.phoneHelp")}
          className="min-[600px]:col-span-2"
        >
          {(control) => <Input {...control} value={me.phone} readOnly className={readOnly} />}
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-bold text-ink-2">{t("common.language")}</span>
          <Segmented
            label={t("common.language")}
            value={language}
            options={LANGUAGES.map((value) => ({
              value,
              label: t(`common.languages.${value}`),
            }))}
            onValueChange={(value) => save.mutate(value)}
            disabled={save.isPending}
            className="w-fit"
          />
          <p role="status" className="text-xs text-ink-3">
            {save.isSuccess && t("account.identity.languageSaved")}
          </p>
        </div>
        {save.isError && (
          <Banner tone="due" className="min-[600px]:col-span-3">
            {errorMessage(save.error, t)}
          </Banner>
        )}
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const { t } = useTranslation();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(
    () =>
      z
        .object({ current_password: z.string().min(1, t("validation.passwordRequired")) })
        .and(passwordSchema(t)),
    [t],
  );
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const save = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      call(
        api.POST("/api/auth/password/", {
          body: { current_password: values.current_password, new_password: values.new_password },
        }),
      ),
    onSuccess: () => form.reset(),
    onError: (error) => {
      if (hasCode(error, "wrong_password")) {
        form.setError("current_password", { message: errorMessage(error, t) });
        setGeneral(null);
        return;
      }
      setGeneral(applyServerErrors(error, ["current_password", "new_password"], form.setError, t));
    },
  });
  const { errors } = form.formState;
  const passwordProps = {
    showLabel: t("common.showPassword"),
    hideLabel: t("common.hidePassword"),
  };

  return (
    <Card>
      <form
        noValidate
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          save.reset();
          save.mutate(values);
        })}
      >
        <CardHeader>
          <CardTitle>{t("account.password.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {general && <Banner tone="due">{general}</Banner>}
          {save.isSuccess && <Banner tone="ok">{t("account.password.done")}</Banner>}
          <div className="grid items-start gap-3 min-[600px]:grid-cols-3">
            <Field
              id="current-password"
              label={t("account.password.current")}
              error={errors.current_password?.message}
            >
              {(control) => (
                <PasswordInput
                  {...control}
                  {...form.register("current_password")}
                  {...passwordProps}
                  autoComplete="current-password"
                />
              )}
            </Field>
            <Field
              id="account-new-password"
              label={t("account.password.new")}
              help={t("account.password.help")}
              error={errors.new_password?.message}
            >
              {(control) => (
                <PasswordInput
                  {...control}
                  {...form.register("new_password")}
                  {...passwordProps}
                  autoComplete="new-password"
                />
              )}
            </Field>
            <Field
              id="account-confirm-password"
              label={t("account.password.confirm")}
              error={errors.confirm?.message}
            >
              {(control) => (
                <PasswordInput
                  {...control}
                  {...form.register("confirm")}
                  {...passwordProps}
                  autoComplete="new-password"
                  placeholder={t("account.password.confirmPlaceholder")}
                />
              )}
            </Field>
          </div>
        </CardContent>
        <CardFooter>
          <span className="text-sm text-ink-3">{t("account.password.note")}</span>
          <Button type="submit" variant="outline" disabled={save.isPending}>
            {t("account.password.submit")}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

/** Code PIN de déverrouillage (B5) : propre à cet appareil mémorisé, jamais envoyé au serveur. */
function PinCard({ me }: { me: Me }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const device = useQuery({
    queryKey: [...keys.localDevice, me.id],
    queryFn: async () => (await localDevice(me.id)) ?? null,
    retry: false,
  });
  const schema = useMemo(
    () =>
      z
        .object({
          pin: z.string().refine((pin) => !weakPin(pin), t("account.pin.weak")),
          confirm: z.string(),
        })
        .refine((values) => values.pin === values.confirm, {
          message: t("account.pin.mismatch"),
          path: ["confirm"],
        }),
    [t],
  );
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { pin: "", confirm: "" } });
  const save = useMutation({
    mutationFn: (values: z.infer<typeof schema>) => setPin(me.id, values.pin),
    onSuccess: () => {
      form.reset();
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: keys.localDevice });
    },
  });
  const { errors } = form.formState;
  const defined = !!device.data?.pin;
  const pinProps = {
    type: "password",
    inputMode: "numeric",
    autoComplete: "off",
    maxLength: PIN_LENGTH,
    className: "max-w-[8rem] tracking-[.3em]",
  } as const;

  return (
    <Card>
      <form
        noValidate
        onSubmit={form.handleSubmit((values) => {
          save.reset();
          save.mutate(values);
        })}
      >
        <CardHeader>
          <CardTitle>{t("account.pin.title")}</CardTitle>
          {device.data && (
            <StatusPill tone={defined ? "ok" : "warn"}>
              {t(defined ? "account.pin.defined" : "account.pin.undefined")}
            </StatusPill>
          )}
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {device.isPending ? (
            <Skeleton label={t("common.loading")} />
          ) : !device.data ? (
            <p className="text-sm text-ink-3">{t("account.pin.noDevice")}</p>
          ) : (
            <>
              <p className="text-sm">{t("account.pin.text")}</p>
              {save.isSuccess && <Banner tone="ok">{t("account.pin.done")}</Banner>}
              {save.isError && <Banner tone="due">{t("account.pin.failed")}</Banner>}
              {editing && (
                <div className="grid items-start gap-3 min-[600px]:grid-cols-2">
                  <Field
                    id="account-pin"
                    label={t("account.pin.new")}
                    help={t("account.pin.help")}
                    error={errors.pin?.message}
                  >
                    {(control) => <Input {...control} {...form.register("pin")} {...pinProps} />}
                  </Field>
                  <Field
                    id="account-pin-confirm"
                    label={t("account.pin.confirm")}
                    error={errors.confirm?.message}
                  >
                    {(control) => (
                      <Input {...control} {...form.register("confirm")} {...pinProps} />
                    )}
                  </Field>
                </div>
              )}
            </>
          )}
        </CardContent>
        {device.data && (
          <CardFooter>
            <span className="text-sm text-ink-3">{t("account.pin.thisDevice")}</span>
            {editing ? (
              <Button type="submit" variant="outline" size="sm" disabled={save.isPending}>
                {t("common.save")}
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  save.reset();
                  setEditing(true);
                }}
              >
                {t(defined ? "account.pin.change" : "account.pin.set")}
              </Button>
            )}
          </CardFooter>
        )}
      </form>
    </Card>
  );
}

function TwoFactorCard({ me }: { me: Me }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [disabled, setDisabled] = useState(false);
  const low = me.recovery_codes_left <= LOW_RECOVERY_CODES;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("account.twoFactor.title")}</CardTitle>
        <StatusPill tone={me.totp_enabled ? "ok" : "gray"}>
          {me.totp_enabled ? t("account.twoFactor.on") : t("account.twoFactor.off")}
        </StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {disabled && !me.totp_enabled && (
          <Banner tone="ok">{t("account.twoFactor.disabled")}</Banner>
        )}
        {me.totp_enabled ? (
          <>
            <List>
              {me.totp_enabled_at && (
                <div>
                  <span>{t("account.twoFactor.since")}</span>
                  <b className="num">
                    {formatDate(me.totp_enabled_at, i18n.language, school.timezone)}
                  </b>
                </div>
              )}
              <div>
                <span>{t("account.twoFactor.codesLeft")}</span>
                <b className={low ? "num text-warn" : "num"}>
                  {t("account.twoFactor.codesLeftValue", { count: me.recovery_codes_left })}
                </b>
              </div>
            </List>
            {low && <Banner tone="warn">{t("account.twoFactor.lowCodes")}</Banner>}
          </>
        ) : (
          <p className="text-sm">{t("account.twoFactor.offText")}</p>
        )}
        {me.totp_required && (
          <p className="text-sm text-ink-3">{t("account.twoFactor.required")}</p>
        )}
      </CardContent>
      <CardFooter>
        {me.totp_enabled ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to="/account/two-factor">{t("account.twoFactor.changePhone")}</Link>
              </Button>
              {!me.totp_required && <DisableTwoFactorDialog onDone={() => setDisabled(true)} />}
            </div>
            <NewRecoveryCodesDialog phone={me.phone} />
          </>
        ) : (
          <Button asChild size="sm" className="ml-auto">
            <Link to="/account/two-factor">{t("account.twoFactor.activate")}</Link>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

/** Appareils mémorisés du compte dans cette école (M4) ; « Déconnecter » ferme leur session. */
function DevicesCard() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [target, setTarget] = useState<Device | null>(null);
  const devices = useQuery({
    queryKey: keys.myDevices,
    queryFn: () => call(api.GET("/api/me/devices/")),
  });
  const revoke = useMutation({
    mutationFn: (device: Device) =>
      call(api.POST("/api/me/devices/{id}/revoke/", { params: { path: { id: device.id } } })),
    onSuccess: () => {
      setTarget(null);
      void queryClient.invalidateQueries({ queryKey: keys.myDevices });
    },
  });
  const list = devices.data?.results ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("account.devices.title")}</CardTitle>
      </CardHeader>
      <CardContent className="py-1">
        {devices.isPending ? (
          <div className="py-3">
            <Skeleton label={t("common.loading")} />
          </div>
        ) : devices.isError ? (
          <Banner tone="due" className="my-3">
            {errorMessage(devices.error, t)}
          </Banner>
        ) : list.length === 0 ? (
          <p className="py-3 text-sm text-ink-3">{t("account.devices.empty")}</p>
        ) : (
          <List>
            {list.map((device) => (
              <div key={device.id}>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Tag>{device.prefix}</Tag>
                    <b>{device.label}</b>
                    {device.is_current && (
                      <StatusPill tone="info">{t("account.devices.current")}</StatusPill>
                    )}
                  </div>
                  {device.last_seen_at && (
                    <span className="text-sm text-ink-3">
                      {formatVisit(device.last_seen_at, i18n.language, school.timezone, (time) =>
                        t("common.today", { time }),
                      )}
                    </span>
                  )}
                </div>
                {!device.is_current && (
                  <Button variant="destructive-outline" size="sm" onClick={() => setTarget(device)}>
                    {t("account.devices.disconnect")}
                  </Button>
                )}
              </div>
            ))}
          </List>
        )}
      </CardContent>
      <ConfirmDialog
        open={target !== null}
        onOpenChange={(open) => !open && setTarget(null)}
        title={t("account.devices.confirmTitle", { label: target?.label })}
        confirmLabel={t("account.devices.disconnect")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => target && revoke.mutate(target)}
        pending={revoke.isPending}
      >
        <p className="text-sm text-ink-2">{t("account.devices.confirmText")}</p>
        {revoke.isError && <Banner tone="due">{errorMessage(revoke.error, t)}</Banner>}
      </ConfirmDialog>
    </Card>
  );
}

function SchoolsCard({ me }: { me: Me }) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("account.schools.title")}</CardTitle>
      </CardHeader>
      <CardContent className="py-1">
        <List>
          {me.schools.map((item) => (
            <div key={item.code}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <b>{item.name}</b>
                  {item.code === school.code ? (
                    <StatusPill tone="info">{t("account.schools.current")}</StatusPill>
                  ) : (
                    item.status === "suspended" && (
                      <StatusPill tone="gray">{t("schools.suspended")}</StatusPill>
                    )
                  )}
                </div>
                <span className="text-sm text-ink-3">{rolesLabel(item.roles, t)}</span>
              </div>
              {item.code !== school.code && item.status !== "suspended" && (
                <Button asChild variant="ghost" size="sm">
                  <a href={`${item.url}/app/`}>
                    {t("account.schools.open")}
                    <Icon name="chevron" size={16} />
                  </a>
                </Button>
              )}
            </div>
          ))}
        </List>
      </CardContent>
    </Card>
  );
}
