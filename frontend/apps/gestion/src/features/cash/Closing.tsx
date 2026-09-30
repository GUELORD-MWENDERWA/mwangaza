// Clôture de caisse par le caissier (F8, maquette `caisse-cloture`) : l'argent compté par devise
// face à l'attendu (paiements pas annulés de la session), l'écart expliqué, le détail par type de
// frais ; puis le bordereau imprimé, à signer et remettre au comptable. Appareil mémorisé : tout
// se calcule et se clôture sur l'appareil, avec ou sans réseau (opération `cash_session.close`) ;
// sinon en ligne. Le serveur recalcule l'attendu à l'arrivée ; 3.8.3 montre les clôtures.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDay, formatDateTime, formatTime, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount, parseAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Field,
  Icon,
  List,
  PageHeader,
  Skeleton,
  Table,
  Textarea,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { fullName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { headerLines } from "../settings/ReceiptCard";
import type { DeviceCash } from "./CashDesk";
import { type ClosingData, type Counted, closingOnDevice, differences } from "./closing";
import { useSessionClosing } from "./data";
import { queueClosing } from "./localData";
import { schoolDay, sessionPayments } from "./offline";
import { ReceiptPages, usePrintArea } from "./Receipt";
import "./receipt.css";

type Session = Schemas["CashSession"];
type Line = Schemas["CashClosingLine"];

/** Clôture faite : ce que montre et imprime le bordereau. */
export type Slip = {
  session: Session;
  data: ClosingData;
  lines: Line[];
  note: string;
  closedAt: string;
  /** Clôture dans la file de l'appareil, pas encore reçue par le serveur. */
  queued: boolean;
};

/** « USD », « FC » (comme les totaux de la caisse). */
const currencyName = (currency: string) => (currency === "CDF" ? "FC" : currency);
const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
const signed = (minor: number, currency: string) =>
  minor > 0
    ? `+ ${money(minor, currency)}`
    : minor < 0
      ? `− ${money(-minor, currency)}`
      : money(0, currency);
const tone = (minor: number | null) =>
  minor === null ? undefined : minor === 0 ? "text-ok" : "text-due";

export function ClosingPanel({
  session,
  device,
  onBack,
  onClosed,
}: {
  session: Session;
  device?: DeviceCash;
  onBack: () => void;
  onClosed: (slip: Slip) => void;
}) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const online = useSessionClosing(session.id, !device);
  const local =
    device &&
    closingOnDevice(
      sessionPayments(device.local.enrollments, device.local.queued, session.id),
      school.enabled_currencies,
    );
  const data: ClosingData | undefined = local ?? online.data;
  if (!device && online.error)
    return <LoadError error={online.error} onRetry={() => void online.refetch()} />;
  if (!data) return <Skeleton label={t("common.loading")} />;
  return (
    <ClosingForm
      session={session}
      data={data}
      device={device}
      onBack={onBack}
      onClosed={onClosed}
    />
  );
}

