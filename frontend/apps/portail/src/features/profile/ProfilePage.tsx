import { api, call, ensureCsrf, type Schemas } from "@mwangaza/api";
import {
  applyServerErrors,
  changeLanguage,
  errorMessage,
  formatPhone,
  type Language,
  LANGUAGES,
  useTranslation,
} from "@mwangaza/i18n";
import {
  Avatar,
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  List,
  Segmented,
  Skeleton,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm, type Path } from "react-hook-form";
import { Link, useOutletContext } from "react-router";
import { z } from "zod";

import type { Account } from "../../lib/account";
import { PortalFrame, useLogout } from "../home/PortalFrame";

type Profile = Schemas["PortalProfile"];

const profileKey = ["portal", "profile"] as const;
const ADDRESS_PARTS = ["commune", "quartier", "avenue", "number"] as const;
const FIELDS = [
  ...ADDRESS_PARTS.map((part) => `address.${part}` as const),
  "email",
  "emergency_contact.full_name",
  "emergency_contact.phone",
] as const;

/** « Mon profil » (maquette `profil`, H5) : le compte, les coordonnées envoyées aux écoles des
 *  enfants (chacune les reporte dans sa propre fiche), la langue et la déconnexion. Le numéro du
 *  compte ne change pas ici ; notifications et code PIN : V1.1. */
export function ProfilePage() {
  const { t, i18n } = useTranslation();
  const account = useOutletContext<Account>();
  const profile = useQuery({
    queryKey: profileKey,
    queryFn: () => call(api.GET("/api/portal/profile/")),
  });
  const logout = useLogout();
  const letters = account.name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word.charAt(0))
    .join("")
    .toUpperCase();

  return (
    <PortalFrame heading={t("portal.profile.title")}>
      <Card>
        <CardContent className="flex items-center gap-3.5">
          <Avatar text={letters} className="size-14 text-lg" />
          <div className="min-w-0">
            <b className="block truncate">{account.name}</b>
            <span className="text-sm text-ink-3">
              {t("portal.profile.account", { phone: formatPhone(account.phone) })}
            </span>
          </div>
        </CardContent>
      </Card>
      {profile.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : profile.isError ? (
        <Banner tone="due">{t("portal.profile.loadError")}</Banner>
      ) : (
        <ContactCard profile={profile.data} />
      )}
      <Card>
        <CardContent>
          <List>
            <div>
              <span>{t("common.language")}</span>
              <Segmented
                label={t("common.language")}
                value={i18n.language as Language}
                options={LANGUAGES.map((value) => ({ value, label: value.toUpperCase() }))}
                onValueChange={(value) => void changeLanguage(value)}
              />
            </div>
            <Link to="/guide" className="text-ink no-underline">
              {t("portal.profile.guide")}
              <Icon name="chevron" size={20} className="text-ink-2" />
            </Link>
            <button
              type="button"
              className="w-full cursor-pointer text-left text-due disabled:opacity-60"
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              {t("portal.home.logout")}
              <Icon name="logout" size={20} className="text-ink-2" />
            </button>
          </List>
          {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
        </CardContent>
      </Card>
    </PortalFrame>
  );
}

function ContactCard({ profile }: { profile: Profile }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(
    () =>
      z.object({
        address: z.object({
          commune: z.string().trim().max(80),
          quartier: z.string().trim().max(80),
          avenue: z.string().trim().max(120),
          number: z.string().trim().max(20),
        }),
        email: z.union([z.literal(""), z.email(t("validation.emailInvalid"))]),
        emergency_contact: z
          .object({ full_name: z.string().trim().max(150), phone: z.string().trim() })
          .superRefine(({ full_name, phone }, context) => {
            if (!full_name !== !phone) {
              context.addIssue({
                code: "custom",
                path: [full_name ? "phone" : "full_name"],
                message: t("portal.profile.emergencyIncomplete"),
              });
            }
          }),
      }),
    [t],
  );
  type Values = z.infer<typeof schema>;
  const values = (data: Profile): Values => ({
    address: data.address as Values["address"],
    email: data.email,
    emergency_contact: data.emergency_contact as Values["emergency_contact"],
  });
  const form = useForm({ resolver: zodResolver(schema), defaultValues: values(profile) });
  const save = useMutation({
    mutationFn: async (body: Values) => {
      await ensureCsrf();
      return call(api.POST("/api/portal/profile/", { body }));
    },
    onMutate: () => setGeneral(null),
    onSuccess: (data) => {
      queryClient.setQueryData(profileKey, data);
      form.reset(values(data));
    },
    onError: (error) =>
      setGeneral(applyServerErrors(error, FIELDS as unknown as Path<Values>[], form.setError, t)),
  });
  const errors = form.formState.errors;
  const pending = profile.pending_schools;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("portal.profile.contact")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((data) => save.mutate(data))}
        >
          {general && <Banner tone="due">{general}</Banner>}
          {pending.length > 0 ? (
            <Banner tone="info">
              {t("portal.profile.pending", { schools: pending.join(", ") })}
            </Banner>
          ) : (
            save.isSuccess && <Banner tone="ok">{t("portal.profile.upToDate")}</Banner>
          )}
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-2 font-bold">{t("portal.profile.address")}</legend>
            <div className="grid grid-cols-2 gap-3">
              {ADDRESS_PARTS.map((part) => (
                <Field
                  key={part}
                  id={`address-${part}`}
                  label={t(`portal.profile.addressParts.${part}`)}
                  error={errors.address?.[part]?.message}
                >
                  {(control) => <Input {...control} {...form.register(`address.${part}`)} />}
                </Field>
              ))}
            </div>
          </fieldset>
          <Field id="email" label={t("portal.profile.email")} error={errors.email?.message}>
            {(control) => (
              <Input
                {...control}
                type="email"
                placeholder={t("portal.profile.optional")}
                {...form.register("email")}
              />
            )}
          </Field>
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-2 font-bold">{t("portal.profile.emergency")}</legend>
            <Field
              id="emergency-name"
              label={t("portal.profile.emergencyName")}
              error={errors.emergency_contact?.full_name?.message}
            >
              {(control) => (
                <Input {...control} {...form.register("emergency_contact.full_name")} />
              )}
            </Field>
            <Field
              id="emergency-phone"
              label={t("portal.profile.emergencyPhone")}
              error={errors.emergency_contact?.phone?.message}
            >
              {(control) => (
                <Input
                  {...control}
                  type="tel"
                  inputMode="tel"
                  placeholder={t("auth.login.phonePlaceholder")}
                  {...form.register("emergency_contact.phone")}
                />
              )}
            </Field>
          </fieldset>
          <Button type="submit" size="lg" disabled={save.isPending}>
            {t("portal.profile.save")}
          </Button>
          <p className="text-xs text-ink-3">{t("portal.profile.help")}</p>
        </form>
      </CardContent>
    </Card>
  );
}
