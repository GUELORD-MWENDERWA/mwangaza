// Nouvelle année scolaire (C1) : dates, modèle de découpage et, en option, les classes d'une autre
// année (sans les titulaires).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Select,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { TEMPLATES, useRefresh, type Template, type Year } from "./data";
import { useYearSchema } from "./YearCard";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  years: Year[];
  onCreated: (year: Year) => void;
};

export function NewYearDialog({ open, onOpenChange, years, onCreated }: Props) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const yearSchema = useYearSchema();
  const [general, setGeneral] = useState<string | null>(null);
  const current = years.find((year) => year.is_current);
  const form = useForm({
    resolver: zodResolver(yearSchema.and(z.object({ template: z.string(), copy: z.string() }))),
    defaultValues: {
      name: "",
      starts_on: "",
      ends_on: "",
      template: "secondary",
      copy: current?.id ?? "",
    },
  });
  const create = useMutation({
    mutationFn: ({
      copy,
      template,
      ...values
    }: z.output<typeof yearSchema> & {
      template: string;
      copy: string;
    }) =>
      call(
        api.POST("/api/academic-years/", {
          body: {
            ...values,
            template: template as Template,
            copy_classes_from: copy || null,
          },
        }),
      ),
    onSuccess: async (year) => {
      await refresh(keys.years);
      onCreated(year);
      onOpenChange(false);
      form.reset();
    },
    onError: (error) =>
      setGeneral(
        applyServerErrors(error, ["name", "starts_on", "ends_on", "template"], form.setError, t),
      ),
  });
  const { errors } = form.formState;

  return (
    <DialogRoot
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        setGeneral(null);
      }}
    >
      <DialogContent
        title={t("organisation.create.title")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form="new-year" disabled={create.isPending}>
              {t("organisation.create.submit")}
            </Button>
          </>
        }
      >
        <form
          id="new-year"
          noValidate
          className="grid gap-3 min-[600px]:grid-cols-2"
          onSubmit={form.handleSubmit((values) => {
            setGeneral(null);
            create.mutate(values);
          })}
        >
          {general && (
            <Banner tone="due" className="min-[600px]:col-span-2">
              {general}
            </Banner>
          )}
          <Field
            id="new-year-starts"
            label={t("organisation.year.starts")}
            required
            error={errors.starts_on?.message}
          >
            {(control) => <Input {...control} type="date" {...form.register("starts_on")} />}
          </Field>
          <Field
            id="new-year-ends"
            label={t("organisation.year.ends")}
            required
            error={errors.ends_on?.message}
          >
            {(control) => <Input {...control} type="date" {...form.register("ends_on")} />}
          </Field>
          <Field
            id="new-year-name"
            label={t("organisation.create.name")}
            help={t("organisation.create.nameHelp")}
            error={errors.name?.message}
            className="min-[600px]:col-span-2"
          >
            {(control) => <Input {...control} {...form.register("name")} />}
          </Field>
          <Field
            id="new-year-template"
            label={t("organisation.create.template")}
            help={t("organisation.create.templateHelp")}
            className="min-[600px]:col-span-2"
          >
            {(control) => (
              <Select {...control} {...form.register("template")}>
                {TEMPLATES.map((template) => (
                  <option key={template} value={template}>
                    {t(`organisation.templates.${template}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            id="new-year-copy"
            label={t("organisation.create.copy")}
            help={t("organisation.create.copyHelp")}
            className="min-[600px]:col-span-2"
          >
            {(control) => (
              <Select {...control} {...form.register("copy")}>
                <option value="">{t("organisation.create.noCopy")}</option>
                {years.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </form>
      </DialogContent>
    </DialogRoot>
  );
}