function ClosingForm({
  session,
  data,
  device,
  onBack,
  onClosed,
}: {
  session: Session;
  data: ClosingData;
  device?: DeviceCash;
  onBack: () => void;
  onClosed: (slip: Slip) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [tried, setTried] = useState(false);
  const counted: Counted = Object.fromEntries(
    data.currencies.map(({ currency }) => [
      currency,
      parseAmount(texts[currency] ?? "", currency as Currency),
    ]),
  );
  const rows = differences(data, counted);
  const gaps = rows.filter((row) => row.difference_minor);
  const missing = rows.some((row) => row.counted_minor === null);
  const noteMissing = gaps.length > 0 && !note.trim();
  const unsynced = device?.local.queued.filter((op) => op.status === "pending").length ?? 0;

  const close = useMutation({
    mutationFn: async (): Promise<Slip> => {
      const lines = rows.map((row) => ({
        ...row,
        counted_minor: row.counted_minor!,
        difference_minor: row.difference_minor!,
      })) as Line[];
      const closedAt = new Date().toISOString();
      const amounts = lines.map(({ currency, counted_minor }) => ({
        currency,
        amount_minor: counted_minor,
      }));
      if (device) {
        await queueClosing(device.db, {
          cash_session: session.id,
          counted: amounts,
          note: note.trim(),
          closed_at: closedAt,
        });
        return { session, data, lines, note: note.trim(), closedAt, queued: true };
      }
      const done = await call(
        api.POST("/api/cash-sessions/{id}/close/", {
          params: { path: { id: session.id } },
          body: { counted: amounts, note: note.trim() },
        }),
      );
      const closing = done.closing!;
      return {
        session: done.session,
        data: done,
        lines: closing.lines,
        note: closing.note,
        closedAt: closing.closed_at,
        queued: false,
      };
    },
    onSuccess: (slip) => {
      void queryClient.invalidateQueries({ queryKey: keys.cashSession });
      void queryClient.invalidateQueries({ queryKey: keys.payments });
      onClosed(slip);
    },
  });

  const submit = () => {
    setTried(true);
    if (!missing && !noteMissing && confirmed) close.mutate();
  };
  const day = formatDay(schoolDay(school.timezone, new Date(session.opened_at)), i18n.language);

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <button type="button" className="text-lake underline" onClick={onBack}>
              {session.cash_register.name}
            </button>
            {" / "}
            {t("cash.closing.crumb")}
          </>
        }
        title={t("cash.closing.title", { name: session.cash_register.name })}
        subtitle={t("cash.closing.subtitle", {
          day,
          time: formatTime(session.opened_at, i18n.language, school.timezone),
          name: fullName(session.cashier),
        })}
      />
      {close.error && <Banner tone="due">{firstErrorMessage(close.error, t)}</Banner>}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[900px]:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("cash.closing.count")}</CardTitle>
            </CardHeader>
            <Table>
              <thead>
                <tr>
                  <th>{t("cash.closing.currency")}</th>
                  <th className="text-right">{t("cash.closing.expected")}</th>
                  <th className="text-right">{t("cash.closing.counted")}</th>
                  <th className="text-right">{t("cash.closing.difference")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.currency}>
                    <td className="font-bold">{currencyName(row.currency)}</td>
                    <td className="text-right tabular-nums">
                      {money(row.expected_minor, row.currency)}
                    </td>
                    <td className="text-right">
                      <input
                        inputMode="decimal"
                        value={texts[row.currency] ?? ""}
                        onChange={(event) =>
                          setTexts((before) => ({ ...before, [row.currency]: event.target.value }))
                        }
                        aria-label={t("cash.closing.countedIn", {
                          currency: currencyName(row.currency),
                        })}
                        aria-invalid={tried && row.counted_minor === null}
                        className={cn(
                          "min-h-[40px] w-full min-w-[7rem] rounded-field border bg-card px-2 text-right tabular-nums",
                          tried && row.counted_minor === null ? "border-due" : "border-line",
                        )}
                      />
                    </td>
                    <td
                      className={cn(
                        "text-right font-bold whitespace-nowrap tabular-nums",
                        tone(row.difference_minor),
                      )}
                    >
                      {row.difference_minor === null
                        ? "—"
                        : signed(row.difference_minor, row.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <CardContent className="flex flex-col gap-3">
              {tried && missing && <p className="text-sm text-due">{t("cash.closing.countAll")}</p>}
              {gaps.length > 0 && (
                <Banner tone="warn">
                  {t("cash.closing.gap", {
                    amount: gaps
                      .map((row) => signed(row.difference_minor!, row.currency))
                      .join(" · "),
                  })}
                </Banner>
              )}
              {gaps.length > 0 && (
                <Field
                  id="closing-note"
                  label={t("cash.closing.note")}
                  required
                  error={tried && noteMissing ? t("cash.closing.noteRequired") : undefined}
                >
                  {(control) => (
                    <Textarea
                      rows={2}
                      maxLength={500}
                      placeholder={t("cash.closing.notePlaceholder")}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      {...control}
                    />
                  )}
                </Field>
              )}
            </CardContent>
          </Card>
          <FeeTypes data={data} />
        </div>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("cash.closing.summary")}</CardTitle>
            </CardHeader>
            <CardContent>
              <Summary data={data} unsynced={device ? unsynced : undefined} />
            </CardContent>
          </Card>
          {device && <Banner tone="info">{t("cash.closing.offline")}</Banner>}
          <CheckboxField
            id="closing-confirm"
            label={t("cash.closing.confirm")}
            checked={confirmed}
            onCheckedChange={(value) => setConfirmed(value === true)}
          />
          {tried && !confirmed && (
            <p className="text-sm text-due">{t("cash.closing.confirmRequired")}</p>
          )}
          <Button size="xl" disabled={close.isPending} onClick={submit}>
            <Icon name="lock" size={20} />
            {t("cash.closing.submit")}
          </Button>
          <p className="text-sm text-ink-3">{t("cash.closing.after")}</p>
        </div>
      </div>
    </>
  );
}

