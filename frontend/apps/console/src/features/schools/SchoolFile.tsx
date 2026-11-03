// Fiche d'une école, suite (CON.2, maquette `console/ecoles`) : contact (reçoit un e-mail à chaque
// changement d'état), contrat en cours, dernières factures, utilisation, notes internes et exports
// complets. Les droits sont ceux de la fiche : sans le droit de modifier, tout est en lecture.
import { api, call, type Schemas } from "@mwangaza/api";
import {
  applyServerErrors,
  errorMessage,
  formatDateTime,
  formatDay,
  useTranslation,
} from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  Input,
  StatusPill,
  Table,
  Textarea,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

type Detail = Schemas["ConsoleSchoolDetail"];

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
const EXPORT_TONES = { pending: "info", ready: "ok", failed: "due", expired: "gray" } as const;

type ContactValues = {
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  internal_notes: string;
};
const CONTACT_FIELDS = [
  "contact_name",
  "contact_phone",
  "contact_email",
  "internal_notes",
] as const satisfies readonly (keyof ContactValues)[];

export function ContactCard({
  school,
  readOnly,
  onSaved,
}: {
  school: Detail;
  readOnly: boolean;
  onSaved: (school: Detail) => void;
}) {
  const { t } = useTranslation();
  const form = useForm<ContactValues>({
    defaultValues: {
      contact_name: school.contact_name,
      contact_phone: school.contact_phone,
      contact_email: school.contact_email,
      internal_notes: school.internal_notes,
    },
  });
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (values: ContactValues) =>
      call(
        api.PATCH("/api/console/schools/{id}/", {
          params: { path: { id: school.id } },
          body: values,
        }),
      ),
    onSuccess: (data) => {
      setError(null);
      form.reset({
        contact_name: data.contact_name,
        contact_phone: data.contact_phone,
        contact_email: data.contact_email,
        internal_notes: data.internal_notes,
      });
      onSaved(data);
    },
    onError: (failure) =>
      setError(applyServerErrors(failure, [...CONTACT_FIELDS], form.setError, t)),
  });
  const message = (name: keyof ContactValues) =>
    form.getFieldState(name, form.formState).error?.message;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.contactTitle")}</CardTitle>
      </CardHeader>
      <form noValidate onSubmit={form.handleSubmit((values) => save.mutate(values))}>
        <CardContent className="grid gap-4">
          {error && <Banner tone="due">{error}</Banner>}
          <fieldset disabled={readOnly} className="grid min-w-0 gap-4">
            <Field
              id="contact-name"
              label={t("console.schools.contactName")}
              error={message("contact_name")}
            >
              {(control) => (
                <Input {...control} maxLength={120} {...form.register("contact_name")} />
              )}
            </Field>
            <Field
              id="contact-phone"
              label={t("console.schools.contactPhone")}
              error={message("contact_phone")}
            >
              {(control) => (
                <Input {...control} type="tel" maxLength={30} {...form.register("contact_phone")} />
              )}
            </Field>
            <Field
              id="contact-email"
              label={t("console.schools.contactEmail")}
              help={t("console.schools.contactEmailHelp")}
              error={message("contact_email")}
            >
              {(control) => (
                <Input
                  {...control}
                  type="email"
                  maxLength={254}
                  {...form.register("contact_email")}
                />
              )}
            </Field>
            <Field
              id="internal-notes"
              label={t("console.schools.notes")}
              help={t("console.schools.notesHelp")}
              error={message("internal_notes")}
            >
              {(control) => (
                <Textarea
                  {...control}
                  rows={4}
                  maxLength={4000}
                  {...form.register("internal_notes")}
                />
              )}
            </Field>
          </fieldset>
        </CardContent>
        {!readOnly && (
          <CardFooter>
            <Button type="submit" disabled={save.isPending}>
              {t("console.schools.saveContact")}
            </Button>
          </CardFooter>
        )}
      </form>
    </Card>
  );
}

