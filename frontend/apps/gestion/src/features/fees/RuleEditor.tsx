// Éditeur d'un barème (E2) : portée (toute l'école, un niveau, une option ou une classe), devise
// parmi celles de l'école, total, découpage en tranches, mensuel ou unique. La somme des tranches
// doit égaler le total : rien n'est envoyé sinon (le serveur le vérifie aussi). Montants saisis
// lus par `@mwangaza/money`, envoyés en entiers (centimes, francs).
import { api, ApiError, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  formatAmount,
  formatAmountValue,
  parseAmount,
  sumAmounts,
  type Currency,
} from "@mwangaza/money";
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
  Icon,
  Input,
  Segmented,
  Select,
  Table,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useFieldArray, useForm, useWatch } from "react-hook-form";

import { errorMessage, fieldMessage } from "../../lib/errors";
import { keys, useSchool } from "../../lib/queries";
import { useClasses, useLevels, useRefresh, useTracks, type Year } from "../organisation/data";
import { SCHEDULE_KINDS, type FeeRule, type FeeType, type ScheduleKind } from "./data";
import { installmentLines, monthlyLines, spread, type Line } from "./schedule";

type Props = { year: Year; type: FeeType; rule: FeeRule | null; onClose: () => void };

type Row = { label: string; amount: string; due_on: string };
type Values = {
  scope: string;
  currency: Currency;
  total: string;
  kind: ScheduleKind;
  lines: Row[];
};

const LOCALES: Record<string, string> = { fr: "fr-FR", en: "en-GB" };

function scopeOf(rule: FeeRule | null): string {
  if (rule?.class_group) return `class:${rule.class_group}`;
  if (rule?.level) return `level:${rule.level}`;
  if (rule?.track) return `track:${rule.track}`;
  return "";
}

/** Premier refus d'une saisie (somme, devise, portée…) ou erreur métier, traduits. */
function ruleError(error: unknown, t: ReturnType<typeof useTranslation>["t"]): string {
  if (error instanceof ApiError && error.code === "invalid") {
    const [first] = Object.values(error.fields)[0] ?? [];
    if (first) return fieldMessage(first.code, t);
  }
  return errorMessage(error, t);
}

