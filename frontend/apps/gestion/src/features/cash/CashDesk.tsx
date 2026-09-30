// Accueil de la caisse ouverte (maquette `caisse-accueil`) : recherche de l'élève, totaux de la
// session par devise (jamais additionnés), paiements de la session ; un élève choisi → encaissement
// (`CollectPanel`), dont le reçu s'imprime aussitôt ; « Réimprimer » : duplicata noté au journal.
// Clavier : Ctrl K rechercher, Échap changer d'élève. Appareil mémorisé (`device`) : recherche,
// totaux et paiements lus sur l'appareil, encaissements de la file compris (3.5.1), duplicata
// fait sur l'appareil (3.5.2) ; « Annuler… » : demande d'annulation (3.8.1, par la file sur un
// appareil mémorisé) ; clôture : 3.8.2.
import { api, call } from "@mwangaza/api";
import { formatTime, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount, formatRate } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { fullName, studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import type { LocalDb } from "../../lib/sync/db";
import { useSettled } from "../../lib/settled";
import { Pagination } from "../shell/Pagination";
import { RequestDialog } from "../cancellations/RequestDialog";
import { LoadError } from "../status/StatusPages";
import { type StudentRow, useStudentSearch } from "../students/data";
import { RateBanner } from "./CashPage";
import { ClosingPanel, type Slip } from "./Closing";
import { type Chosen, CollectPanel } from "./CollectPanel";
import { type CurrentSession, useSessionPayments } from "./data";
import { type LocalCash, queueReprint } from "./localData";
import {
  duplicateReceipt,
  type SessionPayment,
  searchEnrollments,
  sessionPayments,
  sessionTotals,
} from "./offline";
import { type Receipt, useReceiptPrinter } from "./Receipt";

type Session = NonNullable<CurrentSession["session"]>;

/** Caisse d'un appareil mémorisé : sa base, son préfixe et ce qu'elle contient. */
export type DeviceCash = { db: LocalDb; prefix: string; local: LocalCash };

type Found = { id: string; name: string; detail: string; chosen: Chosen | null };

const SHOWN = 8;
const RECENT = 3;

const currencyName = (currency: string) => (currency === "CDF" ? "FC" : currency);

function chosenFrom(student: StudentRow): Chosen | null {
  if (!student.enrollment) return null;
  return {
    enrollment: student.enrollment.id,
    name: studentName(student),
    matricule: student.matricule,
    classGroup: student.enrollment.class_group_name,
    guardian: student.primary_guardian,
  };
}

export function CashDesk({
  current,
  session,
  device,
  onClosed,
}: {
  current: CurrentSession;
  session: Session;
  device?: DeviceCash;
  /** Caisse clôturée (3.8.2) : le bordereau s'imprime à l'écran suivant. */
  onClosed: (slip: Slip) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const rows = device
    ? sessionPayments(device.local.enrollments, device.local.queued, session.id)
    : undefined;
  const totals = rows ? sessionTotals(rows) : current.totals;
  // Appareil mémorisé : duplicata fait ici, avec ou sans réseau, noté au journal par la file
  // (3.5.2) ; sinon par le serveur. Jamais pour un paiement annulé ou refusé.
  const reprintable = (id: string) =>
    !rows ||
    rows.some((row) => row.payment.id === id && row.sync !== "rejected" && !row.payment.cancelled);
  const [chosen, setChosen] = useState<Chosen | null>(null);
  const [recorded, setRecorded] = useState<Receipt | null>(null);
  const [cancelling, setCancelling] = useState<SessionPayment["payment"] | null>(null);
  const [closing, setClosing] = useState(false);
  const canCancel = can(useCurrentMe(), ["finance.request_cancellation"]);
  const searchRef = useRef<HTMLInputElement>(null);
  const printer = useReceiptPrinter();
  const reprint = useMutation({
    mutationFn: async (id: string) => {
      const reprintedAt = new Date().toISOString();
      if (!device) {
        const payment = await call(
          api.POST("/api/payments/{id}/reprint/", { params: { path: { id } } }),
        );
        return { payment, reprintedAt };
      }
      const { byId, queued, config } = device.local;
      const row = rows?.find((item) => item.payment.id === id);
      const enrollment = row && byId.get(row.payment.enrollment);
      const payment =
        enrollment && duplicateReceipt(enrollment, id, queued, config, school.timezone);
      if (!payment) throw new Error(`Payment ${id} is not on this device`);
      await queueReprint(device.db, id, reprintedAt);
      return { payment, reprintedAt };
    },
    onSuccess: ({ payment, reprintedAt }) => printer.print({ payment, reprintedAt }),
  });

  // Ctrl K : la recherche de la caisse, pas la recherche générale (qui laisse faire).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setChosen(null);
        requestAnimationFrame(() => searchRef.current?.focus());
      } else if (event.key === "Escape" && chosen && !document.querySelector("[role=dialog]")) {
        setChosen(null);
        requestAnimationFrame(() => searchRef.current?.focus());
      }
    };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [chosen]);

  const count = totals.reduce((total, item) => total + item.count, 0);
  if (closing)
    return (
      <ClosingPanel
        session={session}
        device={device}
        onBack={() => setClosing(false)}
        onClosed={onClosed}
      />
    );
  const choose = (next: Chosen) => {
    setRecorded(null);
    setChosen(next);
  };

  return (
    <>
      <PageHeader
        title={session.cash_register.name}
        subtitle={t("cash.desk.subtitle", {
          time: formatTime(session.opened_at, i18n.language, school.timezone),
          name: fullName(session.cashier),
          count,
        })}
        actions={
          <>
            {school.enabled_currencies.length > 1 && current.rate && (
              <span className="rounded-field border border-line bg-card px-3 py-2 text-sm tabular-nums">
                {t("cash.rate", { rate: formatRate(current.rate) })}
              </span>
            )}
            <Button variant="outline" onClick={() => setClosing(true)}>
              <Icon name="lock" size={18} />
              {t("cash.closing.open")}
            </Button>
          </>
        }
      />
      <RateBanner current={current} />
      {printer.area}
      <RequestDialog payment={cancelling} db={device?.db} onClose={() => setCancelling(null)} />
      {recorded && (
        <Banner tone="ok" role="status">
          <span className="flex-1">
            {t("cash.desk.recorded", { number: recorded.receipt_number })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={reprint.isPending || !reprintable(recorded.id)}
            onClick={() => reprint.mutate(recorded.id)}
          >
            <Icon name="print" size={16} />
            {t("cash.desk.reprint")}
          </Button>
        </Banner>
      )}
      {reprint.error && <Banner tone="due">{firstErrorMessage(reprint.error, t)}</Banner>}
      {chosen ? (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center gap-3 text-[1.1rem]">
              <Icon name="search" size={22} />
              <b className="min-w-0 flex-1">
                {[chosen.name, chosen.matricule, chosen.classGroup].join(" · ")}
              </b>
              <Button variant="outline" size="sm" onClick={() => setChosen(null)}>
                {t("cash.desk.change")}
                <kbd className="hidden min-[900px]:inline">{t("cash.desk.escape")}</kbd>
              </Button>
            </CardContent>
          </Card>
          <CollectPanel
            key={chosen.enrollment}
            chosen={chosen}
            rate={current.rate}
            session={session}
            device={device}
            onRecorded={(payment) => {
              setRecorded(payment);
              setChosen(null);
              printer.print({ payment });
            }}
          />
        </>
      ) : (
        <>
          <StudentSearch inputRef={searchRef} onChoose={choose} device={device} />
          <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
            {school.enabled_currencies.map((currency) => {
              const total = totals.find((item) => item.currency === currency);
              return (
                <Kpi
                  key={currency}
                  label={t("cash.desk.collected", { currency: currencyName(currency) })}
                  value={formatAmount(total?.amount_minor ?? 0, currency as Currency)}
                  sub={t("cash.desk.collectedCount", { count: total?.count ?? 0 })}
                />
              );
            })}
          </div>
          <SessionPayments
            session={session.id}
            rows={rows}
            onChoose={choose}
            onReprint={(id) => reprint.mutate(id)}
            canReprint={(id) => !reprint.isPending && reprintable(id)}
            onCancel={canCancel ? setCancelling : undefined}
          />
        </>
      )}
    </>
  );
}

