// Partenaires de la bande qui défile sur le site (lot 2, partie 6) : nom, logo de la photothèque
// (sans logo : le nom en lettres), lien en https://.
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
  Skeleton,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { PhotoPicker, RankedList } from "./shared";

type Partner = Schemas["ConsolePartner"];
type Values = { name: string; link: string; published: boolean };

const MAX = 8; // comme le serveur (`Partner.MAX`)
const EMPTY: Values = { name: "", link: "", published: false };
const FIELDS = Object.keys(EMPTY) as (keyof Values)[];

export function PartnersPanel() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const list = useQuery({
    queryKey: keys.sitePartners,
    queryFn: () => call(api.GET("/api/console/site/partners/")),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.sitePartners });
  const move = useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: "up" | "down" }) =>
      call(
        api.POST("/api/console/site/partners/{id}/move/", {
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
          <CardTitle>{t("console.site.partners.title")}</CardTitle>
        </CardHeader>
        {items.length === 0 ? (
          <CardContent>
            <p className="text-ink-3">{t("console.site.partners.empty")}</p>
          </CardContent>
        ) : (
          <RankedList
            label={t("console.site.partners.title")}
            rows={items.map((item) => ({
              id: item.id,
              title: item.name,
              sub: item.link ?? undefined,
              published: item.published,
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
            {t("console.site.partners.count", { count: items.length, max: MAX })}
          </span>
          <Button size="sm" disabled={items.length >= MAX} onClick={() => setEditing(null)}>
            <Icon name="plus" /> {t("console.site.partners.add")}
          </Button>
        </CardFooter>
      </Card>
      <PartnerEditor
        key={selected?.id ?? "new"}
        item={selected}
        onChanged={refresh}
        onDone={() => setEditing(null)}
      />
    </div>
  );
}

function PartnerEditor({
  item,
  onChanged,
  onDone,
}: {
  item: Partner | null;
  onChanged: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const required = t("fieldErrors.required");
  const schema = z.object({
    name: z.string().trim().min(1, required).max(80),
    link: z.string().trim().max(200),
    published: z.boolean(),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: item
      ? {
          name: item.name,
          link: item.link ?? "",
          published: item.published,
        }
      : EMPTY,
  });
  const [logo, setLogo] = useState<string | null>(item?.logo ?? null);
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const errors = form.formState.errors;
  const save = useMutation({
    mutationFn: (values: Values) => {
      const body = { ...values, logo };
      return item
        ? call(
            api.PATCH("/api/console/site/partners/{id}/", {
              params: { path: { id: item.id } },
              body,
            }),
          )
        : call(api.POST("/api/console/site/partners/", { body }));
    },
    onSuccess: () => {
      setSaved(true);
      if (!item) {
        form.reset(EMPTY);
        setLogo(null);
      }
      onChanged();
    },
    onError: (error) => setGeneral(applyServerErrors(error, FIELDS, form.setError, t)),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/console/site/partners/{id}/", {
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
  const text = (field: Exclude<keyof Values, "published">, max: number, type = "text") => (
    <Field
      id={`reference-${field}`}
      label={t(`console.site.partners.fields.${field}`)}
      required={field !== "link"}
      help={field === "link" ? t("console.site.partners.linkHelp") : undefined}
      error={errors[field]?.message}
    >
      {(control) => (
        <Input {...control} type={type} maxLength={max} {...form.register(field as never)} />
      )}
    </Field>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {t(item ? "console.site.partners.editTitle" : "console.site.partners.newTitle")}
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
          <div className="grid gap-4 min-[560px]:grid-cols-2">
            {text("name", 80)}
            {text("link", 200, "url")}
          </div>
          <Field id="partner-logo" label={t("console.site.partners.fields.logo")}>
            {(control) => <PhotoPicker id={control.id} value={logo} onChange={setLogo} />}
          </Field>
          <CheckboxField
            id="partner-published"
            checked={published}
            onCheckedChange={(checked) => form.setValue("published", checked === true)}
            label={
              <>
                <b>{t("console.site.partners.publish")}</b>
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
