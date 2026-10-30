// Formules d'abonnement du site (lot 2, partie 6, page des prix) : prix saisi en unités (40 ou
// 40,50), gardé en centimes ; vide : « sur devis ». Les textes d'exemple livrés avec le site
// portent l'étiquette « Exemple » tant qu'on ne les a pas remplacés.
import { zodResolver } from "@hookform/resolvers/zod";
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
  CheckboxField,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  Select,
  Skeleton,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { ExampleToggle, RankedList } from "./shared";

type Plan = Schemas["ConsolePlan"];
type Values = {
  name_fr: string;
  name_en: string;
  tagline_fr: string;
  tagline_en: string;
  price: string;
  currency: "USD" | "CDF";
  period: "month" | "year";
  features_fr: string;
  features_en: string;
  highlighted: boolean;
  published: boolean;
};

const CURRENCIES = ["USD", "CDF"] as const;
const MAX = 4; // comme le serveur (`SitePlan.MAX`)
const EMPTY: Values = {
  name_fr: "",
  name_en: "",
  tagline_fr: "",
  tagline_en: "",
  price: "",
  currency: "USD",
  period: "month",
  features_fr: "",
  features_en: "",
  highlighted: false,
  published: false,
};
const FIELDS = Object.keys(EMPTY) as (keyof Values)[];

/** « 40,50 » → 4050 (centimes) ; vide → null ; texte invalide → NaN. */
export function toMinor(text: string): number | null {
  const clean = text.trim().replace(",", ".");
  if (!clean) return null;
  if (!/^\d{1,6}(\.\d{1,2})?$/.test(clean)) return Number.NaN;
  return Math.round(Number(clean) * 100);
}

const fromMinor = (minor: number | null | undefined) =>
  minor == null ? "" : String(minor / 100).replace(".", ",");

export function PlansPanel() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const list = useQuery({
    queryKey: keys.sitePlans,
    queryFn: () => call(api.GET("/api/console/site/plans/")),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.sitePlans });
  const move = useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: "up" | "down" }) =>
      call(
        api.POST("/api/console/site/plans/{id}/move/", {
          params: { path: { id } },
          body: { direction },
        }),
      ),
    onSuccess: refresh,
  });
  if (list.isPending) return <Skeleton label={t("common.loading")} />;
  if (list.isError) return <Banner tone="due">{errorMessage(list.error, t)}</Banner>;
  const items = list.data;
  const selected = items.find((item) => item.id === editing) ?? null;

  return (
    <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader className="flex-wrap gap-3">
          <CardTitle>{t("console.site.plans.title")}</CardTitle>
        </CardHeader>
        {items.length === 0 ? (
          <CardContent>
            <p className="text-ink-3">{t("console.site.plans.empty")}</p>
          </CardContent>
        ) : (
          <RankedList
            label={t("console.site.plans.title")}
            rows={items.map((item) => ({
              id: item.id,
              title: item.name_fr,
              sub: item.price == null ? t("console.site.plans.onQuote") : fromMinor(item.price),
              published: item.published,
              note: item.is_example ? t("console.site.example") : undefined,
            }))}
            selected={selected?.id}
            onEdit={setEditing}
            onMove={(id, direction) => move.mutate({ id, direction })}
            moving={move.isPending}
            error={move.error}
          />
        )}
        <CardFooter className="flex-wrap justify-between gap-3">
          <span className="text-sm text-ink-3">
            {t("console.site.plans.count", { count: items.length, max: MAX })}
          </span>
          <Button size="sm" disabled={items.length >= MAX} onClick={() => setEditing(null)}>
            <Icon name="plus" /> {t("console.site.plans.add")}
          </Button>
        </CardFooter>
      </Card>
      <PlanEditor
        key={selected?.id ?? "new"}
        item={selected}
        onChanged={refresh}
        onDone={() => setEditing(null)}
      />
    </div>
  );
}