export function RuleEditor({ year, type, rule, onClose }: Props) {
  const { t, i18n } = useTranslation();
  const refresh = useRefresh();
  const school = useSchool().data;
  const currencies = (school?.enabled_currencies ?? ["USD"]) as Currency[];
  const levels = useLevels();
  const tracks = useTracks();
  const classes = useClasses(year.id);
  const [general, setGeneral] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const nth = (n: number) =>
    n === 1 ? t("fees.editor.firstInstallment") : t("fees.editor.nthInstallment", { n });
  const monthName = (month: number) => {
    const name = new Intl.DateTimeFormat(LOCALES[i18n.language] ?? "fr-FR", {
      month: "long",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(2000, month - 1, 1)));
    return name.charAt(0).toUpperCase() + name.slice(1);
  };
  const currency0 = (rule?.currency ?? school?.default_currency ?? currencies[0]) as Currency;
  const toRows = (lines: Line[], currency: Currency): Row[] =>
    lines.map((line) => ({
      label: line.label,
      amount: line.amount_minor === null ? "" : formatAmountValue(line.amount_minor, currency),
      due_on: line.due_on,
    }));

  const form = useForm<Values>({
    defaultValues: {
      scope: scopeOf(rule),
      currency: currency0,
      total: rule ? formatAmountValue(rule.total_amount_minor, currency0) : "",
      kind: rule?.schedule_kind ?? "installments",
      lines: rule
        ? toRows(
            rule.installments.map(({ label, amount_minor, due_on }) => ({
              label,
              amount_minor,
              due_on,
            })),
            currency0,
          )
        : toRows(installmentLines(null, nth), currency0),
    },
  });
  const lines = useFieldArray({ control: form.control, name: "lines" });
  const [currency, total, kind, rows] = useWatch({
    control: form.control,
    name: ["currency", "total", "kind", "lines"],
  });
  const totalMinor = parseAmount(total, currency);
  const amounts = rows.map((row) => parseAmount(row.amount, currency));
  const sum = amounts.every((amount) => amount !== null) ? sumAmounts(amounts as number[]) : null;

  const changeKind = (next: ScheduleKind) => {
    form.setValue("kind", next);
    const proposed =
      next === "monthly"
        ? monthlyLines(totalMinor, year.starts_on, year.ends_on, monthName)
        : next === "single"
          ? [{ label: type.name, amount_minor: totalMinor, due_on: year.starts_on }]
          : installmentLines(totalMinor, nth);
    lines.replace(toRows(proposed, currency));
  };

  const save = useMutation({
    mutationFn: (values: Values) => {
      const [kindOfScope, id = null] = values.scope.split(":");
      const body = {
        level: kindOfScope === "level" ? id : null,
        track: kindOfScope === "track" ? id : null,
        class_group: kindOfScope === "class" ? id : null,
        currency: values.currency,
        total_amount_minor: parseAmount(values.total, values.currency)!,
        schedule_kind: values.kind,
        installments: values.lines.map((line) => ({
          label: line.label.trim(),
          amount_minor: parseAmount(line.amount, values.currency)!,
          due_on: line.due_on,
        })),
      };
      return rule
        ? call(api.PUT("/api/fee-rules/{id}/", { params: { path: { id: rule.id } }, body }))
        : call(
            api.POST("/api/fee-rules/", {
              body: { ...body, academic_year: year.id, fee_type: type.id },
            }),
          );
    },
    onSuccess: async () => {
      await refresh(keys.feeRules);
      onClose();
    },
    onError: (error) => setGeneral(ruleError(error, t)),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/fee-rules/{id}/", { params: { path: { id: rule!.id } } })),
    onSuccess: async () => {
      await refresh(keys.feeRules);
      onClose();
    },
    onError: (error) => {
      setConfirmDelete(false);
      setGeneral(errorMessage(error, t));
    },
  });

  const submit = form.handleSubmit((values) => {
    setGeneral(null);
    let valid = true;
    if (!totalMinor) {
      form.setError("total", { message: t("fees.editor.invalidAmount") });
      valid = false;
    }
    values.lines.forEach((line, index) => {
      if (!line.label.trim()) {
        form.setError(`lines.${index}.label`, { message: t("fieldErrors.required") });
        valid = false;
      }
      if (!parseAmount(line.amount, values.currency)) {
        form.setError(`lines.${index}.amount`, { message: t("fees.editor.invalidAmount") });
        valid = false;
      }
      if (!line.due_on) {
        form.setError(`lines.${index}.due_on`, { message: t("fieldErrors.required") });
        valid = false;
      }
    });
    if (valid && sum !== totalMinor) {
      setGeneral(t("fieldErrors.installments_total_mismatch"));
      valid = false;
    }
    if (valid) save.mutate(values);
  });
  const { errors } = form.formState;
  const title = rule
    ? t("fees.editor.title", { scope: rule.scope_name || t("fees.rules.wholeSchool") })
    : t("fees.editor.newTitle", { type: type.name });

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{title}</CardTitle>
        <Segmented
          label={t("fees.editor.kind")}
          value={kind}
          onValueChange={changeKind}
          options={SCHEDULE_KINDS.map((value) => ({
            value,
            label: t(`fees.editor.kinds.${value}`),
          }))}
        />
      </CardHeader>
      <form id="fee-rule" noValidate onSubmit={submit}>
        <CardContent className="grid gap-3 min-[600px]:grid-cols-3">
          {general && (
            <Banner tone="due" className="min-[600px]:col-span-3">
              {general}
            </Banner>
          )}
          <Field id="rule-scope" label={t("fees.editor.scope")}>
            {(control) => (
              // Contrôlé : la portée reste choisie quand les niveaux et classes arrivent après.
              <Controller
                control={form.control}
                name="scope"
                render={({ field }) => (
                  <Select {...control} {...field}>
                    <option value="">{t("fees.rules.wholeSchool")}</option>
                    <optgroup label={t("fees.editor.levels")}>
                      {(levels.data ?? []).map((level) => (
                        <option key={level.id} value={`level:${level.id}`}>
                          {level.name}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label={t("fees.editor.tracks")}>
                      {(tracks.data ?? []).map((track) => (
                        <option key={track.id} value={`track:${track.id}`}>
                          {track.name}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label={t("fees.editor.classes")}>
                      {(classes.data ?? []).map((group) => (
                        <option key={group.id} value={`class:${group.id}`}>
                          {group.name}
                        </option>
                      ))}
                    </optgroup>
                  </Select>
                )}
              />
            )}
          </Field>
          <Field id="rule-currency" label={t("fees.editor.currency")}>
            {(control) => (
              <Select {...control} {...form.register("currency")}>
                {currencies.map((code) => (
                  <option key={code} value={code}>
                    {t(`fees.currencies.${code}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            id="rule-total"
            label={t("fees.editor.total")}
            required
            error={errors.total?.message}
          >
            {(control) => (
              <Input {...control} inputMode="decimal" className="num" {...form.register("total")} />
            )}
          </Field>
        </CardContent>
        <Table>
          <thead>
            <tr>
              <th>{t("fees.editor.label")}</th>
              <th className="text-right">{t("fees.editor.amount")}</th>
              <th>{t("fees.editor.dueOn")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {lines.fields.map((line, index) => (
              <tr key={line.id}>
                <td>
                  <Input
                    aria-label={t("fees.editor.labelOf", { n: index + 1 })}
                    aria-invalid={Boolean(errors.lines?.[index]?.label)}
                    className="min-h-8 min-w-[120px]"
                    {...form.register(`lines.${index}.label`)}
                  />
                </td>
                <td>
                  <Input
                    aria-label={t("fees.editor.amountOf", { n: index + 1 })}
                    aria-invalid={Boolean(errors.lines?.[index]?.amount)}
                    inputMode="decimal"
                    className="num min-h-8 min-w-[100px]"
                    {...form.register(`lines.${index}.amount`)}
                  />
                </td>
                <td>
                  <Input
                    type="date"
                    aria-label={t("fees.editor.dueOnOf", { n: index + 1 })}
                    aria-invalid={Boolean(errors.lines?.[index]?.due_on)}
                    className="min-h-8"
                    {...form.register(`lines.${index}.due_on`)}
                  />
                </td>
                <td className="text-right">
                  {kind !== "single" && lines.fields.length > 1 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={t("fees.editor.remove", { n: index + 1 })}
                      onClick={() => lines.remove(index)}
                    >
                      <Icon name="x" size={16} />
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="font-bold">{t("fees.editor.sum")}</td>
              <td className="num font-bold">{sum === null ? "—" : formatAmount(sum, currency)}</td>
              <td colSpan={2} className="text-sm">
                {sum !== null && totalMinor !== null && sum === totalMinor ? (
                  <span className="text-ok">{t("fees.editor.sumOk")}</span>
                ) : (
                  totalMinor !== null && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const current = form.getValues("lines");
                        const spreadLines = spread(
                          current.map((row) => ({ ...row, amount_minor: null })),
                          totalMinor,
                        );
                        lines.replace(toRows(spreadLines, currency));
                      }}
                    >
                      {t("fees.editor.spread")}
                    </Button>
                  )
                )}
              </td>
            </tr>
          </tfoot>
        </Table>
        <CardFooter className="flex-wrap gap-2">
          {kind !== "single" && (
            <Button
              variant="outline"
              className="mr-auto"
              onClick={() =>
                lines.append({ label: nth(lines.fields.length + 1), amount: "", due_on: "" })
              }
            >
              <Icon name="plus" size={16} />
              {t("fees.editor.add")}
            </Button>
          )}
          {rule && (
            <Button variant="outline" onClick={() => setConfirmDelete(true)}>
              {t("fees.editor.delete")}
            </Button>
          )}
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {t("common.save")}
          </Button>
        </CardFooter>
      </form>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("fees.editor.deleteTitle")}
        confirmLabel={t("fees.editor.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      >
        {t("fees.editor.deleteText")}
      </ConfirmDialog>
    </Card>
  );
}
