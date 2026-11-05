// Sortie de caisse (FIN.2, maquette `caisse-sortie`) : payer en espèces une dépense validée avec
// l'argent de la session ouverte du caissier. Le bon de sortie s'imprime et se signe. L'identifiant
// (UUID v7) est donné par l'appareil : un renvoi après une coupure ne sort pas l'argent deux fois.
// Appareil mémorisé : avec ou sans réseau, la sortie s'écrit dans la file (bon numéroté par
// l'appareil) avec les dépenses à payer gardées sur l'appareil ; sinon, en ligne.
import type { Schemas } from "@mwangaza/api";
import { formatDateTime, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  List,
  PageHeader,
  Select,
  Skeleton,
} from "@mwangaza/ui";
import { type ReactNode, useState } from "react";
import { Link } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { fullName } from "../../lib/people";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import type { LocalDb } from "../../lib/sync/db";
import { useSyncStatus } from "../../lib/sync/session";
import { onlineOnlyChosen } from "../shell/SyncMenu";
import { LoadError } from "../status/StatusPages";
import { headerLines } from "../settings/ReceiptCard";
import {
  type CashOut,
  type PayableExpense,
  useCurrentSession,
  useDevicePayable,
  usePayableExpenses,
  useRecordCashOut,
} from "./data";
import {
  cashOutNumber,
  deviceSession,
  recordCashOutOffline,
  sessionCashOuts,
  useLocalCash,
} from "./localData";
import { sessionPayments, sessionTotals } from "./offline";
import { ReceiptPages, usePrintArea } from "./Receipt";
import "./receipt.css";

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

type Session = NonNullable<Schemas["CurrentCashSession"]["session"]>;
type Save = (id: string, expense: PayableExpense, receivedBy: string) => Promise<CashOut>;

export function CashOutPage() {
  const { db, prefix, persisted } = useSyncStatus();
  // Comme la caisse : appareil mémorisé dont le stockage tient, sauf « en ligne seulement ».
  if (db && prefix && persisted !== false && !onlineOnlyChosen())
    return <DeviceCashOut db={db} prefix={prefix} />;
  return <ServerCashOut />;
}

function Header() {
  const { t } = useTranslation();
  const crumbs = (
    <>
      <Link to="/cash" className="text-lake underline">
        {t("cash.out.crumb")}
      </Link>{" "}
      / {t("cash.out.title")}
    </>
  );
  return (
    <PageHeader title={t("cash.out.title")} subtitle={t("cash.out.subtitle")} crumbs={crumbs} />
  );
}

function ServerCashOut() {
  const { t } = useTranslation();
  const current = useCurrentSession();
  const payable = usePayableExpenses();
  const record = useRecordCashOut();
  if (current.error)
    return <LoadError error={current.error} onRetry={() => void current.refetch()} />;
  if (payable.error)
    return <LoadError error={payable.error} onRetry={() => void payable.refetch()} />;
  if (!current.data || !payable.data) return <Skeleton label={t("common.loading")} />;
  const { totals, paid_out } = current.data;
  const have = (currency: string) =>
    (totals.find((row) => row.currency === currency)?.amount_minor ?? 0) -
    (paid_out.find((row) => row.currency === currency)?.amount_minor ?? 0);
  return (
    <CashOutForm
      session={current.data.session}
      expenses={payable.data.results}
      have={have}
      save={(id, expense, receivedBy) =>
        record.mutateAsync({ id, expense: expense.id, received_by: receivedBy })
      }
      note={t("cash.out.onlineOnly")}
    />
  );
}

