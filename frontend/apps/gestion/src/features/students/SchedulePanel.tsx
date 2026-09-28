// Échéancier particulier (E4, maquette `eleve-echeancier`) : ce qui reste dû pour un frais,
// réorganisé en versements de même total et de même devise. « Mensuel » propose les dates et
// les montants (tout reste modifiable) ; « Dates libres » laisse ajouter ou retirer des
// versements. Rien n'est envoyé si la somme diffère du reste (le serveur le vérifie aussi).
// Droit `finance.grant_discount` (route) ; motif obligatoire ; journal d'audit côté serveur.
import { api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
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
  CheckboxField,
  Field,
  Icon,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useFieldArray, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { everyMonth } from "../fees/schedule";
import { LoadError } from "../status/StatusPages";
import { type Charge, type Student, useCharges } from "./data";
import type { Scheduled } from "./StudentFinancesTab";

type Enrollment = Student["enrollments"][number];
type Mode = "monthly" | "free";
type Row = { amount: string; due_on: string };
type Values = { fee: string; reason: string; signed: boolean; count: string; first: string };
type Fee = { id: string; name: string; currency: Currency; charges: Charge[]; total: number };

/** Frais qui ont encore des échéances dues, dans l'ordre de la première échéance.
 *  3.1 : seulement celles pas encore payées, même en partie. */
function feesToReschedule(charges: Charge[]): Fee[] {
  const fees = new Map<string, Fee>();
  for (const charge of charges) {
    if (charge.status !== "active") continue;
    const fee = fees.get(charge.fee_type) ?? {
      id: charge.fee_type,
      name: charge.fee_type_name,
      currency: charge.currency as Currency,
      charges: [],
      total: 0,
    };
    fee.charges.push(charge);
    fee.total = sumAmounts([fee.total, charge.amount_minor]);
    fees.set(charge.fee_type, fee);
  }
  return [...fees.values()];
}

export function SchedulePanel({
  student,
  enrollment,
}: {
  student: Student;
  enrollment: Enrollment | undefined;
}) {
  const { t } = useTranslation();
  const charges = useCharges(enrollment?.id);
  if (charges.error)
    return <LoadError error={charges.error} onRetry={() => void charges.refetch()} />;
  if (!charges.data) return <Skeleton label={t("common.loading")} />;
  const fees = feesToReschedule(charges.data);
  if (!enrollment || enrollment.status !== "active" || fees.length === 0)
    return (
      <Banner tone="warn">
        {t("students.schedule.nothing")}{" "}
        <Link to={`/students/${student.id}/finances`} className="font-bold underline">
          {t("common.back")}
        </Link>
      </Banner>
    );
  return <ScheduleForm student={student} enrollment={enrollment} fees={fees} />;
}

function ScheduleForm({
  student,
  enrollment,
  fees,
}: {
  student: Student;
  enrollment: Enrollment;
  fees: Fee[];
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<Mode>("monthly");
  const [general, setGeneral] = useState<string | null>(null);
  const back = `/students/${student.id}/finances`;
  const lineLabel = (n: number) => t("students.schedule.line", { n });

  // Proposition de départ : autant de versements qu'aujourd'hui, à partir de la même date.
  const proposal = (fee: Fee, count: number, first: string): Row[] =>
    everyMonth(fee.total, count, first, lineLabel).map((line) => ({
      amount: formatAmountValue(line.amount_minor!, fee.currency),
      due_on: line.due_on,
    }));
  const [initial] = fees as [Fee];
  const form = useForm<Values & { lines: Row[] }>({
    defaultValues: {
      fee: initial.id,
      reason: "",
      signed: false,
      count: String(initial.charges.length),
      first: initial.charges[0]!.due_on,
      lines: proposal(initial, initial.charges.length, initial.charges[0]!.due_on),
    },
  });
  const lines = useFieldArray({ control: form.control, name: "lines" });
  const [feeId, rows] = useWatch({ control: form.control, name: ["fee", "lines"] });
  const fee = fees.find((candidate) => candidate.id === feeId) ?? initial;
  const amounts = rows.map((row) => parseAmount(row.amount, fee.currency));
  const sum = amounts.every((amount) => amount !== null) ? sumAmounts(amounts as number[]) : null;

  /** Mensuel : versements recalculés d'après le frais, leur nombre et la première date. */
  const propose = () => {
    const { count, first } = form.getValues();
    const n = Number(count);
    if (Number.isInteger(n) && n >= 1 && n <= 24 && first) lines.replace(proposal(fee, n, first));
  };
  const changeFee = (id: string) => {
    const next = fees.find((candidate) => candidate.id === id)!;
    form.setValue("fee", id);
    form.setValue("count", String(next.charges.length));
    form.setValue("first", next.charges[0]!.due_on);
    lines.replace(proposal(next, next.charges.length, next.charges[0]!.due_on));
  };

  const save = useMutation({
    mutationFn: (values: Values & { lines: Row[] }) =>
      call(
        api.POST("/api/student-charges/reschedule/", {
          body: {
            enrollment: enrollment.id,
            fee_type: fee.id,
            reason: values.reason.trim(),
            parent_signed: values.signed,
            installments: values.lines.map((line, index) => ({
              label: lineLabel(index + 1),
              amount_minor: parseAmount(line.amount, fee.currency)!,
              due_on: line.due_on,
            })),
          },
        }),
      ),
    onSuccess: async (_charges, values) => {
      await queryClient.invalidateQueries({ queryKey: keys.students });
      const scheduled: Scheduled = { fee: fee.name, count: values.lines.length };
      void navigate(back, { state: { scheduled } });
    },
    onError: (error) => setGeneral(firstErrorMessage(error, t)),
  });

  const submit = form.handleSubmit((values) => {
    setGeneral(null);
    let valid = true;
    if (!values.reason.trim()) {
      form.setError("reason", { message: t("fieldErrors.required") });
      valid = false;
    }
    values.lines.forEach((line, index) => {
      if (!parseAmount(line.amount, fee.currency)) {
        form.setError(`lines.${index}.amount`, { message: t("fees.editor.invalidAmount") });
        valid = false;
      }
      if (!line.due_on) {
        form.setError(`lines.${index}.due_on`, { message: t("fieldErrors.required") });
        valid = false;
      }
    });
    if (sum !== null && sum !== fee.total) {
      setGeneral(t("fieldErrors.schedule_total_mismatch"));
      valid = false;
    }
    if (valid) save.mutate(values);
  });
  const { errors } = form.formState;
  const money = (minor: number) => formatAmount(minor, fee.currency);

  return (
    <>
      <PageHeader title={t("students.schedule.title")} subtitle={t("students.schedule.intro")} />
      <form
        noValidate
        onSubmit={submit}
        className="grid items-start gap-4 min-[900px]:grid-cols-[1fr_1.3fr]"
      >
        <div className="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("students.schedule.today")}</CardTitle>
              <span className="text-sm text-ink-3">
                {fee.name} · {fee.currency}
              </span>
            </CardHeader>
            <Table>
              <thead>
                <tr>
                  <th>{t("students.schedule.columns.due")}</th>
                  <th className="text-right max-[599px]:hidden">
                    {t("students.schedule.columns.amount")}
                  </th>
                  <th className="text-right">{t("students.schedule.columns.left")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {fee.charges.map((charge) => (
                  <tr key={charge.id} aria-selected>
                    <td>
                      {charge.label} · {formatDay(charge.due_on, i18n.language)}
                    </td>
                    <td className="num max-[599px]:hidden">{money(charge.amount_minor)}</td>
                    <td className="num font-bold">{money(charge.amount_minor)}</td>
                    <td>
                      <StatusPill tone="warn">{t("students.schedule.toReplace")}</StatusPill>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td className="font-bold">{t("students.schedule.toReschedule")}</td>
                  <td className="max-[599px]:hidden" />
                  <td className="num font-bold">{money(fee.total)}</td>
                  <td />
                </tr>
              </tfoot>
            </Table>
          </Card>
          <Card>
            <CardContent className="grid gap-3">
              <Field
                id="schedule-fee"
                label={t("students.schedule.fee")}
                help={t("students.schedule.feeHelp")}
              >
                {(control) => (
                  <Controller
                    control={form.control}
                    name="fee"
                    render={({ field }) => (
                      <Select
                        {...control}
                        name={field.name}
                        value={field.value}
                        onChange={(event) => changeFee(event.target.value)}
                      >
                        {fees.map((option) => (
                          <option key={option.id} value={option.id}>
                            {t("students.schedule.feeOption", {
                              name: option.name,
                              amount: formatAmount(option.total, option.currency),
                            })}
                          </option>
                        ))}
                      </Select>
                    )}
                  />
                )}
              </Field>
              <Field
                id="schedule-reason"
                label={t("students.schedule.reason")}
                required
                error={errors.reason?.message}
              >
                {(control) => <Input {...control} maxLength={200} {...form.register("reason")} />}
              </Field>
              <Controller
                control={form.control}
                name="signed"
                render={({ field }) => (
                  <CheckboxField
                    id="schedule-signed"
                    label={t("students.schedule.signed")}
                    checked={field.value}
                    onCheckedChange={(checked) => field.onChange(checked === true)}
                  />
                )}
              />
            </CardContent>
          </Card>
        </div>
        <Card className="min-w-0">
          <CardHeader className="flex-wrap">
            <CardTitle>{t("students.schedule.plan")}</CardTitle>
            <Segmented
              label={t("students.schedule.mode")}
              value={mode}
              onValueChange={(next: Mode) => {
                setMode(next);
                if (next === "monthly") propose();
              }}
              options={(["free", "monthly"] as const).map((value) => ({
                value,
                label: t(`students.schedule.modes.${value}`),
              }))}
            />
          </CardHeader>
          {general && (
            <CardContent>
              <Banner tone="due">{general}</Banner>
            </CardContent>
          )}
          {mode === "monthly" && (
            <CardContent className="grid gap-3 min-[600px]:grid-cols-3">
              <Field id="schedule-count" label={t("students.schedule.count")}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    max={24}
                    className="num"
                    {...form.register("count", { onChange: propose })}
                  />
                )}
              </Field>
              <Field id="schedule-first" label={t("students.schedule.first")}>
                {(control) => (
                  <Input
                    {...control}
                    type="date"
                    {...form.register("first", { onChange: propose })}
                  />
                )}
              </Field>
              <Field id="schedule-amount" label={t("students.schedule.amount")}>
                {(control) => (
                  <div className="relative">
                    <Input
                      {...control}
                      readOnly
                      className="num pr-20"
                      value={amounts[0] ? money(amounts[0]) : ""}
                    />
                    <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-ink-3">
                      {t("students.schedule.computed")}
                    </span>
                  </div>
                )}
              </Field>
            </CardContent>
          )}
          <Table>
            <thead>
              <tr>
                <th>{t("students.schedule.label")}</th>
                <th>{t("students.schedule.dueOn")}</th>
                <th className="text-right">{t("students.schedule.amount")}</th>
                {mode === "free" && <th />}
              </tr>
            </thead>
            <tbody>
              {lines.fields.map((line, index) => (
                <tr key={line.id}>
                  <td>{lineLabel(index + 1)}</td>
                  <td>
                    <Input
                      type="date"
                      aria-label={t("students.schedule.dueOnOf", { n: index + 1 })}
                      aria-invalid={Boolean(errors.lines?.[index]?.due_on)}
                      className="min-h-8 min-w-[124px] px-2"
                      {...form.register(`lines.${index}.due_on`)}
                    />
                  </td>
                  <td>
                    <Input
                      aria-label={t("students.schedule.amountOf", { n: index + 1 })}
                      aria-invalid={Boolean(errors.lines?.[index]?.amount)}
                      inputMode="decimal"
                      className="num min-h-8 min-w-[72px] px-2"
                      {...form.register(`lines.${index}.amount`)}
                    />
                  </td>
                  {mode === "free" && (
                    <td className="text-right">
                      {lines.fields.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={t("students.schedule.remove", { n: index + 1 })}
                          onClick={() => lines.remove(index)}
                        >
                          <Icon name="x" size={16} />
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td className="font-bold">{t("students.schedule.total")}</td>
                <td className="text-sm">
                  {sum === fee.total ? (
                    <span className="text-ok">{t("students.schedule.totalOk")}</span>
                  ) : (
                    sum !== null && (
                      <span className="text-due">
                        {t("students.schedule.totalGap", {
                          amount: money(Math.abs(fee.total - sum)),
                        })}
                      </span>
                    )
                  )}
                </td>
                <td className="num font-bold">{sum === null ? "—" : money(sum)}</td>
                {mode === "free" && <td />}
              </tr>
            </tfoot>
          </Table>
          <CardFooter className="flex-wrap gap-2">
            {mode === "free" && (
              <Button variant="outline" onClick={() => lines.append({ amount: "", due_on: "" })}>
                <Icon name="plus" size={16} />
                {t("students.schedule.add")}
              </Button>
            )}
            <span className="mr-auto text-sm text-ink-3">{t("students.schedule.footer")}</span>
            <Button asChild variant="outline">
              <Link to={back}>{t("common.cancel")}</Link>
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {t("students.schedule.submit")}
            </Button>
          </CardFooter>
        </Card>
      </form>
    </>
  );
}