function FeeTypes({ data }: { data: ClosingData }) {
  const { t } = useTranslation();
  const currencies = data.currencies.map((row) => row.currency);
  const names = [...new Set(data.fee_types.map((row) => row.fee_type))];
  const cell = (name: string | null, currency: string) => {
    const row = data.fee_types.find((item) => item.fee_type === name && item.currency === currency);
    return row ? money(row.amount_minor, currency) : "—";
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("cash.closing.byFeeType")}</CardTitle>
      </CardHeader>
      <Table>
        <thead>
          <tr>
            <th>{t("cash.closing.fee")}</th>
            {currencies.map((currency) => (
              <th key={currency} className="text-right">
                {currencyName(currency)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {names.length === 0 && (
            <tr>
              <td colSpan={currencies.length + 1} className="text-ink-3">
                {t("cash.closing.noPayment")}
              </td>
            </tr>
          )}
          {names.map((name) => (
            <tr key={name ?? ""}>
              <td>{name ?? t("cash.closing.surplus")}</td>
              {currencies.map((currency) => (
                <td key={currency} className="text-right tabular-nums">
                  {cell(name, currency)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="font-bold">
            <td>{t("cash.closing.total")}</td>
            {data.currencies.map((row) => (
              <td key={row.currency} className="text-right tabular-nums">
                {money(row.expected_minor, row.currency)}
              </td>
            ))}
          </tr>
        </tfoot>
      </Table>
    </Card>
  );
}

function Summary({ data, unsynced }: { data: ClosingData; unsynced?: number }) {
  const { t } = useTranslation();
  const cancelled = data.cancelled.reduce((sum, row) => sum + row.count, 0);
  return (
    <List>
      <div>
        <span>{t("cash.closing.payments")}</span>
        <b>{data.payments_count}</b>
      </div>
      <div>
        <span>{t("cash.closing.firstReceipt")}</span>
        <span>{data.first_receipt ?? "—"}</span>
      </div>
      <div>
        <span>{t("cash.closing.lastReceipt")}</span>
        <span>{data.last_receipt ?? "—"}</span>
      </div>
      <div>
        <span>{t("cash.closing.cancelled")}</span>
        <b>
          {cancelled
            ? `${cancelled} (${data.cancelled.map((row) => money(row.amount_minor, row.currency)).join(" · ")})`
            : 0}
        </b>
      </div>
      <div>
        <span>{t("cash.closing.pending")}</span>
        <b className={data.cancellations_pending ? "text-warn" : undefined}>
          {data.cancellations_pending}
        </b>
      </div>
      {unsynced !== undefined && (
        <div>
          <span>{t("cash.closing.unsynced")}</span>
          <b className={unsynced ? "text-warn" : undefined}>{unsynced}</b>
        </div>
      )}
    </List>
  );
}

/** Bordereau de clôture, au format de reçu de l'école, un exemplaire : à signer par le caissier
 *  et le comptable qui reçoit l'argent. */
function SlipCopy({ slip }: { slip: Slip }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const when = (value: string) => formatDateTime(value, i18n.language, school.timezone);
  const cancelled = slip.data.cancelled.reduce((sum, row) => sum + row.count, 0);
  return (
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
        <b>{t("cash.closing.slip.title", { name: slip.session.cash_register.name })}</b>
        <span>{when(slip.closedAt)}</span>
      </p>
      <dl className="receipt__rows">
        <div>
          <dt>{t("cash.closing.slip.cashier")}</dt>
          <dd>{fullName(slip.session.cashier)}</dd>
        </div>
        <div>
          <dt>{t("cash.closing.slip.opened")}</dt>
          <dd>{when(slip.session.opened_at)}</dd>
        </div>
        <div>
          <dt>{t("cash.closing.payments")}</dt>
          <dd>
            {slip.data.payments_count}
            {slip.data.first_receipt && ` · ${slip.data.first_receipt} → ${slip.data.last_receipt}`}
          </dd>
        </div>
        <div>
          <dt>{t("cash.closing.cancelled")}</dt>
          <dd>{cancelled}</dd>
        </div>
      </dl>
      <table className="receipt__lines">
        <tbody>
          {slip.lines.map((line) => (
            <tr key={line.currency}>
              <td>
                {t("cash.closing.slip.line", {
                  currency: currencyName(line.currency),
                  expected: money(line.expected_minor, line.currency),
                })}
              </td>
              <td>{money(line.counted_minor, line.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {slip.lines.map((line) => (
        <p key={line.currency} className="receipt__total">
          <span>
            {t("cash.closing.slip.difference", {
              currency: currencyName(line.currency),
            })}
          </span>
          <span>{signed(line.difference_minor, line.currency)}</span>
        </p>
      ))}
      {slip.note && <p>{t("cash.closing.slip.note", { note: slip.note })}</p>}
      <div className="receipt__sign">
        <p>
          {t("cash.closing.slip.signCashier")}
          <br />
          <b>{fullName(slip.session.cashier)}</b>
        </p>
        <p>{t("cash.closing.slip.signAccountant")}</p>
      </div>
    </article>
  );
}

/** Caisse clôturée : le bordereau s'imprime aussitôt, se réimprime, puis retour à l'ouverture. */
export function ClosedView({ slip, onDone }: { slip: Slip; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const single = { ...school, receipt: { ...school.receipt, copies: 1 as const } };
  const { print, area } = usePrintArea<Slip>((job) => (
    <ReceiptPages school={single} copy={() => <SlipCopy slip={job} />} />
  ));
  useEffect(() => print(slip), [print, slip]);

  return (
    <>
      <PageHeader
        title={t("cash.closing.done.title", { name: slip.session.cash_register.name })}
        subtitle={t("cash.closing.done.subtitle", {
          time: formatTime(slip.closedAt, i18n.language, school.timezone),
        })}
      />
      {area}
      <Banner tone="ok" role="status">
        {t(slip.queued ? "cash.closing.done.queued" : "cash.closing.done.sent")}
      </Banner>
      <Card>
        <Table>
          <thead>
            <tr>
              <th>{t("cash.closing.currency")}</th>
              <th className="text-right">{t("cash.closing.expected")}</th>
              <th className="text-right">{t("cash.closing.counted")}</th>
              <th className="text-right">{t("cash.closing.difference")}</th>
            </tr>
          </thead>
          <tbody>
            {slip.lines.map((line) => (
              <tr key={line.currency}>
                <td className="font-bold">{currencyName(line.currency)}</td>
                <td className="text-right tabular-nums">
                  {money(line.expected_minor, line.currency)}
                </td>
                <td className="text-right tabular-nums">
                  {money(line.counted_minor, line.currency)}
                </td>
                <td
                  className={cn(
                    "text-right font-bold whitespace-nowrap tabular-nums",
                    tone(line.difference_minor),
                  )}
                >
                  {signed(line.difference_minor, line.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => print(slip)}>
          <Icon name="print" size={18} />
          {t("cash.closing.done.reprint")}
        </Button>
        <Button onClick={onDone}>{t("cash.closing.done.finish")}</Button>
      </div>
    </>
  );
}
