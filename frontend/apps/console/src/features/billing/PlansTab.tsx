// Offres (ABO.1) : modules compris, prix par élève inscrit et par période. Un plan retiré de la
// vente reste lu par les contrats qui l'ont signé.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { CURRENCIES, formatAmountValue, parseAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  Field,
  Input,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { MODULES } from "../schools/ModulesCard";
import { money } from "./shared";

type Plan = Schemas["Plan"];
type PlanModule = Plan["modules"][number];
export const PLANS_KEY = ["console", "billing", "plans"];
const PLAN_MODULES: PlanModule[] = [...MODULES, "ai"];

export function PlansTab({ manage }: { manage: boolean }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  const plans = useQuery({
    queryKey: PLANS_KEY,
    queryFn: () => call(api.GET("/api/console/billing/plans/")),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.billing.plans.title")}</CardTitle>
        {manage && (
          <Button size="sm" variant="outline" onClick={() => setEditing("new")}>
            {t("console.billing.plans.new")}
          </Button>
        )}
      </CardHeader>
      {plans.isPending ? (
        <Skeleton label={t("console.billing.loading")} />
      ) : plans.isError ? (
        <Banner tone="due" className="m-4">
          {errorMessage(plans.error, t)}
        </Banner>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("console.billing.plans.name")}</th>
              <th>{t("console.billing.plans.modules")}</th>
              <th className="text-right">{t("console.billing.plans.price")}</th>
              <th>{t("console.billing.plans.sale")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {plans.data.results.map((plan) => (
              <tr key={plan.id}>
                <td data-label={t("console.billing.plans.name")}>
                  <b>{plan.name}</b>
                  <br />
                  <span className="text-sm text-ink-3">{plan.description}</span>
                </td>
                <td data-label={t("console.billing.plans.modules")}>
                  <div className="flex flex-wrap gap-1">
                    {plan.modules.map((m) => (
                      <Tag key={m}>{t(`console.schools.modules.${m}`)}</Tag>
                    ))}
                  </div>
                </td>
                <td
                  className="text-right whitespace-nowrap"
                  data-label={t("console.billing.plans.price")}
                >
                  {money(plan.price_per_student, plan.currency)} ·{" "}
                  {t(`console.billing.period.${plan.period}`)}
                </td>
                <td data-label={t("console.billing.plans.sale")}>
                  <StatusPill tone={plan.active ? "ok" : "gray"}>
                    {t(
                      plan.active
                        ? "console.billing.plans.onSale"
                        : "console.billing.plans.withdrawn",
                    )}
                  </StatusPill>
                </td>
                <td>
                  {manage && (
                    <Button size="sm" variant="ghost" onClick={() => setEditing(plan)}>
                      {t("console.billing.plans.edit")}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {editing && (
        <PlanDialog plan={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
    </Card>
  );
}

function PlanDialog({ plan, onClose }: { plan: Plan | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    code: plan?.code ?? "",
    name: plan?.name ?? "",
    description: plan?.description ?? "",
    currency: (plan?.currency ?? "USD") as Currency,
    price: plan ? formatAmountValue(plan.price_per_student, plan.currency as Currency) : "",
    period: plan?.period ?? "term",
    modules: plan?.modules ?? ([] as PlanModule[]),
    active: plan?.active ?? true,
  });
  const [bad, setBad] = useState(false);
  const save = useMutation({
    mutationFn: () => {
      const price = parseAmount(form.price, form.currency);
      if (price === null) {
        setBad(true);
        throw new Error("price");
      }
      const body = {
        code: form.code,
        name: form.name,
        description: form.description,
        currency: form.currency,
        period: form.period,
        modules: form.modules,
        active: form.active,
        price_per_student: price,
      };
      return plan
        ? call(
            api.PATCH("/api/console/billing/plans/{id}/", {
              params: { path: { id: plan.id } },
              body,
            }),
          )
        : call(api.POST("/api/console/billing/plans/", { body }));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PLANS_KEY });
      onClose();
    },
  });
  const text = (name: "code" | "name" | "description" | "price") => ({
    value: form[name],
    onChange: (e: { target: { value: string } }) => {
      setBad(false);
      setForm({ ...form, [name]: e.target.value });
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t(plan ? "console.billing.plans.editTitle" : "console.billing.plans.new")}
      confirmLabel={t("console.team.save")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => save.mutate()}
      pending={save.isPending}
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          <Field id="plan-name" label={t("console.billing.plans.name")} required>
            {(c) => <Input {...c} maxLength={80} {...text("name")} />}
          </Field>
          <Field id="plan-code" label={t("console.billing.plans.code")} required>
            {(c) => <Input {...c} maxLength={40} {...text("code")} />}
          </Field>
        </div>
        <Field id="plan-desc" label={t("console.billing.plans.description")}>
          {(c) => <Input {...c} maxLength={240} {...text("description")} />}
        </Field>
        <div className="grid gap-4 min-[600px]:grid-cols-3">
          <Field
            id="plan-price"
            label={t("console.billing.plans.price")}
            required
            error={bad ? t("console.billing.badAmount") : undefined}
          >
            {(c) => <Input {...c} inputMode="decimal" {...text("price")} />}
          </Field>
          <Field id="plan-currency" label={t("console.billing.currency")}>
            {(c) => (
              <Select
                {...c}
                value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value as Currency })}
              >
                {CURRENCIES.map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </Select>
            )}
          </Field>
          <Field id="plan-period" label={t("console.billing.plans.period")}>
            {(c) => (
              <Select
                {...c}
                value={form.period}
                onChange={(e) => setForm({ ...form, period: e.target.value as Plan["period"] })}
              >
                <option value="term">{t("console.billing.period.term")}</option>
                <option value="year">{t("console.billing.period.year")}</option>
              </Select>
            )}
          </Field>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-bold text-ink-2">
            {t("console.billing.plans.modules")}
          </legend>
          {PLAN_MODULES.map((code) => (
            <CheckboxField
              key={code}
              id={`plan-module-${code}`}
              label={t(`console.schools.modules.${code}`)}
              checked={form.modules.includes(code)}
              onCheckedChange={(on) =>
                setForm({
                  ...form,
                  modules: PLAN_MODULES.filter((m) =>
                    m === code ? on === true : form.modules.includes(m),
                  ),
                })
              }
            />
          ))}
        </fieldset>
        <CheckboxField
          id="plan-active"
          label={t("console.billing.plans.onSale")}
          checked={form.active}
          onCheckedChange={(on) => setForm({ ...form, active: on === true })}
        />
        {save.isError && !bad && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}
