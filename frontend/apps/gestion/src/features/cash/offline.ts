// Caisse sur l'appareil (F5, 3.5) : l'état reçu du serveur (inscriptions avec frais dus et
// paiements) plus les encaissements de la file pas encore descendus. Calculs sans base ni écran,
// mêmes règles que le serveur (`finance.services._settle` et `balance`) ; montants en entiers.
import type { Schemas } from "@mwangaza/api";
import type { Currency } from "@mwangaza/money";

import { studentName } from "../../lib/people";
import type { LocalEnrollment, QueuedOperation } from "../../lib/sync/db";
import type { Config } from "../../lib/sync/engine";
import type { Line } from "./allocation";
import type { Receipt } from "./Receipt";

type Charge = Schemas["StudentCharge"];
type Balance = Schemas["Balance"];
type Payment = Schemas["Payment"];

/** Contenu de l'opération `payment.create` (serveur : `OfflinePaymentSerializer`). */
export type OfflinePayment = {
  id: string;
  enrollment: string;
  received_amount_minor: number;
  received_currency: Currency;
  convert: false;
  allocations: { student_charge: string; received_minor: number }[];
  note: string;
  cash_session: string;
  receipt_number: string;
  paid_at: string;
};

/** Paiement d'une session : `pending` pas encore envoyé ; `rejected` refusé par le serveur ;
 *  `recorded` enregistré sur le serveur. */
export type SessionPayment = {
  payment: Payment;
  sync: "recorded" | "pending" | "rejected";
  error: Schemas["Error"] | null;
};

/** Jour de l'école (« 2026-09-29 »), pour les retards. */
export function schoolDay(timeZone: string, now = new Date()): string {
  return now.toLocaleDateString("en-CA", { timeZone });
}

/** Encaissements de la file qui comptent : pas refusés, et pas déjà dans l'état reçu du serveur
 *  (un paiement envoyé reste dans la file jusqu'à la descente suivante). */
function queuedReceipts(queued: QueuedOperation[], known: ReadonlySet<string>): Receipt[] {
  return queued.flatMap((op) =>
    op.type === "payment.create" &&
    op.status !== "rejected" &&
    op.receipt &&
    !known.has(op.receipt.id)
      ? [op.receipt]
      : [],
  );
}

/** Frais dus avec des montants de plus payés : reste et état recalculés au jour `day`, comme
 *  `_settle` (frais retiré ou remplacé : ne compte plus). */
export function settle(
  charges: Charge[],
  paid: { student_charge: string; amount_minor: number }[],
  day: string,
): Charge[] {
  const extra = new Map<string, number>();
  for (const line of paid) {
    extra.set(line.student_charge, (extra.get(line.student_charge) ?? 0) + line.amount_minor);
  }
  return charges.map((charge) => {
    const paidMinor = charge.paid_minor + (extra.get(charge.id) ?? 0);
    if (charge.status !== "active")
      return { ...charge, paid_minor: paidMinor, remaining_minor: 0, state: null };
    const remaining = Math.max(charge.amount_minor - charge.discount_minor - paidMinor, 0);
    const state = remaining === 0 ? "paid" : charge.due_on < day ? "overdue" : "upcoming";
    return { ...charge, paid_minor: paidMinor, remaining_minor: remaining, state };
  });
}

const CURRENCIES = ["USD", "CDF"] as const;

