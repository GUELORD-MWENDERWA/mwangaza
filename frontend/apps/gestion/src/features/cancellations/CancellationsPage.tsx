// Annulations de paiements (F7, maquette `annulations`) : un paiement n'est jamais supprimé, il
// est annulé avec motif et validation. En attente / validées / refusées ; à droite, la demande
// choisie. Valider ou refuser : `finance.approve_cancellation`, jamais sa propre demande (le
// serveur vérifie) ; validée, le reçu d'annulation (M15) s'imprime aussitôt. Sans ce droit, on
// ne voit que ses demandes. Venu de « Crédits d'élèves » (`?payment=`) : le dialogue de demande
// s'ouvre sur ce paiement. La validation se fait en ligne (la demande, elle, part aussi hors
// ligne depuis la caisse).
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDate, formatTime, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  List,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
  Textarea,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { useSearchParams } from "react-router";

import { errorMessage } from "../../lib/errors";
import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { type CancellationReceipt, useCancellationPrinter } from "./CancellationReceipt";
import { RequestDialog } from "./RequestDialog";

type Item = Schemas["CancellationRequest"];
type Status = Item["status"];
const PAGE_SIZE = 50;
const TONES = { pending: "warn", approved: "gray", rejected: "due" } as const;

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

function useCancellations(status: Status, page: number) {
  return useQuery({
    queryKey: [...keys.cancellations, status, page],
    queryFn: () =>
      call(
        api.GET("/api/cancellations/", {
          params: { query: { status, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** « 19/10 · 09:58 » dans le fuseau de l'école. */
function useWhen() {
  const { i18n } = useTranslation();
  const school = useCurrentSchool();
  return (iso: string) =>
    `${formatDate(iso, i18n.language, school.timezone).slice(0, 5)} · ${formatTime(iso, i18n.language, school.timezone)}`;
}

export function CancellationsPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const client = useQueryClient();
  const [status, setStatus] = useState<Status>("pending");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [done, setDone] = useState<CancellationReceipt | null>(null);
  const printer = useCancellationPrinter();
  const list = useCancellations(status, page);
  const pending = useCancellations("pending", 1);
  const [params, setParams] = useSearchParams();
  const asked = can(me, ["finance.request_cancellation"]) ? params.get("payment") : null;
  const payment = useQuery({
    queryKey: [...keys.payments, "one", asked],
    queryFn: () => call(api.GET("/api/payments/{id}/", { params: { path: { id: asked! } } })),
    enabled: Boolean(asked),
  });
  const reprint = useMutation({
    mutationFn: (id: string) =>
      call(api.POST("/api/cancellations/{id}/reprint/", { params: { path: { id } } })),
    onSuccess: (cancellation) =>
      printer.print({ cancellation, reprintedAt: new Date().toISOString() }),
  });

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const current = results.find((item) => item.id === selected) ?? results[0] ?? null;
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const closeRequest = () =>
    setParams(
      (previous) => {
        previous.delete("payment");
        return previous;
      },
      { replace: true },
    );

  return (
    <>
      <PageHeader
        title={t("cancellations.title")}
        subtitle={t("cancellations.subtitle")}
        actions={
          <Segmented
            label={t("cancellations.filter")}
            value={status}
            onValueChange={(next) => {
              setStatus(next);
              setPage(1);
              setSelected(null);
            }}
            options={[
              {
                value: "pending",
                label: t("cancellations.filters.pending", { count: pending.data?.count ?? 0 }),
              },
              { value: "approved", label: t("cancellations.filters.approved") },
              { value: "rejected", label: t("cancellations.filters.rejected") },
            ]}
          />
        }
      />
      {done?.cancellation && (
        <Banner tone="ok">
          <span className="flex flex-wrap items-center gap-3">
            <span className="flex-1">
              {t("cancellations.done", { number: done.cancellation.receipt_number })}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={reprint.isPending}
              onClick={() => reprint.mutate(done.id)}
            >
              {t("cancellations.reprint")}
            </Button>
          </span>
        </Banner>
      )}
      {reprint.error && <Banner tone="due">{errorMessage(reprint.error, t)}</Banner>}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card data-guide="cancellations-list">
          {!list.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : results.length === 0 ? (
            <CardContent className="text-ink-3">{t(`cancellations.empty.${status}`)}</CardContent>
          ) : (
            <RequestTable items={results} selected={current?.id ?? null} onSelect={setSelected} />
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(list.data?.previous)}
            hasNext={Boolean(list.data?.next)}
            onPage={setPage}
            summary={t("cancellations.range", {
              from,
              to: from ? from + results.length - 1 : 0,
              count,
            })}
          />
        </Card>
        {current ? (
          <RequestDetail
            key={current.id}
            item={current}
            onApproved={(receipt) => {
              setDone(receipt);
              printer.print({ cancellation: receipt });
            }}
            onReprint={() => reprint.mutate(current.id)}
          />
        ) : (
          <Card>
            <CardContent className="text-ink-3">{t("cancellations.pick")}</CardContent>
          </Card>
        )}
      </div>
      <RequestDialog
        payment={payment.data ?? null}
        onClose={closeRequest}
        onSent={() => {
          setStatus("pending");
          void client.invalidateQueries({ queryKey: keys.credits });
        }}
      />
      {printer.area}
    </>
  );
}

function RequestTable({
  items,
  selected,
  onSelect,
}: {
  items: Item[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  const when = useWhen();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("cancellations.columns.receipt")}</th>
          <th>{t("cancellations.columns.student")}</th>
          <th className="text-right">{t("cancellations.columns.amount")}</th>
          <th>{t("cancellations.columns.requestedBy")}</th>
          <th>{t("cancellations.columns.reason")}</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} aria-selected={item.id === selected}>
            <td>
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                className="cursor-pointer text-left font-bold whitespace-nowrap focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
              >
                {item.payment.receipt_number}
              </button>
              <span className="block text-sm text-ink-3 tabular-nums">
                {when(item.requested_at)}
              </span>
            </td>
            <td>
              {item.payment.student.full_name}
              <span className="block text-sm text-ink-3">{item.payment.class_group}</span>
            </td>
            <td className="num font-bold">
              {money(item.payment.received_amount_minor, item.payment.received_currency)}
            </td>
            <td>
              {fullName(item.requested_by)}
              <span className="block text-sm text-ink-3">{item.payment.cash_register_name}</span>
            </td>
            <td className="text-sm">{item.reason}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Line({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex-wrap text-sm">
      <span>{label}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}

function RequestDetail({
  item,
  onApproved,
  onReprint,
}: {
  item: Item;
  onApproved: (receipt: CancellationReceipt) => void;
  onReprint: () => void;
}) {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const client = useQueryClient();
  const when = useWhen();
  const [note, setNote] = useState("");
  const { payment } = item;
  const refresh = () =>
    Promise.all(
      [keys.cancellations, keys.payments, keys.credits, keys.students, keys.cashSession].map(
        (queryKey) => client.invalidateQueries({ queryKey }),
      ),
    );
  const approve = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/cancellations/{id}/approve/", {
          params: { path: { id: item.id } },
          body: { note },
        }),
      ),
    onSuccess: async (receipt) => {
      onApproved(receipt);
      await refresh();
    },
  });
  const reject = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/cancellations/{id}/reject/", {
          params: { path: { id: item.id } },
          body: { note },
        }),
      ),
    onSuccess: refresh,
  });
  const deciding = can(me, ["finance.approve_cancellation"]) && item.status === "pending";
  const own = item.requested_by.id === me.id;
  const error = approve.error ?? reject.error;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{payment.receipt_number}</CardTitle>
        <StatusPill tone={TONES[item.status]}>
          {t(`cancellations.states.${item.status}`)}
        </StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <List>
          <Line label={t("cancellations.student")}>
            <b>{payment.student.full_name}</b>
          </Line>
          <Line label={t("cancellations.amount")}>
            <b>{money(payment.received_amount_minor, payment.received_currency)}</b>{" "}
            {t("cancellations.cash")}
          </Line>
          <Line label={t("cancellations.allocation")}>
            {payment.allocations.map((line) => (
              <span key={line.student_charge} className="block">
                {line.fee_type_name} {line.label} {money(line.amount_minor, line.currency)}
              </span>
            ))}
          </Line>
          <Line label={t("cancellations.collectedBy")}>
            {fullName(payment.cashier)} · {when(payment.paid_at)}
          </Line>
          <Line label={t("cancellations.request.label")}>
            {fullName(item.requested_by)} · {when(item.requested_at)}
            {item.offline && ` · ${t("cancellations.offline")}`}
          </Line>
          <Line label={t("cancellations.request.reason")}>{item.reason}</Line>
          {item.decided_by && item.decided_at && (
            <Line label={t(`cancellations.decidedBy.${item.status}`)}>
              {fullName(item.decided_by)} · {when(item.decided_at)}
            </Line>
          )}
          {item.decision_note && <Line label={t("cancellations.note")}>{item.decision_note}</Line>}
          {item.cancellation && (
            <Line label={t("cancellations.receiptNumber")}>
              <b>{item.cancellation.receipt_number}</b>
            </Line>
          )}
        </List>
        {item.cancellation && (
          <Button variant="outline" onClick={onReprint}>
            {t("cancellations.reprint")}
          </Button>
        )}
        {deciding && own && <Banner tone="info">{t("cancellations.own")}</Banner>}
        {deciding && !own && (
          <>
            <Banner tone="info">{t("cancellations.afterApproval")}</Banner>
            <Field
              id="cancellation-note"
              label={t("cancellations.note")}
              help={t("cancellations.optional")}
            >
              {(control) => (
                <Textarea
                  rows={2}
                  maxLength={200}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  {...control}
                />
              )}
            </Field>
            {error && <Banner tone="due">{errorMessage(error, t)}</Banner>}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={reject.isPending || approve.isPending}
                onClick={() => reject.mutate()}
              >
                {t("cancellations.reject")}
              </Button>
              <Button
                className="flex-1"
                disabled={reject.isPending || approve.isPending}
                onClick={() => approve.mutate()}
              >
                {t("cancellations.approve")}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
