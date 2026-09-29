// Accorder une réduction (E3, maquette `eleve-reduction`) : modèle (motif), frais concernés ou
// tous, pourcentage (1 à 100) ou montant dans la devise du frais (jamais plus que le frais),
// motif obligatoire, et l'effet sur ce que doit l'élève, calculé comme le serveur. Retirer une
// réduction : avec un motif, rien n'est effacé. Droit `finance.grant_discount` ; qui, quand et
// journal d'audit côté serveur. « Déjà payé » et crédit de l'élève : avec la caisse (3.1).
import { api, call } from "@mwangaza/api";
import { formatDate, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  currencySymbol,
  formatAmount,
  parseAmount,
  sumAmounts,
  type Currency,
} from "@mwangaza/money";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Icon,
  Input,
  Segmented,
  Select,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { firstErrorMessage } from "../../lib/errors";
import { fullName, studentName } from "../../lib/people";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import {
  type Charge,
  DISCOUNT_REASONS,
  type Discount,
  type DiscountReason,
  type Student,
} from "./data";
import { chargesByFee, type DiscountRule, discountShares } from "./discounts";

type Enrollment = Student["enrollments"][number];
type Kind = Discount["kind"];
type Values = {
  reason_code: DiscountReason;
  fee: string;
  kind: Kind;
  value: string;
  reason: string;
};

const ALL = "all";

/** Saisie → pourcentage entier de 1 à 100, ou montant entier dans la devise ; null : refusée. */
function parseValue(kind: Kind, text: string, currency: Currency | undefined): number | null {
  if (kind === "amount") return currency ? parseAmount(text, currency) : null;
  if (!/^\d{1,3}$/.test(text.trim())) return null;
  const percent = Number.parseInt(text.trim(), 10);
  return percent >= 1 && percent <= 100 ? percent : null;
}

type Props = {
  student: Student;
  enrollment: Enrollment;
  charges: Charge[];
  discounts: Discount[];
  onClose: () => void;
  onGranted: () => void;
};

export function DiscountDialog(props: Props) {
  return (
    <DialogRoot open onOpenChange={(open) => !open && props.onClose()}>
      <DiscountForm {...props} />
    </DialogRoot>
  );
}