/** Solde par devise, jamais additionné entre devises, dollars d'abord (`finance.services.balance`). */
export function balanceOf(charges: Charge[]): Balance {
  const active = charges.filter((charge) => charge.state);
  const upcoming = active.filter((charge) => charge.state === "upcoming").map((c) => c.due_on);
  const nextDueOn = upcoming.length ? upcoming.reduce((a, b) => (b < a ? b : a)) : null;
  const sum = (items: Charge[], value: (charge: Charge) => number) =>
    items.reduce((total, charge) => total + value(charge), 0);
  const currencies = CURRENCIES.flatMap((currency) => {
    const items = active.filter((charge) => charge.currency === currency);
    if (!items.length) return [];
    return [
      {
        currency,
        total_minor: sum(items, (c) => c.amount_minor - c.discount_minor),
        paid_minor: sum(items, (c) => c.paid_minor),
        remaining_minor: sum(items, (c) => c.remaining_minor),
        overdue_minor: sum(items, (c) => (c.state === "overdue" ? c.remaining_minor : 0)),
        next_due_minor: sum(items, (c) =>
          c.state === "upcoming" && c.due_on === nextDueOn ? c.remaining_minor : 0,
        ),
      },
    ];
  });
  const late = currencies.some((item) => item.overdue_minor);
  const situation = !late
    ? "up_to_date"
    : currencies.some((item) => item.paid_minor)
      ? "partial"
      : "overdue";
  return { situation, next_due_on: nextDueOn, currencies };
}

/** Frais dus et solde d'une inscription, encaissements de la file compris. */
export function financeOf(
  enrollment: LocalEnrollment,
  queued: QueuedOperation[],
  day: string,
): { charges: Charge[]; balance: Balance } {
  const known = new Set((enrollment.payments ?? []).map((payment) => payment.id));
  const paid = queuedReceipts(queued, known)
    .filter((receipt) => receipt.enrollment === enrollment.id)
    .flatMap((receipt) => receipt.allocations);
  const charges = settle(enrollment.charges ?? [], paid, day);
  return { charges, balance: balanceOf(charges) };
}

/** Paiements d'une session, les plus récents d'abord : ceux du serveur et ceux de la file. */
export function sessionPayments(
  enrollments: LocalEnrollment[],
  queued: QueuedOperation[],
  session: string,
): SessionPayment[] {
  const known = new Set<string>();
  const rows: SessionPayment[] = [];
  for (const enrollment of enrollments) {
    for (const payment of enrollment.payments ?? []) {
      known.add(payment.id);
      if (payment.cash_session === session) rows.push({ payment, sync: "recorded", error: null });
    }
  }
  for (const op of queued) {
    if (op.type !== "payment.create" || !op.receipt || known.has(op.receipt.id)) continue;
    if (op.receipt.cash_session !== session) continue;
    const sync =
      op.status === "pending" ? "pending" : op.status === "sent" ? "recorded" : "rejected";
    rows.push({ payment: op.receipt, sync, error: op.error });
  }
  return rows.sort((a, b) => b.payment.paid_at.localeCompare(a.payment.paid_at));
}

/** Totaux par devise d'une session : ni les annulés, ni les refusés. */
export function sessionTotals(rows: SessionPayment[]): Schemas["SessionTotal"][] {
  const totals = new Map<string, Schemas["SessionTotal"]>();
  for (const { payment, sync } of rows) {
    if (payment.cancelled || sync === "rejected") continue;
    const currency = payment.received_currency;
    const total = totals.get(currency) ?? { currency, amount_minor: 0, count: 0 };
    total.amount_minor += payment.received_amount_minor;
    total.count += 1;
    totals.set(currency, total);
  }
  return [...totals.values()];
}

const plain = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Recherche de la caisse : chaque mot tapé dans le nom ou le matricule, sans tenir compte des
 *  accents ni des majuscules. */
export function searchEnrollments(
  enrollments: LocalEnrollment[],
  text: string,
  limit: number,
): LocalEnrollment[] {
  const words = plain(text).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const found: LocalEnrollment[] = [];
  for (const enrollment of enrollments) {
    const { student } = enrollment;
    const haystack = plain(`${studentName(student)} ${student.matricule}`);
    if (words.every((word) => haystack.includes(word))) found.push(enrollment);
  }
  return found
    .sort((a, b) => studentName(a.student).localeCompare(studentName(b.student)))
    .slice(0, limit);
}

/** Numéro donné par l'appareil : `ITIG-P1-26-000184` (école, appareil, année scolaire, séquence
 *  de l'appareil), celui que le serveur vérifie. */
export function receiptNumber(school: string, prefix: string, yearStartsOn: string, seq: number) {
  return `${school.toUpperCase()}-${prefix}-${yearStartsOn.slice(2, 4)}-${String(seq).padStart(6, "0")}`;
}

