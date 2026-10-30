// Réseaux sociaux (SITE.5) : les mêmes champs que l'identité de la plateforme, tenus par la
// communication. Un lien vide n'apparaît pas sur le site.
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Skeleton,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { keys } from "../../lib/queries";

type Links = Schemas["ConsoleSocialLinks"];
const FIELDS = [
  "whatsapp_url",
  "facebook_url",
  "instagram_url",
  "linkedin_url",
  "youtube_url",
  "tiktok_url",
] as const;

export function SocialPanel() {
  const { t } = useTranslation();
  const links = useQuery({
    queryKey: keys.siteSocial,
    queryFn: () => call(api.GET("/api/console/site/social/")),
  });
  if (links.isPending) return <Skeleton label={t("common.loading")} />;
  if (links.isError) return <Banner tone="due">{errorMessage(links.error, t)}</Banner>;
  return <SocialForm links={links.data} />;
}

function SocialForm({ links }: { links: Links }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const form = useForm<Links>({ defaultValues: links });
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: (body: Links) => call(api.PATCH("/api/console/site/social/", { body })),
    onSuccess: (data) => {
      setSaved(true);
      form.reset(data);
      void queryClient.invalidateQueries({ queryKey: keys.siteSocial });
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  return (
    <Card className="mt-4">
      <CardHeader className="flex-wrap gap-3">
        <CardTitle>{t("console.site.social.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("console.site.social.hint")}</span>
      </CardHeader>
      <form
        onSubmit={(event) => {
          setGeneral(null);
          setSaved(false);
          void form.handleSubmit((values) => save.mutate(values))(event);
        }}
        noValidate
      >
        <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
          {saved && (
            <div className="min-[820px]:col-span-2">
              <Banner tone="ok">{t("console.site.saved")}</Banner>
            </div>
          )}
          {general && (
            <div className="min-[820px]:col-span-2">
              <Banner tone="due">{general}</Banner>
            </div>
          )}
          {FIELDS.map((field) => (
            <Field
              key={field}
              id={`social-${field}`}
              label={t(`console.identity.fields.${field}`)}
              error={form.formState.errors[field]?.message}
            >
              {(control) => <Input {...control} maxLength={200} {...form.register(field)} />}
            </Field>
          ))}
        </CardContent>
        <CardFooter className="flex-wrap justify-between gap-3">
          <span className="text-sm text-ink-3">{t("console.site.social.same")}</span>
          <Button type="submit" size="sm" disabled={save.isPending}>
            {t("console.site.save")}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