function StudentSearch({
  inputRef,
  onChoose,
  device,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>;
  onChoose: (chosen: Chosen) => void;
  device?: DeviceCash;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const search = useSettled(text.trim());
  const found = useStudentSearch(device ? "" : search);
  let results: Found[] | undefined = [];
  if (search.length >= 2 && device) {
    const classes = new Map(device.local.config?.class_groups.map((item) => [item.id, item.name]));
    results = searchEnrollments(device.local.enrollments, search, SHOWN).map((enrollment) => {
      const name = studentName(enrollment.student);
      const classGroup = classes.get(enrollment.class_group) ?? "";
      const { matricule } = enrollment.student;
      return {
        id: enrollment.id,
        name,
        detail: [matricule, classGroup].join(" · "),
        chosen: { enrollment: enrollment.id, name, matricule, classGroup, guardian: null },
      };
    });
  } else if (search.length >= 2) {
    results = found.data?.results.slice(0, SHOWN).map((student) => ({
      id: student.id,
      name: studentName(student),
      detail: [
        student.matricule,
        student.enrollment?.class_group_name ?? t("cash.desk.notEnrolled"),
      ].join(" · "),
      chosen: chosenFrom(student),
    }));
  }
  const first = results?.find((result) => result.chosen)?.chosen;

  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <label className="flex min-h-[54px] items-center gap-3 rounded-field border-2 border-lake bg-card px-3 text-[1.2rem]">
          <Icon name="search" size={22} />
          <input
            ref={inputRef}
            autoFocus
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && first) onChoose(first);
            }}
            aria-label={t("cash.desk.searchLabel")}
            placeholder={t("cash.desk.search")}
            className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-ink-3"
          />
          <kbd className="hidden text-sm text-ink-3 min-[900px]:inline">
            {t("shell.search.shortcut")}
          </kbd>
        </label>
        {search.length >= 2 && results?.length === 0 && (
          <p className="text-sm text-ink-3">{t("cash.desk.noResult")}</p>
        )}
        {results && results.length > 0 && (
          <ul className="flex flex-col divide-y divide-line-soft">
            {results.map(({ id, name, detail, chosen }) => (
              <li key={id}>
                <button
                  type="button"
                  disabled={!chosen}
                  onClick={() => chosen && onChoose(chosen)}
                  className="flex w-full flex-wrap items-baseline gap-x-3 px-1 py-2.5 text-left hover:bg-surface disabled:cursor-not-allowed disabled:opacity-55"
                >
                  <b>{name}</b>
                  <span className="text-sm text-ink-3">{detail}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

const PAGE = 50;

/** Recherche dans les paiements de l'appareil : reçu, nom ou matricule. */
function matches(payment: SessionPayment["payment"], search: string): boolean {
  const text = search.toLowerCase();
  return [payment.receipt_number, payment.student.full_name, payment.student.matricule].some(
    (value) => value.toLowerCase().includes(text),
  );
}

function SessionPayments({
  session,
  rows,
  onChoose,
  onReprint,
  canReprint,
  onCancel,
}: {
  session: string;
  /** Paiements lus sur l'appareil ; sans eux, demandés au serveur. */
  rows?: SessionPayment[];
  onChoose: (chosen: Chosen) => void;
  onReprint: (id: string) => void;
  canReprint: (id: string) => boolean;
  /** Demander l'annulation (`finance.request_cancellation`) : paiement enregistré par le serveur,
   *  ni annulé, ni déjà en attente d'annulation. */
  onCancel?: (payment: SessionPayment["payment"]) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [text, setText] = useState("");
  const [page, setPage] = useState(1);
  const search = useSettled(text.trim());
  const payments = useSessionPayments(session, search, page, !rows);

  let data: { results: SessionPayment[]; count: number; previous: boolean; next: boolean } | null =
    null;
  if (rows) {
    const found = search ? rows.filter((row) => matches(row.payment, search)) : rows;
    data = {
      results: found.slice((page - 1) * PAGE, page * PAGE),
      count: found.length,
      previous: page > 1,
      next: page * PAGE < found.length,
    };
  } else if (payments.error) {
    return <LoadError error={payments.error} onRetry={() => void payments.refetch()} />;
  } else if (payments.data) {
    data = {
      results: payments.data.results.map((payment) => ({
        payment,
        sync: "recorded",
        error: null,
      })),
      count: payments.data.count,
      previous: Boolean(payments.data.previous),
      next: Boolean(payments.data.next),
    };
  }
  const results = data?.results ?? [];
  const from = results.length ? (page - 1) * PAGE + 1 : 0;
  // Derniers élèves servis (sans tuteur : la fiche complète est dans « Élèves »).
  const recent = search
    ? []
    : results
        .map((row) => row.payment)
        .filter(
          (payment, index, all) =>
            all.findIndex((other) => other.enrollment === payment.enrollment) === index,
        )
        .slice(0, RECENT);

  return (
    <>
      {recent.length > 0 && (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-ink-3">{t("cash.desk.recent")}</span>
          {recent.map((payment) => (
            <button
              key={payment.enrollment}
              type="button"
              onClick={() =>
                onChoose({
                  enrollment: payment.enrollment,
                  name: payment.student.full_name,
                  matricule: payment.student.matricule,
                  classGroup: payment.class_group,
                  guardian: null,
                })
              }
            >
              <Tag>{payment.student.full_name}</Tag>
            </button>
          ))}
        </p>
      )}
      <Card>
        <CardHeader className="flex-wrap">
          <CardTitle>{t("cash.payments.title")}</CardTitle>
          <Input
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setPage(1);
            }}
            aria-label={t("cash.payments.search")}
            placeholder={t("cash.payments.search")}
            className="min-[900px]:max-w-[320px]"
          />
        </CardHeader>
        {!data ? (
          <Skeleton label={t("common.loading")} />
        ) : results.length === 0 ? (
          <CardContent className="text-ink-3">
            {t(search ? "cash.payments.noMatch" : "cash.payments.empty")}
          </CardContent>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <th>{t("cash.payments.time")}</th>
                  <th>{t("cash.payments.receipt")}</th>
                  <th>{t("cash.payments.student")}</th>
                  <th className="text-right">{t("cash.payments.amount")}</th>
                  <th>{t("cash.payments.state")}</th>
                  <th>
                    <span className="sr-only">{t("cash.payments.reprint")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map(({ payment, sync, error }) => {
                  const amount = formatAmount(
                    payment.received_amount_minor,
                    payment.received_currency as Currency,
                  );
                  const struck = payment.cancelled || sync === "rejected";
                  return (
                    <tr key={payment.id}>
                      <td className="text-ink-3">
                        {formatTime(payment.paid_at, i18n.language, school.timezone)}
                      </td>
                      <td className="font-bold whitespace-nowrap">{payment.receipt_number}</td>
                      <td>
                        {payment.student.full_name}
                        <span className="block text-sm text-ink-3">{payment.class_group}</span>
                      </td>
                      <td className="text-right font-bold tabular-nums whitespace-nowrap">
                        {struck ? <s>{amount}</s> : amount}
                      </td>
                      <td>
                        <PaymentState payment={payment} sync={sync} />
                        {error && <span className="block text-sm text-due">{error.detail}</span>}
                      </td>
                      <td className="text-right whitespace-nowrap">
                        {!struck && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!canReprint(payment.id)}
                            aria-label={t("cash.payments.reprintLabel", {
                              number: payment.receipt_number,
                            })}
                            onClick={() => onReprint(payment.id)}
                          >
                            {t("cash.payments.reprint")}
                          </Button>
                        )}
                        {onCancel &&
                          !struck &&
                          sync === "recorded" &&
                          !payment.cancellation_pending && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="ml-2"
                              aria-label={t("cash.payments.cancelLabel", {
                                number: payment.receipt_number,
                              })}
                              onClick={() => onCancel(payment)}
                            >
                              {t("cash.payments.cancel")}
                            </Button>
                          )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            <Pagination
              page={page}
              hasPrevious={data.previous}
              hasNext={data.next}
              onPage={setPage}
              summary={t("cash.payments.range", {
                from,
                to: from + results.length - 1,
                count: data.count,
              })}
            />
          </>
        )}
      </Card>
    </>
  );
}

/** Annulé ; annulation demandée (compte encore) ; encaissé sur l'appareil et pas encore envoyé ;
 *  refusé par le serveur ; enregistré. */
function PaymentState({
  payment,
  sync,
}: {
  payment: SessionPayment["payment"];
  sync: SessionPayment["sync"];
}) {
  const { t } = useTranslation();
  if (payment.cancelled) return <StatusPill tone="gray">{t("cash.payments.cancelled")}</StatusPill>;
  if (payment.cancellation_pending) {
    return <StatusPill tone="due">{t("cash.payments.cancellationPending")}</StatusPill>;
  }
  if (sync === "pending") return <StatusPill tone="warn">{t("cash.payments.pending")}</StatusPill>;
  if (sync === "rejected") return <StatusPill tone="due">{t("cash.payments.rejected")}</StatusPill>;
  return <StatusPill tone="ok">{t("cash.payments.recorded")}</StatusPill>;
}
