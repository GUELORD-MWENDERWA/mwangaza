// Encaissement (maquette `caisse-encaissement`, F1-F2, F5) : ce que doit l'élève, le montant reçu,
// la répartition par défaut (`allocate`) ajustable en cochant les frais ; la répartition affichée
// est envoyée telle quelle et le serveur la vérifie. Identifiant du paiement donné par l'appareil
// et gardé jusqu'au succès : un double clic ou un nouvel essai après une coupure ne fait qu'un
// paiement. Jamais plus que ce que doit l'élève. F9 valide. Crédit de l'élève (M14, 3.6.2) :
// proposé avant l'encaissement, utilisé d'un clic sur ses échéances les plus anciennes.
// Appareil mémorisé : frais dus et crédits lus sur l'appareil, paiement et crédit utilisé écrits
// dans la file (numéro de reçu de l'appareil), avec ou sans réseau (3.5.1).
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  type Currency,
  currencySymbol,
  formatAmount,
  formatAmountValue,
  formatRate,
  parseAmount,
} from "@mwangaza/money";
import {
  Avatar,
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  CheckboxField,
  Field,
  Icon,
  Input,
  List,
  Segmented,
  Skeleton,
  StateCard,
  StatusPill,
  Table,
  initials,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { formatPhone } from "../../lib/people";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useRefresh } from "../organisation/data";
import { StudentCredits } from "../credits/StudentCredits";
import { LoadError } from "../status/StatusPages";
import {
  type Balance,
  type Charge,
  useBalance,
  useCharges,
  useStudentCredits,
} from "../students/data";
import { type Line, allocate, feeLabel, owedCharges, payableTotal } from "./allocation";
import type { DeviceCash } from "./CashDesk";
import type { CurrentSession } from "./data";
import { queueCreditUse, recordOffline } from "./localData";
import { financeOf, offlineReceipt, receiptNumber, schoolDay } from "./offline";
import type { Receipt } from "./Receipt";

type Session = NonNullable<CurrentSession["session"]>;
type Credit = Schemas["StudentCredit"];

/** Ce que le caissier valide. */
type Collect = {
  id: string;
  received: { minor: number; currency: Currency };
  lines: Line[];
  note: string;
};

/** Élève choisi à la caisse, avec son inscription de l'année. */
export type Chosen = {
  enrollment: string;
  name: string;
  matricule: string;
  classGroup: string;
  guardian: Schemas["Guardian"] | null;
};

const DAY = 86_400_000;

/** Jours de retard d'une échéance, au jour de l'école. */
function daysLate(dueOn: string, timeZone: string): number {
  const today = new Date().toLocaleDateString("en-CA", { timeZone });
  return Math.round((Date.parse(today) - Date.parse(dueOn)) / DAY);
}

/** « 20,00 $ + 30 000 FC » : chaque devise à part, jamais additionnées ; `null` si rien. */
function perCurrency(amounts: { currency: string; minor: number }[]): string | null {
  const listed = amounts.filter((item) => item.minor > 0);
  return listed.length
    ? listed.map((item) => formatAmount(item.minor, item.currency as Currency)).join(" + ")
    : null;
}

type PanelProps = {
  chosen: Chosen;
  rate: string | null;
  session: Session;
  onRecorded: (payment: Receipt) => void;
};

export function CollectPanel({ device, ...props }: PanelProps & { device?: DeviceCash }) {
  return device ? <DeviceCollect device={device} {...props} /> : <ServerCollect {...props} />;
}

function ServerCollect({ chosen, rate, onRecorded }: PanelProps) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const charges = useCharges(chosen.enrollment);
  const balance = useBalance(chosen.enrollment);
  const credits = useStudentCredits(chosen.enrollment);
  const refetch = () => void Promise.all([charges.refetch(), balance.refetch(), credits.refetch()]);
  const error = charges.error ?? balance.error ?? credits.error;
  if (error) return <LoadError error={error} onRetry={refetch} />;
  if (!charges.data || !balance.data || !credits.data)
    return <Skeleton label={t("common.loading")} />;
  const save = async ({ id, received, lines, note }: Collect) => {
    const payment = await call(
      api.POST("/api/payments/", {
        body: {
          id,
          enrollment: chosen.enrollment,
          received_amount_minor: received.minor,
          received_currency: received.currency,
          convert: false,
          allocations: lines.map((line) => ({
            student_charge: line.charge.id,
            received_minor: line.received,
          })),
          note,
        },
      }),
    );
    await refresh(keys.students, keys.payments, keys.cashSession);
    return payment;
  };
  // Le serveur répartit le crédit lui-même, sur ce que l'élève doit à ce moment.
  const spendCredit = async (credit: Credit) => {
    await call(api.POST("/api/student-credits/{id}/use/", { params: { path: { id: credit.id } } }));
    await refresh(keys.students, keys.credits);
  };
  return (
    <CollectForm
      chosen={chosen}
      rate={rate}
      charges={charges.data}
      balance={balance.data}
      credits={credits.data}
      save={save}
      spendCredit={spendCredit}
      onRecorded={onRecorded}
      onRefused={refetch}
    />
  );
}

