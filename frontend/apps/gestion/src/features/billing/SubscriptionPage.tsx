// « Mon abonnement » (ABO.4, maquette `gestion/mon-abonnement`) : le contrat de l'école avec la
// plateforme, ses factures (PDF), le solde, la prochaine échéance et comment payer. Reste ouvert
// en lecture seule : c'est ici qu'on voit pourquoi et comment rouvrir. La demande d'un module en
// plus est rangée dans la console ; elle n'active ni ne facture rien.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import { formatAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardHeader,
  CardTitle,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type Invoice = Schemas["Invoice"];
const KEY = ["subscription"];
const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
const today = () => new Date().toISOString().slice(0, 10);

function state(invoice: Invoice, now: string) {
  if (invoice.kind === "credit_note") return { tone: "gray", key: "creditNote" } as const;
  if (invoice.cancelled) return { tone: "gray", key: "cancelled" } as const;
  if (invoice.balance === 0) return { tone: "ok", key: "paid" } as const;
  if (invoice.due_on < now) return { tone: "due", key: "late" } as const;
  return { tone: "warn", key: invoice.paid > 0 ? "partial" : "open" } as const;
}

export function SubscriptionPage() {
  const { t, i18n } = useTranslation();
  const [asking, setAsking] = useState(false);
  const day = (value: string) => formatDay(value, i18n.language);
  const summary = useQuery({
    queryKey: KEY,
    queryFn: () => call(api.GET("/api/subscription/")),
  });
  const invoices = useQuery({
    queryKey: [...KEY, "invoices"],
    queryFn: () => call(api.GET("/api/subscription/invoices/", {})),
  });
  const data = summary.data;
  const contract = data?.contract;
  const now = today();
  return (
    <>
      <PageHeader
        title={t("subscription.title")}
        subtitle={t("subscription.subtitle")}
        actions={
          <Button onClick={() => setAsking(true)} disabled={!contract}>
            {t("subscription.ask.open")}
          </Button>
        }
      />
      {summary.isPending && <Skeleton label={t("console.billing.loading")} />}
      {data && !contract && <Banner tone="info">{t("subscription.none")}</Banner>}
      {data && contract && (
        <div className="grid gap-3.5 sm:grid-cols-3">
          <Card>
            <div className="flex flex-col gap-1 p-4">
              <span className="text-sm text-ink-3">{t("subscription.offer")}</span>
              <b className="text-xl">{data.plan_name}</b>
              <span className="text-sm text-ink-3">
                {contract.number} · {t("subscription.until", { date: day(contract.end_date) })}
              </span>
            </div>
          </Card>
          <Card>
            <div className="flex flex-col gap-1 p-4">
              <span className="text-sm text-ink-3">{t("subscription.balance")}</span>
              <b className="text-xl">
                {data.balance.length
                  ? data.balance.map((b) => money(b.amount, b.currency)).join(" · ")
                  : money(0, contract.currency)}
              </b>
              {data.late && (
                <span className="self-start">
                  <StatusPill tone="due">{t("subscription.late")}</StatusPill>
                </span>
              )}
            </div>
          </Card>
          <Card>
            <div className="flex flex-col gap-1 p-4">
              <span className="text-sm text-ink-3">{t("subscription.nextDue")}</span>
              {data.next_due ? (
                <>
                  <b className="text-xl">{day(data.next_due.due_on)}</b>
                  <span className="text-sm text-ink-3">
                    {data.next_due.number} · {money(data.next_due.amount, data.next_due.currency)}
                  </span>
                </>
              ) : (
                <b className="text-xl">—</b>
              )}
            </div>
          </Card>
        </div>
      )}
      {data && contract && (
        <div className="grid gap-4 min-[900px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>{t("subscription.invoices.title")}</CardTitle>
              </CardHeader>
              {invoices.data && !invoices.data.results.length && (
                <p className="p-4 text-ink-3">{t("subscription.invoices.empty")}</p>
              )}
              {!!invoices.data?.results.length && (
                <Table stacked>
                  <thead>
                    <tr>
                      <th>{t("subscription.invoices.number")}</th>
                      <th>{t("subscription.invoices.issued")}</th>
                      <th>{t("subscription.invoices.due")}</th>
                      <th className="text-right">{t("subscription.invoices.total")}</th>
                      <th className="text-right">{t("subscription.invoices.balance")}</th>
                      <th>{t("subscription.invoices.state")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.data.results.map((invoice) => {
                      const s = state(invoice, now);
                      return (
                        <tr key={invoice.id}>
                          <td
                            className="whitespace-nowrap"
                            data-label={t("subscription.invoices.number")}
                          >
                            <b>{invoice.number}</b>
                          </td>
                          <td data-label={t("subscription.invoices.issued")}>
                            {day(invoice.issued_on)}
                          </td>
                          <td data-label={t("subscription.invoices.due")}>{day(invoice.due_on)}</td>
                          <td className="text-right" data-label={t("subscription.invoices.total")}>
                            {money(invoice.total, invoice.currency)}
                          </td>
                          <td
                            className="text-right"
                            data-label={t("subscription.invoices.balance")}
                          >
                            {money(invoice.balance, invoice.currency)}
                          </td>
                          <td data-label={t("subscription.invoices.state")}>
                            <StatusPill tone={s.tone}>
                              {t(`subscription.invoices.status.${s.key}`)}
                            </StatusPill>
                          </td>
                          <td>
                            <a
                              className={buttonVariants({ variant: "ghost", size: "sm" })}
                              href={`/api/subscription/invoices/${encodeURIComponent(invoice.id)}/pdf/`}
                            >
                              {t("subscription.pdf")}
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
              )}
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("subscription.modules")}</CardTitle>
              </CardHeader>
              <div className="flex flex-col gap-2 p-4">
                <div className="flex flex-wrap gap-1.5">
                  {contract.modules.map((m) => (
                    <Tag key={m}>{t(`console.schools.modules.${m as "students"}`)}</Tag>
                  ))}
                </div>
                {data.open_requests.length > 0 && (
                  <p className="text-sm text-ink-3">
                    {t("subscription.openRequests", {
                      modules: data.open_requests
                        .map((m) => t(`console.schools.modules.${m as "students"}`))
                        .join(", "),
                    })}
                  </p>
                )}
              </div>
            </Card>
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>{t("subscription.howToPay")}</CardTitle>
              </CardHeader>
              <div className="flex flex-col gap-2 p-4">
                <p className="whitespace-pre-line">
                  {data.payment_details || t("subscription.noPaymentDetails")}
                </p>
                <p className="text-sm text-ink-3">{t("subscription.payHelp")}</p>
              </div>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("subscription.contract")}</CardTitle>
              </CardHeader>
              <div className="p-4">
                <a
                  className={buttonVariants({ variant: "outline" })}
                  href="/api/subscription/contract/pdf/"
                >
                  {t("subscription.contractPdf")}
                </a>
              </div>
            </Card>
          </div>
        </div>
      )}
      {asking && contract && (
        <AskDialog owned={contract.modules} onClose={() => setAsking(false)} />
      )}
    </>
  );
}

const ALL_MODULES = [
  "students",
  "finance",
  "communication",
  "academics",
  "timetable",
  "ai",
  "portal",
  "notifications",
  "offline",
] as const;

function AskDialog({ owned, onClose }: { owned: readonly string[]; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const available = ALL_MODULES.filter((m) => !owned.includes(m));
  const [module, setModule] = useState<string>(available[0] ?? "");
  const [note, setNote] = useState("");
  const send = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/subscription/module-requests/", {
          body: { module, note } as Schemas["ModuleRequestCreateRequest"],
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("subscription.ask.title")}
        footer={
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="outline">{t("subscription.ask.cancel")}</Button>
            </DialogClose>
            <Button disabled={!module || send.isPending} onClick={() => send.mutate()}>
              {t("subscription.ask.send")}
            </Button>
          </div>
        }
      >
        {send.error && <Banner tone="due">{errorMessage(send.error, t)}</Banner>}
        <Field id="ask-module" label={t("subscription.ask.module")} required>
          {(c) => (
            <Select {...c} value={module} onChange={(e) => setModule(e.target.value)}>
              {available.map((m) => (
                <option key={m} value={m}>
                  {t(`console.schools.modules.${m}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field id="ask-note" label={t("subscription.ask.note")}>
          {(c) => (
            <Input {...c} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />
          )}
        </Field>
      </DialogContent>
    </DialogRoot>
  );
}
