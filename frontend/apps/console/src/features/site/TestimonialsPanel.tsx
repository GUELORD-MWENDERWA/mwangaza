// Témoignages du site (SITE.1b, maquette `console/site-contenus`) : les mots d'une personne, avec
// l'accord écrit déposé (privé). Le serveur refuse « Publié » sans lui.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  Skeleton,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { FilePicker, PhotoPicker, RankedList } from "./shared";

type Testimonial = Schemas["ConsoleTestimonial"];
type Values = {
  name: string;
  role: string;
  school_name: string;
  town: string;
  quote_fr: string;
  quote_en: string;
  published: boolean;
};

const MAX = 6; // comme le serveur (`Testimonial.MAX`)
const EMPTY: Values = {
  name: "",
  role: "",
  school_name: "",
  town: "",
  quote_fr: "",
  quote_en: "",
  published: false,
};
const FIELDS = Object.keys(EMPTY) as (keyof Values)[];

export function TestimonialsPanel() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Testimonial | null>(null);
  const list = useQuery({
    queryKey: keys.siteTestimonials,
    queryFn: () => call(api.GET("/api/console/site/testimonials/")),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.siteTestimonials });
  const move = useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: "up" | "down" }) =>
      call(
        api.POST("/api/console/site/testimonials/{id}/move/", {
          params: { path: { id } },
          body: { direction },
        }),
      ),
    onSuccess: refresh,
  });
  if (list.isPending) return <Skeleton label={t("common.loading")} />;
  if (list.isError) return <Banner tone="due">{errorMessage(list.error, t)}</Banner>;
  const items = list.data;
  const selected = items.find((item) => item.id === editing?.id) ?? null;

  return (
    <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader className="flex-wrap gap-3">
          <CardTitle>{t("console.site.testimonials.title")}</CardTitle>
          <span className="text-sm text-ink-3">{t("console.site.testimonials.order")}</span>
        </CardHeader>
        {items.length === 0 ? (
          <CardContent>
            <p className="text-ink-3">{t("console.site.testimonials.empty")}</p>
          </CardContent>
        ) : (
          <RankedList
            label={t("console.site.testimonials.title")}
            rows={items.map((item) => ({
              id: item.id,
              title: `${item.role} · ${item.school_name}`,
              sub: `« ${item.quote_fr} »`,
              published: item.published,
              note: item.has_consent ? undefined : t("console.site.testimonials.noConsent"),
            }))}
            selected={selected?.id}
            onEdit={(id) => setEditing(items.find((item) => item.id === id) ?? null)}
            onMove={(id, direction) => move.mutate({ id, direction })}
            moving={move.isPending}
            error={move.error}
          />
        )}
        <CardFooter className="flex-wrap justify-between gap-3">
          <span className="text-sm text-ink-3">
            {t("console.site.testimonials.count", { count: items.length, max: MAX })}
          </span>
          <Button size="sm" disabled={items.length >= MAX} onClick={() => setEditing(null)}>
            <Icon name="plus" /> {t("console.site.testimonials.add")}
          </Button>
        </CardFooter>
      </Card>
      <TestimonialEditor
        key={selected?.id ?? "new"}
        item={selected}
        onChanged={refresh}
        onDone={() => setEditing(null)}
      />
    </div>
  );
}

