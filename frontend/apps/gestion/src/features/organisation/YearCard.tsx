// Carte « Année 2026-2027 » : nom, dates, année en cours, suppression d'une année créée par erreur.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
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
  Input,
  StatusPill,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useRefresh, type Year } from "./data";

export function useYearSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z
        .object({
          name: z.string().trim().max(20),
          starts_on: z.string().min(1, t("validation.dateRequired")),
          ends_on: z.string().min(1, t("validation.dateRequired")),
        })
        .refine((year) => !year.starts_on || !year.ends_on || year.starts_on < year.ends_on, {
          path: ["ends_on"],
          message: t("validation.datesOrder"),
        }),
    [t],
  );
}

export function YearCard({ year, onDeleted }: { year: Year; onDeleted: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const schema = useYearSchema();
  const [general, setGeneral] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { name: year.name, starts_on: year.starts_on, ends_on: year.ends_on },
  });
  const save = useMutation({
    mutationFn: (body: z.output<typeof schema>) =>
      call(api.PATCH("/api/academic-years/{id}/", { params: { path: { id: year.id } }, body })),
    onSuccess: async (saved) => {
      form.reset({ name: saved.name, starts_on: saved.starts_on, ends_on: saved.ends_on });
      await refresh(keys.years);
    },
    onError: (error) =>
      setGeneral(applyServerErrors(error, ["name", "starts_on", "ends_on"], form.setError, t)),
  });
  const makeCurrent = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/academic-years/{id}/make-current/", { params: { path: { id: year.id } } }),
      ),
    onSuccess: () => refresh(keys.years),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/academic-years/{id}/", { params: { path: { id: year.id } } })),
    onSuccess: async () => {
      setDeleting(false);
      onDeleted();
      await refresh(keys.years);
    },
  });
  const { errors } = form.formState;
  const failure = makeCurrent.error ?? remove.error;

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
          <CardTitle>{t("organisation.year.title", { name: year.name })}</CardTitle>
          {year.is_current ? (
            <StatusPill tone="ok">{t("organisation.year.current")}</StatusPill>
          ) : (
            <StatusPill tone="info">{t("organisation.year.open")}</StatusPill>
          )}
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {general && <Banner tone="due">{general}</Banner>}
          {failure && <Banner tone="due">{errorMessage(failure, t)}</Banner>}
          {save.isSuccess && !form.formState.isDirty && (
            <Banner tone="ok" role="status">
              {t("organisation.year.saved")}
            </Banner>
          )}
          <div className="grid gap-3 min-[600px]:grid-cols-2">
            <Field
              id="year-starts"
              label={t("organisation.year.starts")}
              error={errors.starts_on?.message}
            >
              {(control) => <Input {...control} type="date" {...form.register("starts_on")} />}
            </Field>
            <Field
              id="year-ends"
              label={t("organisation.year.ends")}
              error={errors.ends_on?.message}
            >
              {(control) => <Input {...control} type="date" {...form.register("ends_on")} />}
            </Field>
            <Field
              id="year-name"
              label={t("organisation.year.name")}
              error={errors.name?.message}
              className="min-[600px]:col-span-2"
            >
              {(control) => <Input {...control} {...form.register("name")} />}
            </Field>
          </div>
          {!year.is_current && (
            <p className="text-[.8rem] text-ink-3">{t("organisation.year.currentHelp")}</p>
          )}
        </CardContent>
        <CardFooter>
          <div className="flex flex-wrap gap-2">
            {!year.is_current && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={makeCurrent.isPending}
                  onClick={() => makeCurrent.mutate()}
                >
                  {t("organisation.year.makeCurrent")}
                </Button>
                <Button variant="destructive-outline" size="sm" onClick={() => setDeleting(true)}>
                  {t("organisation.year.delete")}
                </Button>
              </>
            )}
          </div>
          <Button type="submit" variant="outline" disabled={save.isPending}>
            {t("common.save")}
          </Button>
        </CardFooter>
      </form>
      <ConfirmDialog
        open={deleting}
        onOpenChange={(open) => {
          setDeleting(open);
          remove.reset();
        }}
        title={t("organisation.year.deleteTitle", { name: year.name })}
        confirmLabel={t("organisation.year.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      >
        <p className="text-sm text-ink-2">{t("organisation.year.deleteText")}</p>
        {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
      </ConfirmDialog>
    </Card>
  );
}