function DiscountForm({
  student,
  enrollment,
  charges,
  discounts,
  onGranted,
}: Omit<Props, "onClose">) {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const fees = chargesByFee(charges).map((group) => ({
    id: group[0]!.fee_type,
    name: group[0]!.fee_type_name,
    currency: group[0]!.currency as Currency,
    category: group[0]!.fee_category,
    total: sumAmounts(group.map((charge) => charge.amount_minor)),
  }));
  // Proposé d'abord : le minerval, que visent la plupart des réductions.
  const first = fees.find((candidate) => candidate.category === "tuition") ?? fees[0]!;
  const form = useForm<Values>({
    defaultValues: {
      reason_code: "other",
      fee: first.id,
      kind: "percent",
      value: "",
      reason: "",
    },
  });
  const [feeId, kind, text] = useWatch({ control: form.control, name: ["fee", "kind", "value"] });
  const fee = fees.find((candidate) => candidate.id === feeId);
  const value = parseValue(kind, text, fee?.currency);

  // Effet : parts avec les réductions déjà accordées, puis avec celle-ci en plus.
  const before = discountShares(charges, discounts);
  const draft: DiscountRule = {
    fee_type: fee?.id ?? null,
    kind,
    percent: kind === "percent" ? value : null,
    amount_minor: kind === "amount" ? value : null,
    currency: kind === "amount" && fee ? fee.currency : "",
    revoked_at: null,
  };
  const after = value === null ? before : discountShares(charges, [...discounts, draft]);
  const concerned = chargesByFee(charges).filter((group) => !fee || group[0]!.fee_type === fee.id);

  const grant = useMutation({
    mutationFn: (values: Values) =>
      call(
        api.POST("/api/discounts/", {
          body: {
            enrollment: enrollment.id,
            fee_type: fee?.id ?? null,
            kind: values.kind,
            ...(values.kind === "percent" ? { percent: value! } : { amount_minor: value! }),
            reason_code: values.reason_code,
            reason: values.reason.trim(),
          },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.students });
      onGranted();
    },
    onError: (error) => setGeneral(firstErrorMessage(error, t)),
  });

  const submit = form.handleSubmit((values) => {
    setGeneral(null);
    let valid = true;
    if (value === null || (kind === "amount" && fee && value > fee.total)) {
      const key = kind === "percent" ? "invalidPercent" : "invalidAmount";
      form.setError("value", { message: t(`students.discount.${key}`) });
      valid = false;
    }
    if (!values.reason.trim()) {
      form.setError("reason", { message: t("fieldErrors.required") });
      valid = false;
    }
    if (valid) grant.mutate(values);
  });
  const { errors } = form.formState;
  const reasonCode = useWatch({ control: form.control, name: "reason_code" });
  const changeKind = (next: Kind) => {
    form.setValue("kind", next);
    if (next === "amount" && form.getValues("fee") === ALL) form.setValue("fee", first.id);
  };
  const today = formatDate(new Date(), i18n.language, school.timezone);

  return (
    <DialogContent
      className="w-[min(760px,calc(100vw-32px))]"
      title={t("students.discount.title")}
      description={[
        studentName(student),
        enrollment.class_group_name,
        enrollment.academic_year_name,
      ].join(" · ")}
      footer={
        <>
          {me && (
            <span className="mr-auto self-center text-sm text-ink-3">
              {t("students.discount.grantedBy", { name: fullName(me), date: today })}
            </span>
          )}
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          <Button onClick={() => void submit()} disabled={grant.isPending}>
            {t("students.discount.submit")}
          </Button>
        </>
      }
    >
      <form className="flex flex-col gap-3" onSubmit={(event) => void submit(event)} noValidate>
        {general && <Banner tone="due">{general}</Banner>}
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-bold">{t("students.discount.template")}</legend>
          <div className="flex flex-wrap gap-2">
            {DISCOUNT_REASONS.map((code) => (
              <Button
                key={code}
                type="button"
                size="sm"
                variant={reasonCode === code ? "default" : "outline"}
                aria-pressed={reasonCode === code}
                onClick={() => form.setValue("reason_code", code)}
              >
                {reasonCode === code && <Icon name="check" size={14} />}
                {t(`students.discount.reasons.${code}`)}
              </Button>
            ))}
          </div>
        </fieldset>
        <div className="grid gap-3 min-[600px]:grid-cols-3">
          <Field
            id="discount-fee"
            label={t("students.discount.fee")}
            help={t("students.discount.feeHelp")}
          >
            {(control) => (
              <Select {...control} {...form.register("fee")}>
                {fees.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
                {kind === "percent" && (
                  <option value={ALL}>{t("students.discount.allFees")}</option>
                )}
              </Select>
            )}
          </Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-[.87rem] font-bold text-ink-2">
              {t("students.discount.kind")}
            </span>
            <Segmented
              label={t("students.discount.kind")}
              value={kind}
              onValueChange={changeKind}
              options={(["percent", "amount"] as const).map((option) => ({
                value: option,
                label: t(`students.discount.kinds.${option}`),
              }))}
            />
          </div>
          <Field
            id="discount-value"
            label={t("students.discount.value")}
            error={errors.value?.message}
          >
            {(control) => (
              <div className="relative">
                <Input
                  {...control}
                  inputMode="decimal"
                  className="pr-10"
                  {...form.register("value")}
                />
                <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-ink-3">
                  {kind === "percent" ? "%" : fee ? currencySymbol(fee.currency) : ""}
                </span>
              </div>
            )}
          </Field>
        </div>
        <Field
          id="discount-reason"
          label={t("students.discount.reason")}
          required
          error={errors.reason?.message}
        >
          {(control) => <Input {...control} maxLength={200} {...form.register("reason")} />}
        </Field>
        <section className="overflow-hidden rounded-card border border-line">
          <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
            <h3 className="font-bold">{t("students.discount.effect")}</h3>
            <span className="text-sm text-ink-3">
              {fee ? `${fee.name} · ${fee.currency}` : t("students.discount.allFees")}
            </span>
          </div>
          <Table>
            <thead>
              <tr>
                <th>{t("students.discount.columns.due")}</th>
                <th className="text-right">{t("students.discount.columns.before")}</th>
                <th className="text-right">{t("students.discount.columns.discount")}</th>
                <th className="text-right">{t("students.discount.columns.after")}</th>
                <th className="text-right">{t("students.discount.columns.paid")}</th>
                <th>{t("students.discount.columns.effect")}</th>
              </tr>
            </thead>
            {concerned.map((group) => {
              const currency = group[0]!.currency as Currency;
              const money = (minor: number) => formatAmount(minor, currency);
              const was = (charge: Charge) => charge.amount_minor - (before.get(charge.id) ?? 0);
              const cut = (charge: Charge) =>
                (after.get(charge.id) ?? 0) - (before.get(charge.id) ?? 0);
              const sum = (pick: (charge: Charge) => number) => sumAmounts(group.map(pick));
              // Payé au-delà du nouveau dû : crédit de l'élève (M14), jamais rendu d'office.
              const left = (charge: Charge) => was(charge) - cut(charge) - charge.paid_minor;
              return (
                <tbody key={group[0]!.id}>
                  {group.map((charge) => (
                    <tr key={charge.id}>
                      <td>
                        {charge.label === charge.fee_type_name
                          ? charge.label
                          : `${fee ? "" : `${charge.fee_type_name} · `}${charge.label}`}
                        <span className="block text-sm text-ink-3 tabular-nums">
                          {formatDay(charge.due_on, i18n.language)}
                        </span>
                      </td>
                      <td className="num">{money(was(charge))}</td>
                      <td className="num">{`− ${money(cut(charge))}`}</td>
                      <td className="num font-bold">{money(was(charge) - cut(charge))}</td>
                      <td className="num">{money(charge.paid_minor)}</td>
                      <td>
                        {left(charge) < 0 ? (
                          <StatusPill tone="info">
                            {t("students.discount.effects.credit", {
                              amount: money(-left(charge)),
                            })}
                          </StatusPill>
                        ) : (
                          <StatusPill tone="gray">
                            {t("students.discount.effects.rest", { amount: money(left(charge)) })}
                          </StatusPill>
                        )}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-surface font-bold">
                    <td>{t("students.discount.yearTotal", { fee: group[0]!.fee_type_name })}</td>
                    <td className="num">{money(sum(was))}</td>
                    <td className="num">{`− ${money(sum(cut))}`}</td>
                    <td className="num">{money(sum(was) - sum(cut))}</td>
                    <td className="num">{money(sum((charge) => charge.paid_minor))}</td>
                    <td />
                  </tr>
                </tbody>
              );
            })}
          </Table>
        </section>
      </form>
    </DialogContent>
  );
}

/** Retirer une réduction : motif obligatoire ; elle reste dans la liste, marquée retirée. */
export function RevokeDiscountDialog({
  discount,
  onClose,
}: {
  discount: Discount;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const revoke = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/discounts/{id}/revoke/", {
          params: { path: { id: discount.id } },
          body: { reason: reason.trim() },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.students });
      onClose();
    },
    onError: (failure) => setError(firstErrorMessage(failure, t)),
  });
  const submit = () => {
    if (!reason.trim()) setError(t("fieldErrors.required"));
    else revoke.mutate();
  };

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("students.discount.revokeTitle")}
        description={t("students.discount.revokeHelp")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button variant="destructive" onClick={submit} disabled={revoke.isPending}>
              {t("students.discount.revokeTitle")}
            </Button>
          </>
        }
      >
        <Field
          id="revoke-reason"
          label={t("students.discount.revokeReason")}
          required
          error={error ?? undefined}
        >
          {(control) => (
            <Input
              {...control}
              maxLength={200}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          )}
        </Field>
      </DialogContent>
    </DialogRoot>
  );
}