function TestimonialEditor({
  item,
  onChanged,
  onDone,
}: {
  item: Testimonial | null;
  onChanged: () => void;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation();
  const required = t("fieldErrors.required");
  const schema = z.object({
    name: z.string().trim().min(1, required).max(80),
    role: z.string().trim().min(1, required).max(80),
    school_name: z.string().trim().min(1, required).max(120),
    town: z.string().trim().max(80),
    quote_fr: z.string().trim().min(1, required).max(400),
    quote_en: z.string().trim().max(400),
    published: z.boolean(),
  });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: item ?? EMPTY });
  const [logo, setLogo] = useState<string | null>(item?.logo ?? null);
  const [consent, setConsent] = useState<File | null>(null);
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const errors = form.formState.errors;
  const save = useMutation({
    mutationFn: (values: Values) => {
      const body = new FormData();
      for (const field of FIELDS) body.append(field, String(values[field]));
      body.append("logo", logo ?? "");
      if (consent) body.append("consent", consent);
      return item
        ? call(
            api.PATCH("/api/console/site/testimonials/{id}/", {
              params: { path: { id: item.id } },
              body: body as never,
            }),
          )
        : call(api.POST("/api/console/site/testimonials/", { body: body as never }));
    },
    onSuccess: () => {
      setSaved(true);
      setConsent(null);
      if (!item) {
        form.reset(EMPTY);
        setLogo(null);
      }
      onChanged();
    },
    onError: (error) =>
      setGeneral(
        applyServerErrors(error, [...FIELDS, "consent", "logo"] as never, form.setError, t),
      ),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/console/site/testimonials/{id}/", {
          params: { path: { id: item?.id ?? "" } },
        }),
      ),
    onSuccess: () => {
      setConfirm(false);
      onChanged();
      onDone();
    },
  });
  const published = useWatch({ control: form.control, name: "published" });
  const text = (field: Exclude<keyof Values, "published">, max: number, required_ = false) => (
    <Field
      id={`testimonial-${field}`}
      label={t(`console.site.testimonials.fields.${field}`)}
      required={required_}
      error={errors[field]?.message}
    >
      {(control) => <Input {...control} maxLength={max} {...form.register(field as never)} />}
    </Field>
  );

  return (
    <Card>
      <CardHeader className="flex-wrap gap-2">
        <CardTitle>
          {t(item ? "console.site.testimonials.editTitle" : "console.site.testimonials.newTitle")}
        </CardTitle>
        {item && (
          <span className="text-sm text-ink-3">
            {t("console.site.changed", {
              date: formatDay(item.updated_at.slice(0, 10), i18n.language),
            })}
          </span>
        )}
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            setGeneral(null);
            setSaved(false);
            void form.handleSubmit((values) => save.mutate(values))(event);
          }}
          noValidate
        >
          {saved && <Banner tone="ok">{t("console.site.saved")}</Banner>}
          {general && <Banner tone="due">{general}</Banner>}
          {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
          <div className="grid gap-4 min-[560px]:grid-cols-2">
            {text("name", 80, true)}
            {text("role", 80, true)}
            {text("school_name", 120, true)}
            {text("town", 80)}
          </div>
          <div className="grid gap-4 min-[1300px]:grid-cols-2">
            {(["fr", "en"] as const).map((lang) => (
              <fieldset key={lang} className="flex min-w-0 flex-col gap-3">
                <legend className="mb-3 text-sm font-bold tracking-wide text-ink-3 uppercase">
                  {t(`console.site.languages.${lang}`)}
                </legend>
                <Field
                  id={`testimonial-quote_${lang}`}
                  label={t(`console.site.testimonials.fields.quote_${lang}`)}
                  required={lang === "fr"}
                  error={errors[`quote_${lang}`]?.message}
                  help={lang === "en" ? t("console.site.englishHint") : undefined}
                >
                  {(control) => (
                    <Textarea
                      {...control}
                      maxLength={400}
                      className="min-h-24"
                      {...form.register(`quote_${lang}`)}
                    />
                  )}
                </Field>
              </fieldset>
            ))}
          </div>
          <Field
            id="testimonial-consent"
            label={t("console.site.testimonials.fields.consent")}
            required
            help={t("console.site.testimonials.consentHelp")}
            error={errors.root?.message}
          >
            {(control) => (
              <FilePicker
                id={control.id}
                file={consent}
                onFile={setConsent}
                deposited={item?.has_consent ?? false}
                download={item ? `/api/console/site/testimonials/${item.id}/consent/` : undefined}
              />
            )}
          </Field>
          <Field id="testimonial-logo" label={t("console.site.testimonials.fields.logo")}>
            {(control) => <PhotoPicker id={control.id} value={logo} onChange={setLogo} />}
          </Field>
          <CheckboxField
            id="testimonial-published"
            checked={published}
            onCheckedChange={(checked) => form.setValue("published", checked === true)}
            label={
              <>
                <b>{t("console.site.publish")}</b>
                <span className="block text-sm text-ink-3">
                  {t("console.site.testimonials.publishHint")}
                </span>
              </>
            }
          />
          <div className="flex flex-wrap justify-between gap-2">
            {item ? (
              <Button type="button" variant="destructive-outline" onClick={() => setConfirm(true)}>
                {t("console.site.delete")}
              </Button>
            ) : (
              <span />
            )}
            <span className="flex gap-2">
              {item && (
                <Button type="button" variant="outline" onClick={onDone}>
                  {t("common.cancel")}
                </Button>
              )}
              <Button type="submit" disabled={save.isPending}>
                {t("console.site.save")}
              </Button>
            </span>
          </div>
        </form>
      </CardContent>
      {item && (
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title={t("console.site.deleteTitle", { title: item.name })}
          confirmLabel={t("console.site.delete")}
          cancelLabel={t("common.cancel")}
          pending={remove.isPending}
          onConfirm={() => remove.mutate()}
        >
          {t("console.site.deleteText")}
        </ConfirmDialog>
      )}
    </Card>
  );
}
