// Crédits d'élèves (M14, 3.6.1) : argent reçu en trop — paiement hors ligne arrivé quand
// l'élève ne devait plus rien, réduction sur une échéance déjà payée. Lire : `view_reports` ou
// `approve_cancellation` ; utiliser : `approve_cancellation` (le serveur vérifie). Utiliser un
// crédit le répartit sur les échéances les plus anciennes de sa devise, sans paiement ni reçu
// d'argent ; un justificatif s'imprime. Crédit à la caisse : 3.6.2.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDate, formatDateTime, formatTime, useTranslation } from "@mwangaza/i18n";
import { formatAmount, sumAmounts, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Kpi,
  List,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import "../cash/receipt.css";

type Credit = Schemas["StudentCredit"];
type Detail = Schemas["StudentCreditDetail"];
type Filter = "to_process" | "used" | "all";
const PAGE_SIZE = 50;
const TONES = { to_process: "warn", used: "ok", voided: "gray" } as const;
const ORIGIN_TONES = { offline_surplus: "warn", discount: "info" } as const;

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

export function CreditsPage() {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const [filter, setFilter] = useState<Filter>("to_process");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const summary = useQuery({
    queryKey: [...keys.credits, "summary"],
    queryFn: () => call(api.GET("/api/student-credits/summary/")),
  });
  const credits = useQuery({
    queryKey: [...keys.credits, filter, page],
    queryFn: () =>
      call(
        api.GET("/api/student-credits/", {
          params: { query: { state: filter, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });

  if (credits.isError && !credits.data) {
    return <LoadError error={credits.error} onRetry={() => void credits.refetch()} />;
  }
  const results = credits.data?.results ?? [];
  const current = selected ?? results[0]?.id ?? null;
  const count = credits.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const toProcess = summary.data?.to_process ?? 0;
  const amounts = summary.data?.amounts ?? [];

  return (
    <>
      <PageHeader
        title={t("credits.title")}
        subtitle={t("credits.subtitle")}
        actions={
          <Segmented
            label={t("credits.filter")}
            value={filter}
            onValueChange={(next) => {
              setFilter(next);
              setPage(1);
              setSelected(null);
            }}
            options={[
              { value: "to_process", label: t("credits.filters.to_process", { count: toProcess }) },
              { value: "used", label: t("credits.filters.used") },
              { value: "all", label: t("credits.filters.all") },
            ]}
          />
        }
      />
      <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
        <Kpi
          label={t("credits.kpi.toProcess")}
          value={toProcess}
          sub={t("credits.kpi.toProcessSub")}
        />
        {school.enabled_currencies.map((currency) => {
          const row = amounts.find((item) => item.currency === currency);
          return (
            <Kpi
              key={currency}
              label={t("credits.kpi.amount", { currency: currency === "CDF" ? "FC" : currency })}
              value={money(row?.amount_minor ?? 0, currency)}
            />
          );
        })}
        <Kpi
          label={t("credits.kpi.usedThisMonth")}
          value={summary.data?.used_this_month ?? 0}
          sub={t("credits.kpi.usedSub")}
        />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          {!credits.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : results.length === 0 ? (
            <CardContent className="text-ink-3">{t(`credits.empty.${filter}`)}</CardContent>
          ) : (
            <CreditTable credits={results} selected={current} onSelect={setSelected} />
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(credits.data?.previous)}
            hasNext={Boolean(credits.data?.next)}
            onPage={setPage}
            summary={t("credits.range", {
              from,
              to: from ? from + results.length - 1 : 0,
              count,
            })}
          />
        </Card>
        {current ? (
          <CreditDetail key={current} id={current} />
        ) : (
          <Card>
            <CardContent className="text-ink-3">{t("credits.pick")}</CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

function Origin({ credit }: { credit: Credit }) {
  const { t } = useTranslation();
  return (
    <>
      <StatusPill tone={ORIGIN_TONES[credit.origin]}>
        {t(`credits.origins.${credit.origin}`)}
      </StatusPill>
      <span className="mt-1 block text-sm">
        {t(`credits.originDetail.${credit.origin}`, { register: credit.cash_register_name })}
      </span>
    </>
  );
}

function CreditTable({
  credits,
  selected,
  onSelect,
}: {
  credits: Credit[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("credits.columns.student")}</th>
          <th>{t("credits.columns.origin")}</th>
          <th className="text-right">{t("credits.columns.credit")}</th>
          <th>{t("credits.columns.since")}</th>
        </tr>
      </thead>
      <tbody>
        {credits.map((credit) => (
          <tr key={credit.id} aria-selected={credit.id === selected}>
            <td>
              <button
                type="button"
                onClick={() => onSelect(credit.id)}
                className="cursor-pointer text-left font-bold focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
              >
                {credit.student.full_name}
              </button>
              <span className="block text-sm text-ink-3">{credit.class_group}</span>
            </td>
            <td>
              <Origin credit={credit} />
            </td>
            <td className="num font-bold">{money(credit.amount_minor, credit.currency)}</td>
            <td className="text-sm whitespace-nowrap tabular-nums">
              {formatDate(credit.created_at, i18n.language, school.timezone).slice(0, 5)} ·{" "}
              {formatTime(credit.created_at, i18n.language, school.timezone)}
            </td>
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

function CreditDetail({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const client = useQueryClient();
  const [printing, setPrinting] = useState(false);
  const detail = useQuery({
    queryKey: [...keys.credits, "detail", id],
    queryFn: () => call(api.GET("/api/student-credits/{id}/", { params: { path: { id } } })),
  });
  const use = useMutation({
    mutationFn: () =>
      call(api.POST("/api/student-credits/{id}/use/", { params: { path: { id } } })),
    onSuccess: (credit) => {
      client.setQueryData([...keys.credits, "detail", id], credit);
      void client.invalidateQueries({ queryKey: keys.credits });
      void client.invalidateQueries({ queryKey: keys.students });
    },
  });

  if (detail.isError) {
    return <LoadError error={detail.error} onRetry={() => void detail.refetch()} />;
  }
  const credit = detail.data;
  if (!credit) {
    return (
      <Card>
        <CardContent>
          <Skeleton label={t("common.loading")} />
        </CardContent>
      </Card>
    );
  }
  const amount = (minor: number) => money(minor, credit.currency);
  const when = (iso: string) =>
    `${formatDate(iso, i18n.language, school.timezone).slice(0, 5)} · ${formatTime(iso, i18n.language, school.timezone)}`;
  const open = credit.state === "to_process";
  const canUse = can(me, ["finance.approve_cancellation"]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{credit.student.full_name}</CardTitle>
        <StatusPill tone={TONES[credit.state]}>{t(`credits.states.${credit.state}`)}</StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <List>
          {credit.receipt_number && (
            <Line label={t("credits.receipt", { number: credit.receipt_number })}>
              {when(credit.paid_at!)} · {credit.cash_register_name} ·{" "}
              <b>{amount(credit.amount_minor)}</b>
            </Line>
          )}
          {credit.discount_reason && (
            <Line
              label={t("credits.discount", {
                fee: credit.discount_fee_type ?? t("credits.allFees"),
              })}
            >
              {credit.discount_reason}
            </Line>
          )}
          <Line label={t("credits.columns.credit")}>
            <b>{amount(credit.amount_minor)}</b>
          </Line>
          {credit.allocations.map((part) => (
            <Line
              key={`${part.student_charge}-${part.created_at}`}
              label={`${t("credits.usedOn")} ${part.fee_type_name} · ${part.label}`}
            >
              {when(part.created_at)} · <b>{amount(part.amount_minor)}</b>
            </Line>
          ))}
          {credit.state !== "voided" && credit.used_minor > 0 && open && (
            <Line label={t("credits.left")}>
              <b>{amount(credit.remaining_minor)}</b>
            </Line>
          )}
        </List>
        <Banner
          tone={credit.state === "voided" ? "info" : "warn"}
          icon={credit.origin === "offline_surplus" ? "wifioff" : undefined}
        >
          {t(`credits.explain.${credit.state === "voided" ? "voided" : credit.origin}`)}
        </Banner>
        {open && (
          <>
            <h3 className="font-bold">{t("credits.whatToDo")}</h3>
            <div className="rounded-card border-2 border-lake bg-lake-50 p-3 text-sm">
              <b className="block">{t("credits.useOption")}</b>
              {credit.proposal.length ? (
                <>
                  {credit.proposal
                    .map(
                      (part) => `${part.fee_type_name} ${part.label} ${amount(part.amount_minor)}`,
                    )
                    .join(" · ")}{" "}
                  {t("credits.useOf", { amount: amount(credit.remaining_minor) })}
                </>
              ) : (
                t("credits.nothingOwed")
              )}
            </div>
            {credit.receipt_number && (
              <div className="rounded-card border border-line p-3 text-sm">
                <b className="block">{t("credits.refundOption")}</b>
                {t("credits.refundHelp", { number: credit.receipt_number })}
              </div>
            )}
            {use.error && <Banner tone="due">{errorMessage(use.error, t)}</Banner>}
            {canUse && (
              <div className="flex flex-wrap gap-2">
                {credit.receipt_number && (
                  <Button asChild variant="outline">
                    <Link to="/cancellations">{t("credits.requestCancellation")}</Link>
                  </Button>
                )}
                <Button
                  className="flex-1"
                  disabled={!credit.proposal.length || use.isPending}
                  onClick={() => use.mutate()}
                >
                  {t("credits.use")}
                </Button>
              </div>
            )}
          </>
        )}
        {credit.allocations.length > 0 && (
          <Button variant="outline" onClick={() => setPrinting(true)}>
            {t("credits.printProof")}
          </Button>
        )}
      </CardContent>
      {printing && <Proof credit={credit} onDone={() => setPrinting(false)} />}
    </Card>
  );
}

/** Justificatif d'utilisation (pas un reçu : aucun argent reçu), imprimé seul (`receipt.css`). */
function Proof({ credit, onDone }: { credit: Detail; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  useEffect(() => {
    window.print();
    onDone();
  }, [onDone]);
  const amount = (minor: number) => money(minor, credit.currency);
  const last = credit.allocations.at(-1)!;
  return createPortal(
    <div className="print-area">
      <div className="receipt-sheet receipt-sheet--a5">
        <div className="receipt-cell">
          <div className="receipt">
            <p>
              <b>{school.name}</b>
            </p>
            <p>
              <b>{t("credits.proof.title")}</b>
            </p>
            <p>
              {t("credits.proof.student")} : {credit.student.full_name} · {credit.student.matricule}{" "}
              · {credit.class_group}
            </p>
            <p>
              {t("credits.proof.origin")} : {t(`credits.origins.${credit.origin}`)}
              {credit.receipt_number &&
                ` · ${t("credits.receipt", { number: credit.receipt_number })}`}
            </p>
            <p>
              {t("credits.proof.credit")} : {amount(credit.amount_minor)}
            </p>
            {credit.allocations.map((part) => (
              <p key={`${part.student_charge}-${part.created_at}`}>
                {part.fee_type_name} · {part.label} : {amount(part.amount_minor)}
              </p>
            ))}
            <p>
              <b>
                {t("credits.proof.total")} :{" "}
                {amount(sumAmounts(credit.allocations.map((part) => part.amount_minor)))}
              </b>
            </p>
            <p>{t("credits.proof.note")}</p>
            <p>
              {t("credits.proof.by", {
                name: last.created_by ? fullName(last.created_by) : "",
                date: formatDateTime(last.created_at, i18n.language, school.timezone),
              })}
            </p>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
