// Carte « Caisses » des paramètres de l'école (M13, sans maquette) : nom, code et état de chaque
// caisse, avec `finance.configure_fees`. Une caisse se désactive, jamais ne s'efface ; son code
// (dans le numéro des reçus) ne change plus après la création.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Skeleton,
  StatusPill,
  Tag,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { type CashRegister, useCashRegisters } from "../cash/data";
import { useRefresh } from "../organisation/data";
import { LoadError } from "../status/StatusPages";

const FIELDS = ["name", "code", "is_active"] as const;

export function CashRegistersCard() {
  const { t } = useTranslation();
  const registers = useCashRegisters();
  const [editing, setEditing] = useState<CashRegister | "new" | null>(null);

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("settings.registers.title")}</CardTitle>
        <Button variant="outline" size="sm" onClick={() => setEditing("new")}>
          {t("settings.registers.add")}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-ink-3">{t("settings.registers.help")}</p>
        {registers.error ? (
          <LoadError error={registers.error} onRetry={() => void registers.refetch()} />
        ) : !registers.data ? (
          <Skeleton label={t("common.loading")} />
        ) : registers.data.length === 0 ? (
          <p className="text-ink-3">{t("settings.registers.none")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line-soft">
            {registers.data.map((register) => (
              <li key={register.id} className="flex flex-wrap items-center gap-3 py-2.5">
                <Tag>{register.code}</Tag>
                <b className="min-w-0 flex-1">{register.name}</b>
                <StatusPill tone={register.is_active ? "ok" : "gray"}>
                  {t(
                    register.is_active
                      ? "settings.registers.active"
                      : "settings.registers.inactive",
                  )}
                </StatusPill>
                <Button variant="ghost" size="sm" onClick={() => setEditing(register)}>
                  {t("settings.registers.edit")}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <DialogRoot open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        {editing !== null && (
          <RegisterForm
            key={editing === "new" ? "new" : editing.id}
            register={editing === "new" ? null : editing}
            onClose={() => setEditing(null)}
          />
        )}
      </DialogRoot>
    </Card>
  );
}

function RegisterForm({
  register,
  onClose,
}: {
  register: CashRegister | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = z.object({
    name: z.string().trim().min(1, t("fieldErrors.required")).max(40),
    code: register
      ? z.string()
      : z
          .string()
          .trim()
          .toUpperCase()
          .regex(/^[A-Z0-9]{1,4}$/, t("settings.registers.codeHelp")),
    is_active: z.boolean(),
  });
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      name: register?.name ?? "",
      code: register?.code ?? "",
      is_active: register?.is_active ?? true,
    },
  });
  const save = useMutation({
    mutationFn: ({ name, code, is_active }: z.output<typeof schema>) =>
      register
        ? call(
            api.PATCH("/api/cash-registers/{id}/", {
              params: { path: { id: register.id } },
              body: { name, is_active },
            }),
          )
        : call(api.POST("/api/cash-registers/", { body: { name, code } })),
    onSuccess: async () => {
      await refresh(keys.cashRegisters);
      onClose();
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  const { errors } = form.formState;

  return (
    <DialogContent
      title={t(register ? "settings.registers.editTitle" : "settings.registers.createTitle")}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          <Button type="submit" form="cash-register" disabled={save.isPending}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <form
        id="cash-register"
        noValidate
        className="flex flex-col gap-3"
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          save.mutate(values);
        })}
      >
        {general && <Banner tone="due">{general}</Banner>}
        <Field
          id="cash-register-name"
          label={t("settings.registers.name")}
          required
          error={errors.name?.message}
        >
          {(control) => (
            <Input
              {...control}
              placeholder={t("settings.registers.namePlaceholder")}
              {...form.register("name")}
            />
          )}
        </Field>
        {register ? (
          <Controller
            control={form.control}
            name="is_active"
            render={({ field }) => (
              <CheckboxField
                id="cash-register-active"
                label={t("settings.registers.isActive")}
                checked={field.value}
                onCheckedChange={(checked) => field.onChange(checked === true)}
              />
            )}
          />
        ) : (
          <Field
            id="cash-register-code"
            label={t("settings.registers.code")}
            required
            help={t("settings.registers.codeHelp")}
            error={errors.code?.message}
          >
            {(control) => <Input {...control} {...form.register("code")} />}
          </Field>
        )}
      </form>
    </DialogContent>
  );
}
