// Type de frais (E1) : nom, catégorie, compte SYSCOHADA, prime des enseignants, actif. Un type
// qui a des barèmes ne se supprime pas : on le désactive (refus du serveur `fee_type_in_use`).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  CheckboxField,
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
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useRefresh } from "../organisation/data";
import { CATEGORIES, type FeeCategory, type FeeType } from "./data";

type Props = {
  value: FeeType | "new" | null;
  onClose: () => void;
  onSaved: (type: FeeType) => void;
  onDeleted: () => void;
};

const FIELDS = ["name", "category", "accounting_code", "funds_teacher_bonus", "is_active"] as const;

export function FeeTypeDialog({ value, onClose, onSaved, onDeleted }: Props) {
  return (
    <DialogRoot open={value !== null} onOpenChange={(open) => !open && onClose()}>
      {value !== null && (
        <FeeTypeForm
          key={value === "new" ? "new" : value.id}
          type={value === "new" ? null : value}
          onClose={onClose}
          onSaved={onSaved}
          onDeleted={onDeleted}
        />
      )}
    </DialogRoot>
  );
}

function FeeTypeForm({
  type,
  onClose,
  onSaved,
  onDeleted,
}: Omit<Props, "value"> & { type: FeeType | null }) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = z.object({
    name: z.string().trim().min(1, t("fieldErrors.required")).max(80),
    category: z.string(),
    accounting_code: z.string().trim().max(20),
    funds_teacher_bonus: z.boolean(),
    is_active: z.boolean(),
  });
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      name: type?.name ?? "",
      category: type?.category ?? "tuition",
      accounting_code: type?.accounting_code ?? "",
      funds_teacher_bonus: type?.funds_teacher_bonus ?? false,
      is_active: type?.is_active ?? true,
    },
  });
  const save = useMutation({
    mutationFn: (values: z.output<typeof schema>) => {
      const body = { ...values, category: values.category as FeeCategory };
      return type
        ? call(api.PATCH("/api/fee-types/{id}/", { params: { path: { id: type.id } }, body }))
        : call(api.POST("/api/fee-types/", { body }));
    },
    onSuccess: async (saved) => {
      await refresh(keys.feeTypes);
      onSaved(saved as FeeType);
      onClose();
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/fee-types/{id}/", { params: { path: { id: type!.id } } })),
    onSuccess: async () => {
      await refresh(keys.feeTypes);
      onDeleted();
      onClose();
    },
    onError: (error) => setGeneral(errorMessage(error, t)),
  });
  const { errors } = form.formState;

  return (
    <DialogContent
      title={type ? t("fees.typeDialog.editTitle") : t("fees.typeDialog.createTitle")}
      footer={
        <>
          {type && (
            <Button
              variant="outline"
              className="mr-auto"
              disabled={remove.isPending}
              onClick={() => {
                setGeneral(null);
                remove.mutate();
              }}
            >
              {t("common.delete")}
            </Button>
          )}
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          <Button type="submit" form="fee-type" disabled={save.isPending}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <form
        id="fee-type"
        noValidate
        className="flex flex-col gap-3"
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          save.mutate(values);
        })}
      >
        {general && <Banner tone="due">{general}</Banner>}
        <Field
          id="fee-type-name"
          label={t("fees.typeDialog.name")}
          required
          error={errors.name?.message}
        >
          {(control) => <Input {...control} {...form.register("name")} />}
        </Field>
        <Field id="fee-type-category" label={t("fees.typeDialog.category")}>
          {(control) => (
            <Select {...control} {...form.register("category")}>
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {t(`fees.categories.${category}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          id="fee-type-account"
          label={t("fees.typeDialog.accountingCode")}
          help={t("fees.typeDialog.accountingCodeHelp")}
          error={errors.accounting_code?.message}
        >
          {(control) => <Input {...control} {...form.register("accounting_code")} />}
        </Field>
        <Controller
          control={form.control}
          name="funds_teacher_bonus"
          render={({ field }) => (
            <CheckboxField
              id="fee-type-bonus"
              label={t("fees.typeDialog.bonus")}
              checked={field.value}
              onCheckedChange={(checked) => field.onChange(checked === true)}
            />
          )}
        />
        {type && (
          <Controller
            control={form.control}
            name="is_active"
            render={({ field }) => (
              <CheckboxField
                id="fee-type-active"
                label={t("fees.typeDialog.active")}
                checked={field.value}
                onCheckedChange={(checked) => field.onChange(checked === true)}
              />
            )}
          />
        )}
      </form>
    </DialogContent>
  );
}