/** Frais dus lus sur l'appareil, paiements de la file compris ; reçu fait sur l'appareil. */
function DeviceCollect({
  chosen,
  rate,
  session,
  onRecorded,
  device,
}: PanelProps & { device: DeviceCash }) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const enrollment = device.local.byId.get(chosen.enrollment);
  const year = device.local.config?.academic_year;
  if (!enrollment || !year)
    return (
      <StateCard icon="alert" tone="warn" title={t("cash.offline.missingTitle")}>
        {t("cash.offline.missingText")}
      </StateCard>
    );
  const day = schoolDay(school.timezone);
  const { charges, balance, credits } = financeOf(enrollment, device.local.queued, day);
  const save = ({ id, received, lines, note }: Collect) =>
    recordOffline(device.db, id, (seq) =>
      offlineReceipt({
        id,
        number: receiptNumber(school.code, device.prefix, year.starts_on, seq),
        enrollment,
        classGroup: chosen.classGroup,
        academicYear: year.name,
        session,
        cashier: {
          id: me.id,
          last_name: me.last_name,
          middle_name: me.middle_name,
          first_name: me.first_name,
        },
        received,
        rate,
        lines,
        charges,
        note,
        paidAt: new Date().toISOString(),
        day,
      }),
    );
  return (
    <CollectForm
      chosen={chosen}
      rate={rate}
      charges={charges}
      balance={balance}
      credits={credits}
      save={save}
      spendCredit={(credit, lines) => queueCreditUse(device.db, credit, lines)}
      onRecorded={onRecorded}
    />
  );
}

