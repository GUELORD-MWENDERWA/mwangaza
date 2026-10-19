// Bandeau d'annonce du site (SITE.1a, maquette `console/site`, onglet « Bandeau ») : texte en
// français et en anglais, lien facultatif, dates facultatives, affiché ou caché ; l'état
// (affiché, programmé, terminé, caché) vient du serveur. Aperçu : le bandeau sur l'en-tête du site.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Brand,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Field,
  Icon,
  Input,
  Skeleton,
  StatusPill,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";

type SiteBanner = Schemas["ConsoleSiteBanner"];
type Values = {
  text_fr: string;
  text_en: string;
  link: string;
  starts_on: string;
  ends_on: string;
  active: boolean;
};
const TONES = { shown: "ok", scheduled: "info", ended: "gray", hidden: "gray" } as const;

export function BannerPanel() {
  const { t } = useTranslation();
  const banner = useQuery({
    queryKey: keys.siteBanner,
    queryFn: () => call(api.GET("/api/console/site/banner/")),
  });
  if (banner.isPending) return <Skeleton label={t("common.loading")} />;
  if (banner.isError) return <Banner tone="due">{errorMessage(banner.error, t)}</Banner>;
  return <BannerForm banner={banner.data} />;
}

function BannerForm({ banner }: { banner: SiteBanner }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const schema = z.object({
    text_fr: z.string().trim().max(160),
    text_en: z.string().trim().max(160),
    link: z.string().trim().max(300),
    starts_on: z.string(),
    ends_on: z.string(),
    active: z.boolean(),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      ...banner,
      starts_on: banner.starts_on ?? "",
      ends_on: banner.ends_on ?? "",
    },
  });
  const [general, setGeneral] = useState<string | null>(null);
  const errors = form.formState.errors;
  const save = useMutation({
    mutationFn: (values: Values) =>
      call(
        api.PATCH("/api/console/site/banner/", {
          body: { ...values, starts_on: values.starts_on || null, ends_on: values.ends_on || null },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(keys.siteBanner, data),
    onError: (error) =>
      setGeneral(
        applyServerErrors(
          error,
          ["text_fr", "text_en", "link", "starts_on", "ends_on", "active"],
          form.setError,
          t,
        ),
      ),
  });
  const onSubmit = form.handleSubmit((values) => {
    setGeneral(null);
    save.reset();
    save.mutate(values);
  });
  const day = (value: string | null) => formatDay(value ?? "", i18n.language);
  const state =
    banner.state === "scheduled"
      ? t("console.site.banner.states.scheduled", { from: day(banner.starts_on) })
      : banner.state === "shown" && banner.ends_on
        ? t("console.site.banner.states.shownUntil", { until: day(banner.ends_on) })
        : t(`console.site.banner.states.${banner.state}`);
  const preview = useWatch({ control: form.control });

  return (
    <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader className="flex-wrap gap-2">
          <CardTitle>{t("console.site.banner.title")}</CardTitle>
          <StatusPill tone={TONES[banner.state]}>{state}</StatusPill>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => void onSubmit(event)}
            noValidate
          >
            {save.isSuccess && <Banner tone="ok">{t("console.site.saved")}</Banner>}
            {general && <Banner tone="due">{general}</Banner>}
            <Field
              id="banner-fr"
              label={t("console.site.banner.textFr")}
              error={errors.text_fr?.message}
            >
              {(control) => <Input {...control} maxLength={160} {...form.register("text_fr")} />}
            </Field>
            <Field
              id="banner-en"
              label={t("console.site.banner.textEn")}
              error={errors.text_en?.message}
            >
              {(control) => <Input {...control} maxLength={160} {...form.register("text_en")} />}
            </Field>
            <Field
              id="banner-link"
              label={t("console.site.banner.link")}
              help={t("console.site.banner.linkHint")}
              error={errors.link?.message}
            >
              {(control) => <Input {...control} maxLength={300} {...form.register("link")} />}
            </Field>
            <div className="grid grid-cols-2 gap-3.5">
              <Field
                id="banner-from"
                label={t("console.site.banner.from")}
                error={errors.starts_on?.message}
              >
                {(control) => <Input {...control} type="date" {...form.register("starts_on")} />}
              </Field>
              <Field
                id="banner-until"
                label={t("console.site.banner.until")}
                error={errors.ends_on?.message}
              >
                {(control) => <Input {...control} type="date" {...form.register("ends_on")} />}
              </Field>
            </div>
            <CheckboxField
              id="banner-active"
              checked={preview.active}
              onCheckedChange={(checked) => form.setValue("active", checked === true)}
              label={
                <>
                  <b>{t("console.site.banner.active")}</b>
                  <span className="block text-sm text-ink-3">
                    {t("console.site.banner.activeHint")}
                  </span>
                </>
              }
            />
            <Button type="submit" className="self-end" disabled={save.isPending}>
              {t("console.site.save")}
            </Button>
          </form>
        </CardContent>
      </Card>
      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>{t("console.site.preview")}</CardTitle>
        </CardHeader>
        <p className="bg-lamp px-4 py-2.5 text-center text-sm font-semibold text-night">
          {preview.text_fr || t("console.site.banner.textFr")}
          {preview.link && (
            <span className="ml-1.5 inline-flex items-center gap-1 whitespace-nowrap underline underline-offset-3">
              {t("console.site.banner.more")}
              <Icon name="chevron" />
            </span>
          )}
        </p>
        <div className="bg-night px-4 py-3 text-night-ink">
          <Brand />
        </div>
        <CardContent>
          <p className="text-sm text-ink-3">{t("console.site.banner.previewHint")}</p>
        </CardContent>
      </Card>
    </div>
  );
}