function PlanEditor({
  item,
  onChanged,
  onDone,
}: {
  item: Plan | null;
  onChanged: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const required = t("fieldErrors.required");
  const lines = (max: number) =>
    z.string().refine((text) => text.split("\n").filter((l) => l.trim()).length <= max, {
      message: t("console.site.plans.tooMany"),
    });
  const schema = z.object({
    name_fr: z.string().trim().min(1, required).max(40),
    name_en: z.string().trim().max(40),
    tagline_fr: z.string().trim().min(1, required).max(120),
    tagline_en: z.string().trim().max(120),
    price: z
      .string()
      .refine((text) => !Number.isNaN(toMinor(text)), t("console.site.plans.badPrice")),
    currency: z.enum(["USD", "CDF"]),
    period: z.enum(["month", "year"]),
    features_fr: lines(8).refine((text) => text.trim() !== "", required),
    features_en: lines(8),
    highlighted: z.boolean(),
    published: z.boolean(),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: item
      ? {
          name_fr: item.name_fr,
          name_en: item.name_en ?? "",
          tagline_fr: item.tagline_fr,
          tagline_en: item.tagline_en ?? "",
          price: fromMinor(item.price),
          currency: item.currency as Values["currency"],
          period: item.period as Values["period"],
          features_fr: item.features_fr,
          features_en: item.features_en ?? "",
          highlighted: item.highlighted,
          published: item.published,
        }
      : EMPTY,
  });
  const [example, setExample] = useState(item?.is_example ?? false);
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const errors = form.formState.errors;
  const save = useMutation({
    mutationFn: (values: Values) => {
      const body = {
        ...values,
        price: toMinor(values.price),
        ...(item?.is_example ? { is_example: example } : {}),
      };
      return item
        ? call(
            api.PATCH("/api/console/site/plans/{id}/", { params: { path: { id: item.id } }, body }),
          )
        : call(api.POST("/api/console/site/plans/", { body }));
    },
    onSuccess: () => {
      setSaved(true);
      if (!item) form.reset(EMPTY);
      onChanged();
    },
    onError: (error) => setGeneral(applyServerErrors(error, FIELDS, form.setError, t)),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/console/site/plans/{id}/", { params: { path: { id: item?.id ?? "" } } }),
      ),
    onSuccess: () => {
      setConfirm(false);
      onChanged();
      onDone();
    },
  });
  const highlighted = useWatch({ control: form.control, name: "highlighted" });
  const published = useWatch({ control: form.control, name: "published" });
  const text = (
    field: "name_fr" | "name_en" | "tagline_fr" | "tagline_en" | "price",
    max: number,
  ) => (
    <Field
      id={`plan-${field}`}
      label={t(`console.site.plans.fields.${field}`)}
      required={field.endsWith("_fr")}
      help={field === "price" ? t("console.site.plans.priceHelp") : undefined}
      error={errors[field]?.message}
    >
      {(control) => (
        <Input
          {...control}
          maxLength={max}
          inputMode={field === "price" ? "decimal" : undefined}
          {...form.register(field)}
        />
      )}
    </Field>
  );
  const points = (lang: "fr" | "en") => (
    <Field
      id={`plan-features_${lang}`}
      label={t(`console.site.plans.fields.features_${lang}`)}
      required={lang === "fr"}
      help={t("console.site.plans.featuresHelp")}
      error={errors[`features_${lang}`]?.message}
    >
      {(control) => (
        <Textarea
          {...control}
          maxLength={800}
          className="min-h-32"
          {...form.register(`features_${lang}`)}
        />
      )}
    </Field>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {t(item ? "console.site.plans.editTitle" : "console.site.plans.newTitle")}
        </CardTitle>
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
          {item?.is_example && (
            <ExampleToggle id="plan-example" checked={example} onChange={setExample} />
          )}
          <div className="grid gap-4 min-[560px]:grid-cols-2">
            {text("name_fr", 40)}
            {text("name_en", 40)}
            {text("tagline_fr", 120)}
            {text("tagline_en", 120)}
          </div>
          <div className="grid gap-4 min-[560px]:grid-cols-3">
            {text("price", 10)}
            <Field id="plan-currency" label={t("console.site.plans.fields.currency")}>
              {(control) => (
                <Select {...control} {...form.register("currency")}>
                  {CURRENCIES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field id="plan-period" label={t("console.site.plans.fields.period")}>
              {(control) => (
                <Select {...control} {...form.register("period")}>
                  <option value="month">{t("console.site.plans.month")}</option>
                  <option value="year">{t("console.site.plans.year")}</option>
                </Select>
              )}
            </Field>
          </div>
          <div className="grid gap-4 min-[560px]:grid-cols-2">
            {points("fr")}
            {points("en")}
          </div>
          <CheckboxField
            id="plan-highlighted"
            checked={highlighted}
            onCheckedChange={(checked) => form.setValue("highlighted", checked === true)}
            label={<b>{t("console.site.plans.highlight")}</b>}
          />
          <CheckboxField
            id="plan-published"
            checked={published}
            onCheckedChange={(checked) => form.setValue("published", checked === true)}
            label={<b>{t("console.site.plans.publish")}</b>}
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
          title={t("console.site.deleteTitle", { title: item.name_fr })}
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