/** Caisse de l'appareil : session, paiements et sorties lus sur l'appareil, file d'attente. */
function DeviceCashOut({ db, prefix }: { db: LocalDb; prefix: string }) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const local = useLocalCash(db);
  const payable = useDevicePayable(db);
  if (local.error) return <LoadError error={local.error} onRetry={() => location.reload()} />;
  if (payable.error)
    return <LoadError error={payable.error} onRetry={() => void payable.refetch()} />;
  if (!local.data || !payable.data) return <Skeleton label={t("common.loading")} />;
  const data = local.data;
  const session = data.saved ? deviceSession(data.saved, data.queued).session : undefined;
  const outs = session ? sessionCashOuts(data, session.id) : [];
  const refused = new Set(
    data.queued
      .filter((op) => op.type === "cash_out.create" && op.status === "rejected")
      .map((op) => op.op_id),
  );
  // Payée ici (pas refusée) : plus à payer, même avant que le serveur relise la liste.
  const taken = new Set(
    data.cashOuts.filter((row) => !refused.has(row.id)).map((r) => r.out.expense),
  );
  const expenses = payable.data.value.results.filter((row) => !taken.has(row.id));
  const totals = session
    ? sessionTotals(sessionPayments(data.enrollments, data.queued, session.id))
    : [];
  const have = (currency: string) =>
    (totals.find((row) => row.currency === currency)?.amount_minor ?? 0) -
    outs
      .filter((row) => row.sync !== "rejected" && row.out.currency === currency)
      .reduce((sum, row) => sum + row.out.amount_minor, 0);
  const year = data.config?.academic_year;
  const save: Save = (id, expense, receivedBy) =>
    recordCashOutOffline(db, id, (seq) => ({
      id,
      // Sans année connue, l'année civile, comme le serveur.
      number: cashOutNumber(school.code, prefix, year?.starts_on ?? new Date().toISOString(), seq),
      expense: expense.id,
      expense_number: expense.number,
      category_name: expense.category_name,
      beneficiary: expense.beneficiary,
      reason: expense.reason,
      amount_minor: expense.amount_minor,
      currency: expense.currency,
      received_by: receivedBy,
      paid_at: new Date().toISOString(),
      cash_session: session!.id,
      cash_register_code: session!.cash_register.code,
      cash_register_name: session!.cash_register.name,
      cashier_name: fullName(me),
      offline: true,
      cancelled: false,
      cancellation_reason: null,
    }));
  return (
    <CashOutForm
      session={session ?? null}
      expenses={expenses}
      have={have}
      save={save}
      note={t("cash.out.offline")}
    />
  );
}