export function ContractCard({ school }: { school: Detail }) {
  const { t, i18n } = useTranslation();
  const { contract, invoices } = school;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.contractTitle")}</CardTitle>
      </CardHeader>
      {contract ? (
        <CardContent className="grid gap-1">
          <p>
            <b>{contract.number}</b> · {contract.plan}
          </p>
          <p className="text-sm text-ink-3">
            {t("console.schools.contractLine", {
              start: formatDay(contract.start_date, i18n.language),
              end: formatDay(contract.end_date, i18n.language),
              price: money(contract.price_per_student, contract.currency),
            })}
            {contract.auto_renew ? ` · ${t("console.business.auto")}` : ""}
          </p>
        </CardContent>
      ) : (
        <p className="px-4 py-4 text-ink-3">{t("console.schools.noContract")}</p>
      )}
      {invoices.length > 0 && (
        <Table>
          <thead>
            <tr>
              <th>{t("console.schools.invoiceNumber")}</th>
              <th>{t("console.schools.invoiceDue")}</th>
              <th className="text-right">{t("console.schools.invoiceTotal")}</th>
              <th className="text-right">{t("console.schools.invoiceBalance")}</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.number}>
                <td className="whitespace-nowrap">{invoice.number}</td>
                <td className="whitespace-nowrap">{formatDay(invoice.due_on, i18n.language)}</td>
                <td className="text-right whitespace-nowrap tabular-nums">
                  {money(invoice.total, invoice.currency)}
                </td>
                <td className="text-right whitespace-nowrap tabular-nums">
                  {invoice.balance > 0 ? (
                    <StatusPill tone="due">{money(invoice.balance, invoice.currency)}</StatusPill>
                  ) : (
                    money(0, invoice.currency)
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

export function UsageCard({ school }: { school: Detail }) {
  const { t, i18n } = useTranslation();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const { usage } = school;
  const when = (value: string | null | undefined) =>
    value ? formatDateTime(value, i18n.language, timeZone) : "—";
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.usageTitle")}</CardTitle>
      </CardHeader>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 px-4 pt-3 pb-4 text-md [&_dt]:text-ink-3">
        <dt>{t("console.schools.students")}</dt>
        <dd className="tabular-nums">{usage.students.toLocaleString(i18n.language)}</dd>
        <dt>{t("console.schools.accounts")}</dt>
        <dd className="tabular-nums">{usage.accounts}</dd>
        <dt>{t("console.schools.lastActivity")}</dt>
        <dd>{when(usage.last_activity_at)}</dd>
        <dt>{t("console.schools.lastSync")}</dt>
        <dd>{when(usage.last_sync_at)}</dd>
      </dl>
    </Card>
  );
}

export function ExportsCard({
  school,
  canManage,
  onRequested,
}: {
  school: Detail;
  canManage: boolean;
  onRequested: (school: Detail) => void;
}) {
  const { t, i18n } = useTranslation();
  const request = useMutation({
    mutationFn: () =>
      call(api.POST("/api/console/schools/{id}/export/", { params: { path: { id: school.id } } })),
    onSuccess: onRequested,
  });
  const preparing = school.exports.some((item) => item.state === "pending");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.exportsTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-sm text-ink-3">{t("console.schools.exportsHelp")}</p>
        {request.isError && <Banner tone="due">{errorMessage(request.error, t)}</Banner>}
        {canManage && (
          <Button
            variant="outline"
            className="w-fit"
            disabled={request.isPending || preparing}
            onClick={() => request.mutate()}
          >
            {t("console.schools.exportRequest")}
          </Button>
        )}
        <ul className="m-0 grid list-none gap-2 p-0">
          {school.exports.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm">
                {formatDay(item.created_at.slice(0, 10), i18n.language)}
              </span>
              <StatusPill tone={EXPORT_TONES[item.state]}>
                {t(`console.schools.exportState.${item.state}`)}
                {item.state === "ready" && item.expires_at
                  ? ` · ${t("console.schools.exportUntil", { day: formatDay(item.expires_at.slice(0, 10), i18n.language) })}`
                  : ""}
              </StatusPill>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