function CollectForm({
  chosen,
  rate,
  charges,
  balance,
  credits,
  save,
  spendCredit,
  onRecorded,
  onRefused,
}: {
  chosen: Chosen;
  rate: string | null;
  charges: Charge[];
  balance: Balance;
  credits: Credit[];
  save(collect: Collect): Promise<Receipt>;
  spendCredit(credit: Credit, lines: Line[]): Promise<void>;
  onRecorded: (payment: Receipt) => void;
  onRefused?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const currencies = school.enabled_currencies as Currency[];
  const [currency, setCurrency] = useState<Currency>(
    currencies.includes(school.default_currency as Currency)
      ? (school.default_currency as Currency)
      : currencies[0]!,
  );
  const [text, setText] = useState("");
  const [convertOthers, setConvertOthers] = useState(false);
  // Frais cochés par le caissier ; `null` : répartition par défaut.
  const [only, setOnly] = useState<ReadonlySet<string> | null>(null);
  const [note, setNote] = useState("");
  const paymentId = useRef(uuidv7());

  const owed = owedCharges(charges);
  const other = currencies.find((item) => item !== currency);
  const canConvert =
    rate !== null && owed.some((charge) => charge.currency !== currency) && Boolean(other);
  const received = parseAmount(text, currency) ?? 0;
  const lines = allocate(charges, { minor: received, currency }, rate, {
    convertOthers,
    only: only ?? undefined,
  });
  const allocated = lines.reduce((total, line) => total + line.received, 0);
  const surplus = received - allocated;
  const checked = only ?? new Set(lines.map((line) => line.charge.id));
  const overdue = owed.filter((charge) => charge.state === "overdue");

  const pay = useMutation({
    mutationFn: (payLines: Line[]) =>
      save({
        id: paymentId.current,
        received: { minor: received, currency },
        lines: payLines,
        note: note.trim(),
      }),
    onSuccess: (payment) => {
      paymentId.current = uuidv7();
      onRecorded(payment);
    },
    onError: onRefused,
  });
  const spend = useMutation({
    mutationFn: async ({ credit, lines }: { credit: Credit; lines: Line[] }) => {
      await spendCredit(credit, lines);
      const used = lines.reduce((total, line) => total + line.amount, 0);
      return formatAmount(used, credit.currency as Currency);
    },
    onError: onRefused,
  });
  const ready = received > 0 && lines.length > 0 && surplus === 0 && !pay.isPending;
  // Verrou immédiat : deux F9 avant le prochain rendu ne doivent ni enregistrer ni imprimer
  // deux fois (`isPending` ne change qu'au rendu suivant).
  const sending = useRef(false);
  const submit = () => {
    if (!ready || sending.current) return;
    sending.current = true;
    pay.mutate(lines, {
      onSettled: () => {
        sending.current = false;
      },
    });
  };
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "F9") return;
      event.preventDefault();
      formRef.current?.requestSubmit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const setAmount = (minor: number) => {
    setOnly(null);
    setText(formatAmountValue(minor, currency));
  };
  const toggle = (id: string) => {
    const next = new Set(checked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setOnly(next);
  };
  const remainingAfter = perCurrency(
    balance.currencies.map((item) => ({
      currency: item.currency,
      minor:
        item.remaining_minor -
        lines
          .filter((line) => line.charge.currency === item.currency)
          .reduce((total, line) => total + line.amount, 0),
    })),
  );
  const overdueTotal = perCurrency(
    balance.currencies.map((item) => ({ currency: item.currency, minor: item.overdue_minor })),
  );
  const remaining = perCurrency(
    balance.currencies.map((item) => ({ currency: item.currency, minor: item.remaining_minor })),
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-wrap items-center gap-4">
            <Avatar
              text={initials(chosen.name.split(" ")[0] ?? "", chosen.name.split(" ").at(-1) ?? "")}
              className="size-12 text-base"
            />
            <div className="min-w-0 flex-1">
              <h2 className="text-[1.15rem] font-bold">{chosen.name}</h2>
              <p className="text-sm text-ink-3">
                {[
                  chosen.classGroup,
                  chosen.guardian &&
                    t("cash.collect.guardian", {
                      name: chosen.guardian.full_name,
                      phone: formatPhone(chosen.guardian.phone),
                    }),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <div className="flex flex-wrap gap-5">
              <div>
                <p className="text-sm text-ink-3">{t("cash.collect.overdue")}</p>
                <p className={overdueTotal ? "font-bold text-due" : "font-bold"}>
                  {overdueTotal ?? t("cash.collect.nothing")}
                </p>
              </div>
              <div>
                <p className="text-sm text-ink-3">{t("cash.collect.remaining")}</p>
                <p className="font-bold">{remaining ?? t("cash.collect.nothing")}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        {spend.data && (
          <Banner tone="ok" role="status">
            {t("credits.student.used", { amount: spend.data })}
          </Banner>
        )}
        {spend.error && <Banner tone="due">{firstErrorMessage(spend.error, t)}</Banner>}
        <StudentCredits
          credits={credits}
          charges={charges}
          using={spend.isPending}
          onUse={(credit, lines) => spend.mutate({ credit, lines })}
        />
        {owed.length === 0 ? (
          <StateCard icon="check" tone="lake" title={t("cash.collect.toPay")}>
            {t("cash.collect.allPaid")}
          </StateCard>
        ) : (
          <Card>
            <CardHeader className="flex-wrap">
              <CardTitle>{t("cash.collect.toPay")}</CardTitle>
              <span className="text-sm text-ink-3">{t("cash.collect.toPayHelp")}</span>
            </CardHeader>
            <Table>
              <thead>
                <tr>
                  <th />
                  <th>{t("cash.collect.fee")}</th>
                  <th className="text-right">{t("cash.collect.left")}</th>
                  <th>{t("cash.collect.state")}</th>
                </tr>
              </thead>
              <tbody>
                {owed.map((charge) => {
                  const fee = feeLabel(charge);
                  const late = charge.state === "overdue";
                  return (
                    <tr key={charge.id} aria-selected={checked.has(charge.id)}>
                      <td>
                        <Checkbox
                          checked={checked.has(charge.id)}
                          disabled={charge.currency !== currency && rate === null}
                          onCheckedChange={() => toggle(charge.id)}
                          aria-label={t("cash.collect.pay", { fee })}
                        />
                      </td>
                      <td>
                        <b>{fee}</b>
                        <span className="block text-sm text-ink-3">
                          {t("cash.collect.dueOn", {
                            date: formatDay(charge.due_on, i18n.language),
                          })}
                        </span>
                      </td>
                      <td className="text-right font-bold tabular-nums whitespace-nowrap">
                        {formatAmount(charge.remaining_minor, charge.currency as Currency)}
                      </td>
                      <td>
                        <StatusPill tone={late ? "due" : "gray"}>
                          {late
                            ? t("cash.collect.late", {
                                count: daysLate(charge.due_on, school.timezone),
                              })
                            : t("cash.collect.upcoming")}
                        </StatusPill>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </Card>
        )}
      </div>
      {owed.length > 0 && (
        <form
          ref={formRef}
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <Card>
            <CardHeader className="flex-wrap">
              <CardTitle>{t("cash.collect.received")}</CardTitle>
              {currencies.length > 1 && (
                <Segmented
                  label={t("cash.collect.currency")}
                  value={currency}
                  options={currencies.map((item) => ({ value: item, label: item }))}
                  onValueChange={(value) => {
                    setCurrency(value);
                    setText("");
                    setOnly(null);
                    setConvertOthers(false);
                  }}
                />
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <label className="flex min-h-[54px] items-center gap-2 rounded-field border-2 border-lake bg-card px-3">
                <input
                  autoFocus
                  inputMode="decimal"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  aria-label={t("cash.collect.amount", { currency })}
                  className="min-w-0 flex-1 bg-transparent text-[1.4rem] font-bold tabular-nums outline-none"
                />
                <span className="text-ink-3">{currencySymbol(currency)}</span>
              </label>
              <div className="flex flex-wrap gap-2">
                {overdue.length > 0 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setAmount(payableTotal(overdue, currency, rate, convertOthers))}
                  >
                    {t("cash.collect.allOverdue")}
                  </Button>
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAmount(payableTotal(owed, currency, rate, convertOthers))}
                >
                  {t("cash.collect.allYear")}
                </Button>
              </div>
              {canConvert && (
                <CheckboxField
                  id="cash-convert"
                  label={t("cash.collect.convert", {
                    currency: currencySymbol(other!),
                    rate: formatRate(rate!),
                  })}
                  checked={convertOthers}
                  onCheckedChange={(value) => {
                    setOnly(null);
                    setConvertOthers(value === true);
                  }}
                />
              )}
            </CardContent>
          </Card>
          {received > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("cash.collect.split")}</CardTitle>
              </CardHeader>
              <CardContent>
                {surplus > 0 && (
                  <Banner tone="due" className="mb-3">
                    {t("cash.collect.surplus", { amount: formatAmount(surplus, currency) })}
                  </Banner>
                )}
                <List>
                  {lines.map((line) => {
                    const settled = line.amount === line.charge.remaining_minor;
                    const chargeCurrency = line.charge.currency as Currency;
                    return (
                      <div key={line.charge.id}>
                        <span>{feeLabel(line.charge)}</span>
                        <span className="flex items-center gap-2 tabular-nums whitespace-nowrap">
                          <b>{formatAmount(line.amount, chargeCurrency)}</b>
                          <StatusPill tone={settled ? "ok" : "warn"}>
                            {settled
                              ? t("cash.collect.settled")
                              : t("cash.collect.leftAfter", {
                                  amount: formatAmount(
                                    line.charge.remaining_minor - line.amount,
                                    chargeCurrency,
                                  ),
                                })}
                          </StatusPill>
                        </span>
                      </div>
                    );
                  })}
                  <div className="border-t-2 border-ink">
                    <b>{t("cash.collect.total")}</b>
                    <b className="text-[1.2rem] tabular-nums">
                      {formatAmount(allocated, currency)}
                    </b>
                  </div>
                  <div>
                    <span className="text-ink-3">{t("cash.collect.remainingAfter")}</span>
                    <b className="tabular-nums">{remainingAfter ?? t("cash.collect.nothing")}</b>
                  </div>
                </List>
              </CardContent>
            </Card>
          )}
          <Field id="cash-note" label={t("cash.collect.note")}>
            {(control) => (
              <Input
                {...control}
                value={note}
                maxLength={200}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t("cash.collect.notePlaceholder")}
              />
            )}
          </Field>
          {pay.error && <Banner tone="due">{firstErrorMessage(pay.error, t)}</Banner>}
          <Button type="submit" size="xl" disabled={!ready}>
            <Icon name="cash" size={20} />
            {t("cash.collect.submit")}
            <kbd className="ml-2 rounded-[5px] bg-white/20 px-1.5 text-[.8rem]">
              {t("cash.collect.submitKey")}
            </kbd>
          </Button>
        </form>
      )}
    </div>
  );
}