function CashOutForm({
  session,
  expenses,
  have,
  save,
  note,
}: {
  session: Session | null;
  expenses: PayableExpense[];
  /** Argent de la session dans la caisse, par devise. */
  have: (currency: string) => number;
  save: Save;
  note: ReactNode;
}) {
  const { t } = useTranslation();
  const { print, area } = usePrintArea<CashOut>((job) => <SlipCopy out={job} />);
  const [expenseId, setExpenseId] = useState("");
  const [receivedBy, setReceivedBy] = useState("");
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<CashOut | null>(null);
  // Même identifiant tant que la sortie n'a pas réussi : un double clic n'en crée qu'une.
  const [id, setId] = useState(uuidv7);

  if (done)
    return (
      <>
        <Header />
        {area}
        <Card>
          <CardContent className="flex flex-col gap-4">
            <Banner tone="ok">
              {t("cash.out.done", {
                number: done.number,
                amount: money(done.amount_minor, done.currency),
              })}
            </Banner>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => print(done)}>
                <Icon name="print" size={18} />
                {t("cash.out.reprint")}
              </Button>
              <Button variant="outline" asChild>
                <Link to="/cash">{t("cash.out.back")}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </>
    );
  if (!session)
    return (
      <>
        <Header />
        <Banner tone="warn">
          {t("cash.out.noSession")}{" "}
          <Link to="/cash" className="underline">
            {t("cash.out.open")}
          </Link>
        </Banner>
      </>
    );

  const expense = expenses.find((row) => row.id === expenseId);
  const before = expense ? have(expense.currency) : 0;
  const lacking = expense !== undefined && before < expense.amount_minor;
  const name = receivedBy.trim();

  const choose = (value: string) => {
    setExpenseId(value);
    setReceivedBy(expenses.find((row) => row.id === value)?.beneficiary ?? "");
  };
  const submit = () => {
    setTried(true);
    if (!expense || !name || lacking || busy) return;
    setBusy(true);
    setError(null);
    save(id, expense, name)
      .then((out) => {
        setDone(out);
        setId(uuidv7());
        print(out);
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  return (
    <>
      <Header />
      {area}
      {error != null && <Banner tone="due">{firstErrorMessage(error, t)}</Banner>}
      {expenses.length === 0 && <Banner tone="info">{t("cash.out.none")}</Banner>}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[900px]:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("cash.out.expense")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Field
                id="out-expense"
                label={t("cash.out.expense")}
                help={t("cash.out.expenseHelp")}
                error={tried && !expense ? t("cash.out.expenseRequired") : undefined}
              >
                {(control) => (
                  <Select value={expenseId} onChange={(e) => choose(e.target.value)} {...control}>
                    <option value="">{t("cash.out.choose")}</option>
                    {expenses.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.number} · {row.beneficiary} · {money(row.amount_minor, row.currency)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              {expense && (
                <List>
                  <div>
                    <span>{t("cash.out.category")}</span>
                    <span>{expense.category_name}</span>
                  </div>
                  <div>
                    <span>{t("cash.out.amount")}</span>
                    <b>{money(expense.amount_minor, expense.currency)}</b>
                  </div>
                  <div>
                    <span>{t("cash.out.beneficiary")}</span>
                    <span>{expense.beneficiary}</span>
                  </div>
                  <div>
                    <span>{t("cash.out.reason")}</span>
                    <span>{expense.reason}</span>
                  </div>
                </List>
              )}
              <Field
                id="out-received"
                label={t("cash.out.receivedBy")}
                error={tried && expense && !name ? t("cash.out.receivedRequired") : undefined}
              >
                {(control) => (
                  <Input
                    maxLength={120}
                    value={receivedBy}
                    onChange={(e) => setReceivedBy(e.target.value)}
                    {...control}
                  />
                )}
              </Field>
            </CardContent>
          </Card>
        </div>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("cash.out.session", { name: session.cash_register.name })}</CardTitle>
            </CardHeader>
            <CardContent>
              {expense ? (
                <List>
                  <div>
                    <span>{t("cash.out.before")}</span>
                    <span className="tabular-nums">{money(before, expense.currency)}</span>
                  </div>
                  <div>
                    <span>{t("cash.out.after")}</span>
                    <b className={lacking ? "tabular-nums text-due" : "tabular-nums"}>
                      {money(before - expense.amount_minor, expense.currency)}
                    </b>
                  </div>
                </List>
              ) : (
                <p className="text-sm text-ink-3">{t("cash.out.pickFirst")}</p>
              )}
              {lacking && <Banner tone="due">{t("cash.out.notEnough")}</Banner>}
            </CardContent>
          </Card>
          <div className="flex flex-wrap gap-3">
            <Button size="xl" disabled={busy || lacking} onClick={submit}>
              <Icon name="print" size={20} />
              {t("cash.out.submit")}
            </Button>
            <Button variant="outline" size="xl" asChild>
              <Link to="/cash">{t("common.cancel")}</Link>
            </Button>
          </div>
          <Banner tone="info">{note}</Banner>
        </div>
      </div>
    </>
  );
}

/** Bon de sortie imprimé : à signer par le caissier et par celui qui reçoit l'argent. */
function SlipCopy({ out }: { out: CashOut }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  return (
    <ReceiptPages school={school}>
      <article className="receipt">
        <header className="receipt__head">
          <div className="receipt__school">
            <b>{school.name}</b>
            {headerLines(school.receipt.header).map((line, index) => (
              <span key={index}>{line}</span>
            ))}
          </div>
        </header>
        <p className="receipt__title">
          <b>{t("cash.out.slip.title", { number: out.number })}</b>
          <span>{formatDateTime(out.paid_at, i18n.language, school.timezone)}</span>
        </p>
        <dl className="receipt__rows">
          <div>
            <dt>{t("cash.out.slip.register")}</dt>
            <dd>
              {out.cash_register_name} · {out.cashier_name}
            </dd>
          </div>
          <div>
            <dt>{t("cash.out.slip.expense")}</dt>
            <dd>
              {out.expense_number} · {out.category_name}
            </dd>
          </div>
          <div>
            <dt>{t("cash.out.reason")}</dt>
            <dd>{out.reason}</dd>
          </div>
          <div>
            <dt>{t("cash.out.beneficiary")}</dt>
            <dd>{out.beneficiary}</dd>
          </div>
          <div>
            <dt>{t("cash.out.receivedBy")}</dt>
            <dd>{out.received_by}</dd>
          </div>
        </dl>
        <p className="receipt__total">
          <span>{t("cash.out.slip.amount")}</span>
          <span>{money(out.amount_minor, out.currency)}</span>
        </p>
        <div className="receipt__sign">
          <p>{t("cash.out.slip.signCashier")}</p>
          <p>{t("cash.out.slip.signReceiver")}</p>
        </div>
      </article>
    </ReceiptPages>
  );
}
