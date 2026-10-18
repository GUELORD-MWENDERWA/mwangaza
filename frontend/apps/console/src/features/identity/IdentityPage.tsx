// Identité de la plateforme (5.2.2, maquette `console/identite-plateforme`) : nom, logo, icône,
// couleurs, support, mentions légales, et les dernières modifications (journal de la plateforme).
// Le serveur vérifie tout (super-admin, couleurs lisibles, fichiers) ; l'aperçu suit la saisie.
import { zodResolver } from "@hookform/resolvers/zod";
import { ApiError, api, call, type Schemas } from "@mwangaza/api";
import {
  applyServerErrors,
  errorMessage,
  fieldMessage,
  formatDateTime,
  type TFunction,
  useTranslation,
} from "@mwangaza/i18n";
import {
  Banner,
  BrandMark,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  cn,
  Field,
  Icon,
  Input,
  PageHeader,
  Skeleton,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type CSSProperties, Fragment, useMemo, useRef, useState } from "react";
import { Controller, useForm, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";

type Identity = Schemas["ConsolePlatform"];
type Change = Schemas["PlatformChange"];

// Réseaux de la plateforme (WEB.1d) : lien vide = caché sur le site ; domaine vérifié par le serveur.
const SOCIAL = [
  "whatsapp_url",
  "facebook_url",
  "instagram_url",
  "linkedin_url",
  "youtube_url",
  "tiktok_url",
] as const;

const FIELDS = [
  "name",
  "short_name",
  "site_name",
  "primary_color",
  "accent_color",
  "support_phone",
  "support_email",
  "legal_notice",
  "address",
  "city",
  "region",
  ...SOCIAL,
] as const;
const COLORS = ["primary_color", "accent_color"] as const;
const COLOR = /^#[0-9A-F]{6}$/i;

function useSchema() {
  const { t } = useTranslation();
  return useMemo(() => {
    const color = z.string().trim().regex(COLOR, t("validation.colorFormat"));
    const link = z.string().trim().max(200);
    return z.object({
      name: z.string().trim().min(1, t("validation.nameRequired")).max(60),
      short_name: z.string().trim().min(1, t("validation.nameRequired")).max(20),
      site_name: z.string().trim().min(1, t("validation.nameRequired")).max(60),
      primary_color: color,
      accent_color: color,
      support_phone: z.string().trim(),
      support_email: z.union([z.literal(""), z.email(t("validation.emailInvalid"))]),
      legal_notice: z.string().trim(),
      address: z.string().trim().max(120),
      city: z.string().trim().max(60),
      region: z.string().trim().max(60),
      whatsapp_url: link,
      facebook_url: link,
      instagram_url: link,
      linkedin_url: link,
      youtube_url: link,
      tiktok_url: link,
    });
  }, [t]);
}

type Values = z.infer<ReturnType<typeof useSchema>>;
type Form = UseFormReturn<Values>;

const valuesOf = (identity: Identity): Values => ({
  name: identity.name,
  short_name: identity.short_name,
  site_name: identity.site_name,
  primary_color: identity.primary_color,
  accent_color: identity.accent_color,
  support_phone: identity.support_phone,
  support_email: identity.support_email,
  legal_notice: identity.legal_notice,
  address: identity.address,
  city: identity.city,
  region: identity.region,
  whatsapp_url: identity.whatsapp_url,
  facebook_url: identity.facebook_url,
  instagram_url: identity.instagram_url,
  linkedin_url: identity.linkedin_url,
  youtube_url: identity.youtube_url,
  tiktok_url: identity.tiktok_url,
});

/** Après un changement : l'écran, et l'identité de toute la console (nom, couleurs, logo). */
function useSaved() {
  const queryClient = useQueryClient();
  return (data: Identity) => {
    queryClient.setQueryData(keys.identity, data);
    void queryClient.invalidateQueries({ queryKey: keys.platform });
  };
}

export function IdentityPage() {
  const { t } = useTranslation();
  const identity = useQuery({
    queryKey: keys.identity,
    queryFn: () => call(api.GET("/api/console/platform/")),
  });
  if (identity.isPending) return <Skeleton label={t("common.loading")} />;
  if (identity.isError) {
    return (
      <>
        <Banner tone="due">{errorMessage(identity.error, t)}</Banner>
        <Button variant="outline" className="w-fit" onClick={() => void identity.refetch()}>
          {t("common.retry")}
        </Button>
      </>
    );
  }
  return <IdentityForm identity={identity.data} />;
}

function IdentityForm({ identity }: { identity: Identity }) {
  const { t } = useTranslation();
  const saved = useSaved();
  const schema = useSchema();
  const [general, setGeneral] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: valuesOf(identity),
  });
  const save = useMutation({
    mutationFn: (body: Values) => call(api.PATCH("/api/console/platform/", { body })),
    onSuccess: (data) => {
      saved(data);
      form.reset(valuesOf(data));
    },
    onError: (error) => {
      setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t));
      // Couleur illisible : trop claire (principale) ou trop sombre (accent), pas les deux.
      for (const field of COLORS) {
        if (form.getFieldState(field).error?.message === fieldMessage("unreadable_color", t)) {
          form.setError(field, {
            type: "server",
            message: t(`console.identity.${field}.unreadable`),
          });
        }
      }
    },
  });
  const errors = form.formState.errors;
  const text = (field: (typeof FIELDS)[number], help?: string, maxLength?: number) => (
    <Field
      id={`identity-${field}`}
      label={t(`console.identity.fields.${field}`)}
      help={help}
      error={errors[field]?.message}
    >
      {(control) => <Input {...control} maxLength={maxLength} {...form.register(field)} />}
    </Field>
  );

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        save.reset();
        save.mutate(values);
      })}
    >
      <PageHeader
        title={t("console.identity.title")}
        subtitle={t("console.identity.subtitle")}
        actions={
          <Button type="submit" size="lg" disabled={save.isPending}>
            {t("console.identity.save")}
          </Button>
        }
      />
      {general && <Banner tone="due">{general}</Banner>}
      {save.isSuccess && !form.formState.isDirty && (
        <Banner tone="ok" role="status">
          {t("console.identity.saved")}
        </Banner>
      )}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("console.identity.nameTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              {text("name", t("console.identity.nameHelp"), 60)}
              {text("short_name", t("console.identity.shortNameHelp"), 20)}
              <div className="min-[820px]:col-span-2">
                {text("site_name", t("console.identity.siteNameHelp"), 60)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.identity.filesTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              <FileField identity={identity} kind="logo" />
              <FileField identity={identity} kind="icon" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.identity.colorsTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              {COLORS.map((field) => (
                <ColorField key={field} form={form} field={field} />
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.identity.supportTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              {text("support_phone", t("console.identity.phoneHelp"))}
              {text("support_email")}
              <Field
                id="identity-legal_notice"
                label={t("console.identity.fields.legal_notice")}
                help={t("console.identity.legalHelp")}
                error={errors.legal_notice?.message}
                className="min-[820px]:col-span-2"
              >
                {(control) => <Textarea {...control} rows={4} {...form.register("legal_notice")} />}
              </Field>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.identity.reachTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              <div className="min-[820px]:col-span-2">
                {text("address", t("console.identity.addressHelp"), 120)}
              </div>
              {text("city", undefined, 60)}
              {text("region", undefined, 60)}
              {SOCIAL.map((field) => (
                <Fragment key={field}>{text(field, undefined, 200)}</Fragment>
              ))}
              <p className="text-sm text-ink-3 min-[820px]:col-span-2">
                {t("console.identity.socialHelp")}
              </p>
            </CardContent>
          </Card>
        </div>
        <div className="flex flex-col gap-4">
          <Preview form={form} identity={identity} />
          <History changes={identity.history} />
        </div>
      </div>
    </form>
  );
}

function ColorField({ form, field }: { form: Form; field: (typeof COLORS)[number] }) {
  const { t } = useTranslation();
  const value = form.watch(field);
  return (
    <Field
      id={`identity-${field}`}
      label={t(`console.identity.fields.${field}`)}
      help={t(`console.identity.${field}.help`)}
      error={form.formState.errors[field]?.message}
    >
      {(control) => (
        <div className="flex items-center gap-2.5">
          <Controller
            control={form.control}
            name={field}
            render={({ field: picker }) => (
              <input
                type="color"
                aria-label={t("console.identity.picker")}
                value={COLOR.test(value) ? value : "#000000"}
                onChange={(event) => picker.onChange(event.target.value.toUpperCase())}
                className="h-10 w-12 shrink-0 cursor-pointer rounded-input border border-line bg-white p-1"
              />
            )}
          />
          <Input {...control} {...form.register(field)} className="font-mono" maxLength={7} />
        </div>
      )}
    </Field>
  );
}

/** Logo ou icône, enregistrés aussitôt choisis (envoi à part du formulaire). */
function FileField({ identity, kind }: { identity: Identity; kind: "logo" | "icon" }) {
  const { t } = useTranslation();
  const saved = useSaved();
  const input = useRef<HTMLInputElement>(null);
  const file = identity[kind];
  const upload = useMutation({
    mutationFn: (chosen: File) => {
      const body = new FormData();
      body.append(kind, chosen);
      return kind === "logo"
        ? call(api.POST("/api/console/platform/logo/", { body: body as never }))
        : call(api.POST("/api/console/platform/icon/", { body: body as never }));
    },
    onSuccess: saved,
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        kind === "logo"
          ? api.DELETE("/api/console/platform/logo/")
          : api.DELETE("/api/console/platform/icon/"),
      ),
    onSuccess: saved,
  });
  const failed = upload.error ?? remove.error;
  const [first] = failed instanceof ApiError ? (Object.values(failed.fields)[0] ?? []) : [];
  const error = first ? fieldMessage(first.code, t) : failed ? errorMessage(failed, t) : null;
  const icon = kind === "icon";
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-bold text-ink-2">{t(`console.identity.${kind}.label`)}</span>
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={
            icon
              ? cn(
                  "grid size-[84px] place-items-center overflow-hidden rounded-[20px]",
                  file && "bg-night-2",
                )
              : "grid size-[84px] place-items-center rounded-box border border-line bg-white p-1"
          }
        >
          {file ? (
            <img
              src={file}
              alt={t(`console.identity.${kind}.alt`)}
              className="size-full object-contain"
            />
          ) : (
            <BrandMark className={icon ? "size-[72px]" : "size-12"} />
          )}
        </span>
        <div className="flex flex-col items-start gap-1.5">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => input.current?.click()}
            >
              <Icon name="upload" size={14} />
              {t("console.identity.change")}
            </Button>
            {file && (
              <Button
                variant="ghost"
                size="sm"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                {t("console.identity.remove")}
              </Button>
            )}
          </div>
          <span className="text-xs text-ink-3">{t(`console.identity.${kind}.help`)}</span>
        </div>
        <input
          ref={input}
          type="file"
          accept={icon ? "image/png" : "image/png,image/jpeg,image/svg+xml"}
          className="hidden"
          aria-label={t(`console.identity.${kind}.change`)}
          onChange={(event) => {
            const chosen = event.target.files?.[0];
            event.target.value = "";
            if (chosen) upload.mutate(chosen);
          }}
        />
      </div>
      {error && (
        <p className="text-xs text-due" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/** Ce que verront les applications, avec les couleurs saisies (avant l'enregistrement). */
function Preview({ form, identity }: { form: Form; identity: Identity }) {
  const { t } = useTranslation();
  const [name, shortName, primary, accent] = form.watch([
    "name",
    "short_name",
    "primary_color",
    "accent_color",
  ]);
  const style = {
    ...(COLOR.test(primary) && { "--color-lake": primary }),
    ...(COLOR.test(accent) && { "--color-lamp": accent }),
  } as CSSProperties;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.identity.preview")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3" style={style}>
        <div className="flex items-center gap-2.5 rounded-box bg-night px-3.5 py-3 text-night-ink">
          {identity.logo ? (
            <img src={identity.logo} alt="" className="h-8 w-auto max-w-[120px] object-contain" />
          ) : (
            <BrandMark className="size-8" />
          )}
          <b className="truncate">{name}</b>
          <span className="ml-auto border-b-[3px] border-lamp pb-0.5 text-sm font-bold text-white">
            {t("console.identity.previewMenu")}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-input bg-lake px-4 py-2.5 text-sm font-bold text-white">
            {t("console.identity.previewButton")}
          </span>
          <span className="font-bold text-lake underline">{t("console.identity.previewLink")}</span>
        </div>
        <div className="flex items-end gap-4 rounded-box bg-linear-160 from-ink-2 to-night p-3.5">
          <span className="flex w-16 flex-col items-center gap-1.5 text-center text-xs text-white">
            <span className="grid size-14 place-items-center overflow-hidden rounded-[14px]">
              {identity.icon ? (
                <img src={identity.icon} alt="" className="size-full object-cover" />
              ) : (
                <BrandMark className="size-14" />
              )}
            </span>
            <span className="w-full truncate">{shortName}</span>
          </span>
          <span aria-hidden="true" className="mb-6 size-14 rounded-[14px] bg-white/20" />
          <span aria-hidden="true" className="mb-6 size-14 rounded-[14px] bg-white/20" />
        </div>
      </CardContent>
    </Card>
  );
}

function History({ changes }: { changes: Change[] }) {
  const { t, i18n } = useTranslation();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.identity.historyTitle")}</CardTitle>
      </CardHeader>
      {changes.length === 0 ? (
        <CardContent className="text-md text-ink-3">{t("console.identity.noChange")}</CardContent>
      ) : (
        <ul className="m-0 list-none p-0">
          {changes.map((change) => (
            <li
              key={change.id}
              className="flex flex-col gap-0.5 border-t border-line px-4 py-2.5 text-md first:border-t-0"
            >
              <b>{t(`console.actions.${change.action}`)}</b>
              <span className="text-sm text-ink-3">
                {formatDateTime(change.created_at, i18n.language, timeZone)}
                {change.actor &&
                  ` · ${[change.actor.first_name, change.actor.last_name].join(" ")}`}
              </span>
              {change.action === "platform.updated" && <Differences change={change} t={t} />}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Differences({ change, t }: { change: Change; t: TFunction }) {
  const before = (change.before ?? {}) as Record<string, string>;
  const after = (change.after ?? {}) as Record<string, string>;
  const shown = (value: string | undefined) => value || t("console.identity.empty");
  return (
    <>
      {Object.keys(after).map((field) => {
        const label = t(`console.identity.fields.${field as (typeof FIELDS)[number]}`);
        return (
          <span key={field} className="text-sm break-words">
            {/* Les mentions légales sont longues : seulement le fait qu'elles ont changé. */}
            {field === "legal_notice"
              ? label
              : t("console.identity.difference", {
                  field: label,
                  before: shown(before[field]),
                  after: shown(after[field]),
                })}
          </span>
        );
      })}
    </>
  );
}
