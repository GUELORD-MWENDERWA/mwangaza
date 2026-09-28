// Accueil de la caisse ouverte (maquette `caisse-accueil`) : recherche de l'élève, totaux de la
// session par devise (jamais additionnés), paiements de la session ; un élève choisi → encaissement
// (`CollectPanel`), dont le reçu s'imprime aussitôt ; « Réimprimer » : duplicata noté au journal.
// Clavier : Ctrl K rechercher, Échap changer d'élève. Opérations en attente d'envoi : 3.4 ;
// annulations et clôture : 3.8.
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
import { useCurrentSchool } from "../../lib/school";
import { useSettled } from "../../lib/settled";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { type StudentRow, useStudentSearch } from "../students/data";
import { RateBanner } from "./CashPage";
import { type Chosen, CollectPanel } from "./CollectPanel";
import { type CurrentSession, useSessionPayments } from "./data";
import { type Receipt, useReceiptPrinter } from "./Receipt";

type Session = NonNullable<CurrentSession["session"]>;

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

export function CashDesk({ current, session }: { current: CurrentSession; session: Session }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [chosen, setChosen] = useState<Chosen | null>(null);
  const [recorded, setRecorded] = useState<Receipt | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const printer = useReceiptPrinter();
  const reprint = useMutation({
    mutationFn: (id: string) =>
      call(api.POST("/api/payments/{id}/reprint/", { params: { path: { id } } })),
    onSuccess: (payment) => printer.print({ payment, reprintedAt: new Date().toISOString() }),
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

  const count = current.totals.reduce((total, item) => total + item.count, 0);
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
          school.enabled_currencies.length > 1 && current.rate ? (
            <span className="rounded-field border border-line bg-card px-3 py-2 text-sm tabular-nums">
              {t("cash.rate", { rate: formatRate(current.rate) })}
            </span>
          ) : undefined
        }
      />
      <RateBanner current={current} />
      {printer.area}
      {recorded && (
        <Banner tone="ok" role="status">
          <span className="flex-1">
            {t("cash.desk.recorded", { number: recorded.receipt_number })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={reprint.isPending}
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
            onRecorded={(payment) => {
              setRecorded(payment);
              setChosen(null);
              printer.print({ payment });
            }}
          />
        </>
      ) : (
        <>
          <StudentSearch inputRef={searchRef} onChoose={choose} />
          <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
            {school.enabled_currencies.map((currency) => {
              const total = current.totals.find((item) => item.currency === currency);
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
            onChoose={choose}
            onReprint={(id) => reprint.mutate(id)}
            reprinting={reprint.isPending}
          />
        </>
      )}
    </>
  );
}

function StudentSearch({
  inputRef,
  onChoose,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>;
  onChoose: (chosen: Chosen) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const search = useSettled(text.trim());
  const found = useStudentSearch(search);
  const results = search.length >= 2 ? (found.data?.results ?? []).slice(0, SHOWN) : [];
  const first = results.map(chosenFrom).find(Boolean);

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
        {search.length >= 2 && found.data && results.length === 0 && (
          <p className="text-sm text-ink-3">{t("cash.desk.noResult")}</p>
        )}
        {results.length > 0 && (
          <ul className="flex flex-col divide-y divide-line-soft">
            {results.map((student) => {
              const chosen = chosenFrom(student);
              return (
                <li key={student.id}>
                  <button
                    type="button"
                    disabled={!chosen}
                    onClick={() => chosen && onChoose(chosen)}
                    className="flex w-full flex-wrap items-baseline gap-x-3 px-1 py-2.5 text-left hover:bg-surface disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    <b>{studentName(student)}</b>
                    <span className="text-sm text-ink-3">
                      {[
                        student.matricule,
                        student.enrollment?.class_group_name ?? t("cash.desk.notEnrolled"),
                      ].join(" · ")}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function SessionPayments({
  session,
  onChoose,
  onReprint,
  reprinting,
}: {
  session: string;
  onChoose: (chosen: Chosen) => void;
  onReprint: (id: string) => void;
  reprinting: boolean;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [text, setText] = useState("");
  const [page, setPage] = useState(1);
  const search = useSettled(text.trim());
  const payments = useSessionPayments(session, search, page);

  if (payments.error)
    return <LoadError error={payments.error} onRetry={() => void payments.refetch()} />;
  const results = payments.data?.results ?? [];
  const from = results.length ? (page - 1) * 50 + 1 : 0;
  // Derniers élèves servis (sans tuteur : la fiche complète est dans « Élèves »).
  const recent = search
    ? []
    : results
        .filter(
          (payment, index) =>
            results.findIndex((other) => other.enrollment === payment.enrollment) === index,
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
        {!payments.data ? (
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
                {results.map((payment) => {
                  const amount = formatAmount(
                    payment.received_amount_minor,
                    payment.received_currency as Currency,
                  );
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
                        {payment.cancelled ? <s>{amount}</s> : amount}
                      </td>
                      <td>
                        <StatusPill tone={payment.cancelled ? "gray" : "ok"}>
                          {t(
                            payment.cancelled
                              ? "cash.payments.cancelled"
                              : "cash.payments.recorded",
                          )}
                        </StatusPill>
                      </td>
                      <td className="text-right">
                        {!payment.cancelled && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={reprinting}
                            aria-label={t("cash.payments.reprintLabel", {
                              number: payment.receipt_number,
                            })}
                            onClick={() => onReprint(payment.id)}
                          >
                            {t("cash.payments.reprint")}
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
              hasPrevious={Boolean(payments.data.previous)}
              hasNext={Boolean(payments.data.next)}
              onPage={setPage}
              summary={t("cash.payments.range", {
                from,
                to: from + results.length - 1,
                count: payments.data.count,
              })}
            />
          </>
        )}
      </Card>
    </>
  );
}
