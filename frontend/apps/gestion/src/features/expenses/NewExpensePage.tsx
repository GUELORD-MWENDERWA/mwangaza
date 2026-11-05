// Nouvelle dépense (FIN.1, maquette `depense-nouvelle`) : décrire la dépense et joindre la facture
// (photo ou PDF, 5 Mo). L'identifiant (UUID v7) est donné par l'appareil : un renvoi après une
// coupure ne crée pas de doublon. Au-dessus du seuil de l'école, la dépense attend une validation.
import { zodResolver } from "@hookform/resolvers/zod";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount, parseAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  StatusPill,
  Textarea,
} from "@mwangaza/ui";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { useCurrentSchool } from "../../lib/school";
import { schoolDay } from "../cash/offline";
import {
  ACCOUNTS,
  MAX_VOUCHER_BYTES,
  useCategories,
  useRecordExpense,
  useThresholds,
} from "./data";

export function NewExpensePage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const navigate = useNavigate();
  const categories = useCategories();
  const thresholds = useThresholds();
  const record = useRecordExpense();
  const fileInput = useRef<HTMLInputElement>(null);
  const [general, setGeneral] = useState<string | null>(null);
  // Même identifiant tant que la saisie n'a pas réussi : un double clic ne crée qu'une dépense.
  const [id] = useState(uuidv7);

  const schema = z.object({
    spent_on: z.string().min(1, t("expenses.errors.date")),
    category: z.string().min(1, t("expenses.errors.category")),
    beneficiary: z.string().trim().min(1, t("expenses.errors.beneficiary")).max(120),
    amount: z.string().min(1, t("expenses.errors.amount")),
    currency: z.enum(["USD", "CDF"]),
    account: z.enum(["cash", "bank", "mobile_money"]),
    reason: z.string().trim().min(1, t("expenses.errors.reason")).max(200),
    voucher: z
      .instanceof(File)
      .refine((file) => !(file.size > MAX_VOUCHER_BYTES), t("expenses.errors.voucherSize"))
      .nullable(),
  });
  type Values = z.infer<typeof schema>;
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      spent_on: schoolDay(school.timezone),
      category: "",
      beneficiary: "",
      amount: "",
      currency: "USD",
      account: "bank",
      reason: "",
      voucher: null,
    },
  });
  const { errors } = form.formState;
  const [currency, amountText, voucher, spentOn] = form.watch([
    "currency",
    "amount",
    "voucher",
    "spent_on",
  ]);
  const minor = parseAmount(amountText, currency as Currency);
  const limit =
    currency === "USD"
      ? thresholds.data?.usd_threshold_minor
      : thresholds.data?.cdf_threshold_minor;
  const needsApproval = minor !== null && limit !== undefined && minor > limit;

  const onSubmit = form.handleSubmit((value) => {
    const amount = parseAmount(value.amount, value.currency);
    if (amount === null || amount < 1) {
      form.setError("amount", { message: t("expenses.errors.amount") });
      return;
    }
    setGeneral(null);
    record.mutate(
      {
        id,
        category: value.category,
        beneficiary: value.beneficiary,
        reason: value.reason,
        amount_minor: amount,
        currency: value.currency,
        spent_on: value.spent_on,
        account: value.account,
        voucher: value.voucher,
      },
      {
        onSuccess: () => void navigate("/expenses"),
        onError: (error) =>
          setGeneral(
            applyServerErrors(
              error,
              ["category", "beneficiary", "reason", "currency", "spent_on", "account", "voucher"],
              form.setError,
              t,
            ),
          ),
      },
    );
  });

  return (
    <>
      <PageHeader
        title={t("expenses.newTitle")}
        subtitle={t("expenses.newSubtitle")}
        crumbs={
          <>
            <Link to="/expenses" className="text-lake underline">
              {t("expenses.title")}
            </Link>{" "}
            / {t("expenses.newTitle")}
          </>
        }
      />
      <form
        onSubmit={onSubmit}
        noValidate
        className="grid gap-4 min-[1000px]:grid-cols-[1.6fr_1fr]"
      >
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("expenses.sections.expense")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[700px]:grid-cols-2">
              <Field
                id="exp-date"
                label={t("expenses.fields.date")}
                required
                error={errors.spent_on?.message}
              >
                {(control) => <Input {...control} type="date" {...form.register("spent_on")} />}
              </Field>
              <Field
                id="exp-category"
                label={t("expenses.fields.category")}
                required
                error={errors.category?.message}
              >
                {(control) => (
                  <Select {...control} {...form.register("category")}>
                    <option value="">{t("expenses.fields.chooseCategory")}</option>
                    {(categories.data ?? [])
                      .filter((category) => category.is_active)
                      .map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                  </Select>
                )}
              </Field>
              <Field
                id="exp-beneficiary"
                label={t("expenses.fields.beneficiary")}
                required
                error={errors.beneficiary?.message}
              >
                {(control) => (
                  <Input {...control} maxLength={120} {...form.register("beneficiary")} />
                )}
              </Field>
              <Field
                id="exp-amount"
                label={t("expenses.fields.amount")}
                required
                error={errors.amount?.message}
              >
                {(control) => (
                  <Input {...control} inputMode="decimal" {...form.register("amount")} />
                )}
              </Field>
              <Field id="exp-currency" label={t("expenses.fields.currency")} required>
                {() => (
                  <Segmented
                    label={t("expenses.fields.currency")}
                    value={currency}
                    options={[
                      { value: "USD", label: "USD" },
                      { value: "CDF", label: "FC" },
                    ]}
                    onValueChange={(next) => form.setValue("currency", next)}
                  />
                )}
              </Field>
              <Field
                id="exp-account"
                label={t("expenses.fields.account")}
                required
                help={t("expenses.fields.accountHelp")}
              >
                {(control) => (
                  <Select {...control} {...form.register("account")}>
                    {ACCOUNTS.map((account) => (
                      <option key={account} value={account}>
                        {t(`expenses.account.${account}`)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field
                id="exp-reason"
                label={t("expenses.fields.reason")}
                required
                error={errors.reason?.message}
                className="min-[700px]:col-span-2"
              >
                {(control) => (
                  <Textarea {...control} rows={2} maxLength={200} {...form.register("reason")} />
                )}
              </Field>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("expenses.sections.voucher")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                capture="environment"
                className="hidden"
                aria-label={t("expenses.fields.voucher")}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  event.target.value = "";
                  if (file) form.setValue("voucher", file, { shouldValidate: true });
                }}
              />
              <Button
                type="button"
                variant="outline"
                className="h-auto min-w-0 flex-col py-5"
                onClick={() => fileInput.current?.click()}
              >
                <b>{voucher ? voucher.name : t("expenses.fields.pick")}</b>
                <span className="text-sm font-normal text-ink-3">
                  {t("expenses.fields.voucherHelp")}
                </span>
              </Button>
              {voucher && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="self-start"
                  onClick={() => form.setValue("voucher", null)}
                >
                  {t("expenses.fields.removeVoucher")}
                </Button>
              )}
              {errors.voucher?.message && (
                <span className="text-sm text-due" role="alert">
                  {errors.voucher.message}
                </span>
              )}
            </CardContent>
          </Card>
          {general && <Banner tone="due">{general}</Banner>}
          <div className="flex flex-wrap gap-2.5">
            <Button type="submit" disabled={record.isPending}>
              {t(needsApproval ? "expenses.submitApproval" : "expenses.submit")}
            </Button>
            <Button asChild variant="outline">
              <Link to="/expenses">{t("common.cancel")}</Link>
            </Button>
          </div>
        </div>
        <Card className="self-start">
          <CardHeader>
            <CardTitle>{t("expenses.sections.validation")}</CardTitle>
            <StatusPill tone={needsApproval ? "warn" : "ok"}>
              {t(needsApproval ? "expenses.aboveLimit" : "expenses.belowLimit")}
            </StatusPill>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            {thresholds.data && (
              <p>
                {t("expenses.limitText", {
                  usd: formatAmount(thresholds.data.usd_threshold_minor, "USD"),
                  cdf: formatAmount(thresholds.data.cdf_threshold_minor, "CDF"),
                })}
              </p>
            )}
            <p className="text-ink-3">
              {t(needsApproval ? "expenses.willBeApproved" : "expenses.paidDirectly", {
                date: formatDay(spentOn || schoolDay(school.timezone), i18n.language),
              })}
            </p>
          </CardContent>
        </Card>
      </form>
    </>
  );
}
