// Factures des écoles (ABO.2) : émettre, encaisser à la main, annuler un paiement, annuler la
// facture par un avoir, relevé de l'école. Rien ne se modifie ni ne s'efface : chaque correction
// est une écriture liée, avec son motif, au journal de la plateforme.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { parseAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Select,
  Skeleton,
  StatusPill,
  Table,
  buttonVariants,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Pager } from "../shell/Pager";
import { money, pdfUrl, useDay } from "./shared";

type Invoice = Schemas["Invoice"];
const KEY = ["console", "billing", "invoices"];
const today = () => new Date().toISOString().slice(0, 10);

function state(
  invoice: Invoice,
  now: string,
): { tone: "ok" | "due" | "warn" | "gray" | "info"; key: string } {
  if (invoice.kind === "credit_note") return { tone: "gray", key: "creditNote" };
  if (invoice.cancelled) return { tone: "gray", key: "cancelled" };
  if (invoice.balance === 0) return { tone: "ok", key: "paid" };
  if (invoice.due_on < now) return { tone: "due", key: "late" };
  return { tone: "warn", key: invoice.paid > 0 ? "partial" : "open" };
}

export function InvoicesTab() {
  const { t } = useTranslation();
  const day = useDay();
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [opened, setOpened] = useState<string | null>(null);
  const invoices = useQuery({
    queryKey: [...KEY, page],
    queryFn: () => call(api.GET("/api/console/billing/invoices/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
  const now = today();
  const current = invoices.data?.results.find((i) => i.id === opened);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.billing.invoices.title")}</CardTitle>
        <Button size="sm" onClick={() => setCreating(true)}>
          {t("console.billing.invoices.new")}
        </Button>
      </CardHeader>
      {invoices.isPending ? (
        <Skeleton label={t("console.billing.loading")} />
      ) : invoices.isError ? (
        <Banner tone="due" className="m-4">
          {errorMessage(invoices.error, t)}
        </Banner>
      ) : invoices.data.results.length === 0 ? (
        <p className="p-4 text-md text-ink-3">{t("console.billing.invoices.empty")}</p>
      ) : (
        <>
          <Table stacked>
            <thead>
              <tr>
                <th>{t("console.billing.number")}</th>
                <th>{t("console.billing.school")}</th>
                <th>{t("console.billing.invoices.issued")}</th>
                <th>{t("console.billing.invoices.due")}</th>
                <th className="text-right">{t("console.billing.invoices.total")}</th>
                <th className="text-right">{t("console.billing.invoices.balance")}</th>
                <th>{t("console.billing.state")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {invoices.data.results.map((i) => {
                const s = state(i, now);
                return (
                  <tr key={i.id}>
                    <td data-label={t("console.billing.number")}>
                      <b>{i.number}</b>
                    </td>
                    <td data-label={t("console.billing.school")}>{i.school}</td>
                    <td data-label={t("console.billing.invoices.issued")}>{day(i.issued_on)}</td>
                    <td data-label={t("console.billing.invoices.due")}>{day(i.due_on)}</td>
                    <td
                      data-label={t("console.billing.invoices.total")}
                      className="text-right whitespace-nowrap"
                    >
                      {money(i.total, i.currency)}
                    </td>
                    <td
                      data-label={t("console.billing.invoices.balance")}
                      className="text-right whitespace-nowrap"
                    >
                      {money(i.balance, i.currency)}
                    </td>
                    <td data-label={t("console.billing.state")}>
                      <StatusPill tone={s.tone}>
                        {t(
                          `console.billing.invoices.status.${s.key}` as "console.billing.invoices.status.paid",
                        )}
                      </StatusPill>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1.5">
                        <Button size="sm" variant="ghost" onClick={() => setOpened(i.id)}>
                          {t("console.billing.invoices.open")}
                        </Button>
                        <a
                          href={pdfUrl("invoices", i.id)}
                          target="_blank"
                          rel="noreferrer"
                          className={buttonVariants({ variant: "ghost", size: "sm" })}
                        >
                          {t("console.billing.pdf")}
                        </a>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
          <Pager
            page={page}
            onPage={setPage}
            previous={invoices.data.previous}
            next={invoices.data.next}
          />
        </>
      )}
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
      {current && <InvoiceSheet invoice={current} onClose={() => setOpened(null)} />}
    </Card>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ contract: "", students: "", description: "", unit: "" });
  const [bad, setBad] = useState(false);
  const create = useMutation({
    mutationFn: () => {
      const lines = [];
      if (form.description.trim()) {
        const unit = parseAmount(form.unit, "USD");
        if (unit === null || unit < 1) {
          setBad(true);
          throw new Error("amount");
        }
        lines.push({ description: form.description.trim(), quantity: 1, unit_amount: unit });
      }
      return call(
        api.POST("/api/console/billing/invoices/", {
          body: {
            contract: form.contract.trim(),
            students: form.students ? Number(form.students) : undefined,
            lines: lines.length ? lines : undefined,
          },
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  const set = (name: keyof typeof form) => ({
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
      title={t("console.billing.invoices.new")}
      confirmLabel={t("console.billing.invoices.issue")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => create.mutate()}
      pending={create.isPending}
    >
      <div className="flex flex-col gap-4">
        <Field
          id="inv-contract"
          label={t("console.billing.invoices.contract")}
          help={t("console.billing.invoices.contractHelp")}
          required
        >
          {(c) => <Input {...c} autoComplete="off" {...set("contract")} />}
        </Field>
        <Field
          id="inv-students"
          label={t("console.billing.invoices.students")}
          help={t("console.billing.invoices.studentsHelp")}
        >
          {(c) => <Input {...c} type="number" min={0} {...set("students")} />}
        </Field>
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          <Field id="inv-desc" label={t("console.billing.invoices.extra")}>
            {(c) => <Input {...c} maxLength={200} {...set("description")} />}
          </Field>
          <Field
            id="inv-unit"
            label={t("console.billing.invoices.extraAmount")}
            error={bad ? t("console.billing.badAmount") : undefined}
          >
            {(c) => <Input {...c} inputMode="decimal" {...set("unit")} />}
          </Field>
        </div>
        {create.isError && !bad && <Banner tone="due">{errorMessage(create.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

/** Une facture ouverte : lignes, paiements, actions, relevé de l'école. */
function InvoiceSheet({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const { t } = useTranslation();
  const day = useDay();
  const [action, setAction] = useState<"pay" | "cancel" | { reverse: string } | "statement" | null>(
    null,
  );
  const s = state(invoice, today());
  const real = invoice.kind === "invoice" && !invoice.cancelled;
  return (
    <DialogRoot open onOpenChange={onClose}>
      <DialogContent
        title={`${invoice.number} · ${invoice.school}`}
        className="w-[min(760px,calc(100vw-32px))]"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            {real && (
              <Button variant="outline" className="text-due" onClick={() => setAction("cancel")}>
                {t("console.billing.invoices.cancel")}
              </Button>
            )}
            <Button variant="outline" onClick={() => setAction("statement")}>
              {t("console.billing.invoices.statement")}
            </Button>
            <DialogClose asChild>
              <Button>{t("console.billing.close")}</Button>
            </DialogClose>
          </div>
        }
      >
        <StatusPill tone={s.tone} className="w-fit">
          {t(`console.billing.invoices.status.${s.key}` as "console.billing.invoices.status.paid")}
        </StatusPill>
        <Table>
          <thead>
            <tr>
              <th>{t("console.billing.invoices.line")}</th>
              <th className="text-right">{t("console.billing.invoices.qty")}</th>
              <th className="text-right">{t("console.billing.invoices.unit")}</th>
              <th className="text-right">{t("console.billing.invoices.amount")}</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((l, n) => (
              <tr key={n}>
                <td>{l.description}</td>
                <td className="text-right">{l.quantity}</td>
                <td className="text-right whitespace-nowrap">
                  {money(l.unit_amount, invoice.currency)}
                </td>
                <td className="text-right whitespace-nowrap">
                  {money(l.amount, invoice.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        <div className="flex items-center justify-between">
          <b>{t("console.billing.invoices.payments")}</b>
          {real && invoice.balance > 0 && (
            <Button size="sm" variant="outline" onClick={() => setAction("pay")}>
              {t("console.billing.invoices.pay")}
            </Button>
          )}
        </div>
        {invoice.payments.length === 0 ? (
          <p className="text-md text-ink-3">{t("console.billing.invoices.noPayment")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line-soft text-md">
            {invoice.payments.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  {day(p.paid_on)} · {t(`console.billing.methods.${p.method}`)}
                  {p.reference && ` · ${p.reference}`}
                  {p.reverses && ` · ${t("console.billing.invoices.reversal")} — ${p.reason}`}
                </span>
                <span className="flex items-center gap-2">
                  <b>{money(p.amount, invoice.currency)}</b>
                  {!p.reverses && !invoice.payments.some((o) => o.reverses === p.id) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-due"
                      onClick={() => setAction({ reverse: p.id })}
                    >
                      {t("console.billing.invoices.reverse")}
                    </Button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="text-right">
          {t("console.billing.invoices.balance")} :{" "}
          <b>{money(invoice.balance, invoice.currency)}</b>
        </p>
        {action === "pay" && <PayDialog invoice={invoice} onClose={() => setAction(null)} />}
        {action === "cancel" && (
          <ReasonDialog
            invoice={invoice}
            title={t("console.billing.invoices.cancelTitle", { number: invoice.number })}
            text={t("console.billing.invoices.cancelText")}
            confirm={t("console.billing.invoices.cancelConfirm")}
            path="cancel"
            onClose={() => setAction(null)}
          />
        )}
        {typeof action === "object" && action && (
          <ReasonDialog
            invoice={invoice}
            title={t("console.billing.invoices.reverseTitle")}
            text={t("console.billing.invoices.reverseText")}
            confirm={t("console.billing.invoices.reverse")}
            path={action.reverse}
            onClose={() => setAction(null)}
          />
        )}
        {action === "statement" && (
          <StatementDialog code={invoice.school} onClose={() => setAction(null)} />
        )}
      </DialogContent>
    </DialogRoot>
  );
}

function PayDialog({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    amount: "",
    method: "bank" as Invoice["payments"][number]["method"],
    paid_on: today(),
    reference: "",
  });
  const [bad, setBad] = useState(false);
  const pay = useMutation({
    mutationFn: () => {
      const amount = parseAmount(form.amount, invoice.currency as Currency);
      if (amount === null || amount < 1) {
        setBad(true);
        throw new Error("amount");
      }
      return call(
        api.POST("/api/console/billing/invoices/{id}/pay/", {
          params: { path: { id: invoice.id } },
          body: { amount, method: form.method, paid_on: form.paid_on, reference: form.reference },
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.billing.invoices.pay")}
      confirmLabel={t("console.billing.invoices.payConfirm")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => pay.mutate()}
      pending={pay.isPending}
    >
      <div className="flex flex-col gap-4">
        <Field
          id="pay-amount"
          label={t("console.billing.invoices.amount")}
          help={t("console.billing.invoices.payHelp", {
            max: money(invoice.balance, invoice.currency),
          })}
          error={bad ? t("console.billing.badAmount") : undefined}
          required
        >
          {(c) => (
            <Input
              {...c}
              inputMode="decimal"
              value={form.amount}
              onChange={(e) => {
                setBad(false);
                setForm({ ...form, amount: e.target.value });
              }}
            />
          )}
        </Field>
        <Field id="pay-method" label={t("console.billing.invoices.method")}>
          {(c) => (
            <Select
              {...c}
              value={form.method}
              onChange={(e) => setForm({ ...form, method: e.target.value as typeof form.method })}
            >
              {(["bank", "mobile_money", "cash"] as const).map((m) => (
                <option key={m} value={m}>
                  {t(`console.billing.methods.${m}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          <Field id="pay-date" label={t("console.billing.invoices.paidOn")}>
            {(c) => (
              <Input
                {...c}
                type="date"
                value={form.paid_on}
                onChange={(e) => setForm({ ...form, paid_on: e.target.value })}
              />
            )}
          </Field>
          <Field id="pay-ref" label={t("console.billing.invoices.reference")}>
            {(c) => (
              <Input
                {...c}
                maxLength={80}
                value={form.reference}
                onChange={(e) => setForm({ ...form, reference: e.target.value })}
              />
            )}
          </Field>
        </div>
        {pay.isError && !bad && <Banner tone="due">{errorMessage(pay.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

/** Avoir complet (`path` = « cancel ») ou annulation d'un paiement (`path` = id du paiement) : motif obligatoire. */
function ReasonDialog({
  invoice,
  title,
  text,
  confirm,
  path,
  onClose,
}: {
  invoice: Invoice;
  title: string;
  text: string;
  confirm: string;
  path: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const send = useMutation({
    mutationFn: async () => {
      const params = { path: { id: invoice.id } };
      return path === "cancel"
        ? call(api.POST("/api/console/billing/invoices/{id}/cancel/", { params, body: { reason } }))
        : call(
            api.POST("/api/console/billing/invoices/{id}/payments/{payment}/reverse/", {
              params: { path: { id: invoice.id, payment: path } },
              body: { reason },
            }),
          );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={title}
      confirmLabel={confirm}
      cancelLabel={t("common.cancel")}
      onConfirm={() => reason.trim() && send.mutate()}
      pending={send.isPending}
      destructive
    >
      <div className="flex flex-col gap-4">
        <p>{text}</p>
        <Field id="reason" label={t("console.billing.invoices.reason")} required>
          {(c) => (
            <Input
              {...c}
              maxLength={200}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
        </Field>
        {send.isError && <Banner tone="due">{errorMessage(send.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

type Row = {
  date: string;
  kind: string;
  number: string;
  reference: string;
  debit: number;
  credit: number;
  balance: number;
};

function StatementDialog({ code, onClose }: { code: string; onClose: () => void }) {
  const { t } = useTranslation();
  const day = useDay();
  const statement = useQuery({
    queryKey: [...KEY, "statement", code],
    queryFn: () =>
      call(
        api.GET("/api/console/billing/statement/{code}/", { params: { path: { code } } }),
      ) as Promise<Record<string, Row[]>>,
  });
  return (
    <DialogRoot open onOpenChange={onClose}>
      <DialogContent
        title={t("console.billing.invoices.statementOf", { school: code })}
        className="w-[min(760px,calc(100vw-32px))]"
        footer={
          <DialogClose asChild>
            <Button>{t("console.billing.close")}</Button>
          </DialogClose>
        }
      >
        {statement.isPending ? (
          <Skeleton label={t("console.billing.loading")} />
        ) : statement.isError ? (
          <Banner tone="due">{errorMessage(statement.error, t)}</Banner>
        ) : Object.keys(statement.data).length === 0 ? (
          <p className="text-md text-ink-3">{t("console.billing.invoices.statementEmpty")}</p>
        ) : (
          Object.entries(statement.data).map(([currency, rows]) => (
            <Table key={currency}>
              <thead>
                <tr>
                  <th>{t("console.billing.invoices.date")}</th>
                  <th>{currency}</th>
                  <th className="text-right">{t("console.billing.invoices.debit")}</th>
                  <th className="text-right">{t("console.billing.invoices.credit")}</th>
                  <th className="text-right">{t("console.billing.invoices.running")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, n) => (
                  <tr key={n}>
                    <td>{day(r.date)}</td>
                    <td>
                      {t(
                        `console.billing.invoices.entry.${r.kind}` as "console.billing.invoices.entry.invoice",
                      )}{" "}
                      · {r.number}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      {r.debit ? money(r.debit, currency) : ""}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      {r.credit ? money(r.credit, currency) : ""}
                    </td>
                    <td className="text-right whitespace-nowrap">{money(r.balance, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ))
        )}
      </DialogContent>
    </DialogRoot>
  );
}