/** Reçu d'un encaissement fait sur l'appareil, imprimé sans le serveur ; le solde est celui
 *  d'après ce paiement. */
export function offlineReceipt(input: {
  id: string;
  number: string;
  enrollment: LocalEnrollment;
  classGroup: string;
  academicYear: string;
  session: NonNullable<Schemas["CurrentCashSession"]["session"]>;
  cashier: Schemas["Person"];
  received: { minor: number; currency: Currency };
  rate: string | null;
  lines: Line[];
  charges: Charge[];
  note: string;
  paidAt: string;
  day: string;
}): Receipt {
  const allocations = input.lines.map((line) => ({
    student_charge: line.charge.id,
    fee_type_name: line.charge.fee_type_name,
    label: line.charge.label,
    currency: line.charge.currency,
    due_on: line.charge.due_on,
    received_minor: line.received,
    amount_minor: line.amount,
  }));
  const { student } = input.enrollment;
  return {
    id: input.id,
    receipt_number: input.number,
    enrollment: input.enrollment.id,
    student: { id: student.id, full_name: studentName(student), matricule: student.matricule },
    class_group: input.classGroup,
    cash_register: input.session.cash_register.code,
    cash_register_name: input.session.cash_register.name,
    cash_session: input.session.id,
    cashier: input.cashier,
    received_amount_minor: input.received.minor,
    received_currency: input.received.currency,
    rate_used: input.rate,
    paid_at: input.paidAt,
    method: "cash",
    note: input.note,
    cancelled: false,
    allocations,
    academic_year: input.academicYear,
    balance: balanceOf(settle(input.charges, allocations, input.day)),
  };
}

/** Duplicata (F6) d'un paiement de l'inscription, fait sur l'appareil : le reçu du serveur
 *  (`balance_after`) — solde juste après ce paiement, avec les paiements encaissés jusqu'à lui
 *  (serveur et file, sauf annulés ou refusés), retard au jour du paiement. Paiement de la file :
 *  son propre reçu. */
export function duplicateReceipt(
  enrollment: LocalEnrollment,
  paymentId: string,
  queued: QueuedOperation[],
  config: Config | null,
  timeZone: string,
): Receipt | null {
  const recorded = enrollment.payments ?? [];
  const known = new Set(recorded.map((payment) => payment.id));
  const local = queuedReceipts(queued, known).filter((r) => r.enrollment === enrollment.id);
  const own = local.find((receipt) => receipt.id === paymentId);
  if (own) return own;
  const payment = recorded.find((item) => item.id === paymentId);
  if (!payment) return null;
  const at = (item: Payment) => [Date.parse(item.paid_at), item.id] as const;
  const [time, id] = at(payment);
  const upTo = [...recorded.filter((item) => !item.cancelled), ...local].filter((item) => {
    const [itemTime, itemId] = at(item);
    return itemTime < time || (itemTime === time && itemId <= id);
  });
  const charges = (enrollment.charges ?? []).map((charge) => ({ ...charge, paid_minor: 0 }));
  const day = schoolDay(timeZone, new Date(payment.paid_at));
  const register = config?.cash_registers?.find((item) => item.code === payment.cash_register);
  return {
    ...payment,
    cash_register_name: register?.name ?? payment.cash_register,
    academic_year: config?.academic_year?.name ?? "",
    balance: balanceOf(
      settle(
        charges,
        upTo.flatMap((item) => item.allocations),
        day,
      ),
    ),
  };
}

/** Ce qui part au serveur pour ce reçu. */
export function offlinePayload(receipt: Receipt): OfflinePayment {
  return {
    id: receipt.id,
    enrollment: receipt.enrollment,
    received_amount_minor: receipt.received_amount_minor,
    received_currency: receipt.received_currency as Currency,
    convert: false,
    allocations: receipt.allocations.map((line) => ({
      student_charge: line.student_charge,
      received_minor: line.received_minor,
    })),
    note: receipt.note,
    cash_session: receipt.cash_session,
    receipt_number: receipt.receipt_number,
    paid_at: receipt.paid_at,
  };
}
