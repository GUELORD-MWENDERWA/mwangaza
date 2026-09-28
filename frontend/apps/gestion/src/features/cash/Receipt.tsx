// Reçu imprimé dans le navigateur (F3, F6 ; maquette `recu`) au format choisi par l'école
// (`school.receipt`, carte « Reçus et documents ») : ticket thermique 80 ou 58 mm, ou reçus A6,
// A5 ou petit format sur une feuille A4 avec traits de découpe ; 1 exemplaire, ou 2 avec la
// souche de l'école. Tout vient du paiement (solde juste après lui compris) et de l'école, pour
// qu'il s'imprime aussi hors ligne (3.4). Zone cachée à l'écran, puis `window.print()`.
import type { Schemas } from "@mwangaza/api";
import { formatDateTime, formatDay, type TFunction, useTranslation } from "@mwangaza/i18n";
import { amountInWords, type Currency, formatAmount, formatRate } from "@mwangaza/money";
import { type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { fullName } from "../../lib/people";
import type { School } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { QrCode } from "../auth/QrCode";
import { headerLines } from "../settings/ReceiptCard";
import "./receipt.css";

export type Receipt = Schemas["PaymentReceipt"];
/** `reprintedAt` : duplicata (F6) ; `test` : reçu d'essai de l'imprimante, sans valeur. */
export type PrintJob = { payment: Receipt; reprintedAt?: string; test?: boolean };

// Au-delà, le logo manquant ne retient plus l'impression.
const IMAGE_WAIT_MS = 2000;

function amounts(items: { currency: string; minor: number }[], nothing: string): string {
  const due = items.filter((item) => item.minor > 0);
  if (!due.length) return nothing;
  return due.map((item) => formatAmount(item.minor, item.currency as Currency)).join(" + ");
}

function ReceiptCopy({ job, school, copy }: { job: PrintJob; school: School; copy?: number }) {
  const { t, i18n } = useTranslation();
  const { payment } = job;
  const { printer, sheet_size } = school.receipt;
  const thermal = printer !== "sheet";
  const withDueDates = printer === "sheet" && sheet_size === "a5";
  const logo = thermal ? (school.logo_monochrome ?? school.logo) : school.logo;
  const received = payment.received_currency as Currency;
  const rate =
    payment.rate_used && payment.allocations.some((line) => line.currency !== received)
      ? payment.rate_used
      : null;
  const { origin, host } = window.location;
  const id = payment.id;
  const qr = (
    <div className="receipt__qr">
      <QrCode value={`${origin}/v/${id}`} label={t("cash.receipt.qr")} />
    </div>
  );
  const when = (value: string) => formatDateTime(value, i18n.language, school.timezone);
  const balance = payment.balance.currencies;

  return (
    <article className="receipt">
      {(job.reprintedAt || job.test) && (
        <p className="receipt__mark">
          <strong>{t(job.test ? "cash.receipt.test" : "cash.receipt.duplicate")}</strong>
          {job.test
            ? t("cash.receipt.testHelp")
            : t("cash.receipt.reprinted", { date: when(job.reprintedAt ?? "") })}
        </p>
      )}
      <header className="receipt__head">
        {logo && (
          <img
            className={
              thermal && !school.logo_monochrome
                ? "receipt__logo receipt__logo--gray"
                : "receipt__logo"
            }
            src={logo}
            alt=""
          />
        )}
        <div className="receipt__school">
          <b>{school.name}</b>
          {headerLines(school.receipt.header).map((line, index) => (
            <span key={index}>{line}</span>
          ))}
        </div>
        {!thermal && qr}
      </header>
      <p className="receipt__title">
        <b>{t("cash.receipt.title", { number: payment.receipt_number })}</b>
        <span>{when(payment.paid_at)}</span>
        {withDueDates && <span>{t("cash.receipt.year", { year: payment.academic_year })}</span>}
      </p>
      <dl className="receipt__rows">
        <div>
          <dt>{t("cash.receipt.student")}</dt>
          <dd>
            <b>{payment.student.full_name}</b>
          </dd>
        </div>
        <div>
          <dt>{t("cash.receipt.matricule")}</dt>
          <dd>{payment.student.matricule}</dd>
        </div>
        <div>
          <dt>{t("cash.receipt.classGroup")}</dt>
          <dd>{payment.class_group}</dd>
        </div>
      </dl>
      <table className="receipt__lines">
        <tbody>
          {payment.allocations.map((line) => (
            <tr key={line.student_charge}>
              <td>{`${line.fee_type_name} · ${line.label}`}</td>
              {withDueDates && <td>{formatDay(line.due_on, i18n.language)}</td>}
              <td>{formatAmount(line.amount_minor, line.currency as Currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="receipt__total">
        <span>{t("cash.receipt.total")}</span>
        <span>{formatAmount(payment.received_amount_minor, received)}</span>
      </p>
      <p className="receipt__words">{amountInWords(payment.received_amount_minor, received)}</p>
      {rate && <p>{t("cash.receipt.rate", { rate: formatRate(rate) })}</p>}
      <dl className="receipt__rows receipt__rule">
        <div>
          <dt>{t("cash.receipt.overdue")}</dt>
          <dd>
            {amounts(
              balance.map((item) => ({ currency: item.currency, minor: item.overdue_minor })),
              t("cash.receipt.nothing"),
            )}
          </dd>
        </div>
        <div>
          <dt>{t("cash.receipt.remaining")}</dt>
          <dd>
            {amounts(
              balance.map((item) => ({ currency: item.currency, minor: item.remaining_minor })),
              t("cash.receipt.nothing"),
            )}
          </dd>
        </div>
      </dl>
      {payment.note && <p>{t("cash.receipt.note", { note: payment.note })}</p>}
      <div className="receipt__sign">
        <p>
          {t("cash.receipt.cashier")}
          <br />
          <b>{fullName(payment.cashier)}</b> · {payment.cash_register_name}
        </p>
        <p className="receipt__stamp">{t("cash.receipt.stamp")}</p>
      </div>
      {thermal && qr}
      <p className="receipt__foot receipt__verify">
        {t("cash.receipt.verify", { url: `${host}/v/${id.slice(0, 4)}…${id.slice(-3)}` })}
      </p>
      {school.receipt.footer && <p className="receipt__foot">{school.receipt.footer}</p>}
      {copy !== undefined && (
        <p className="receipt__copy">
          {t(copy === 0 ? "cash.receipt.studentCopy" : "cash.receipt.schoolCopy")}
        </p>
      )}
    </article>
  );
}

/** Les exemplaires d'un reçu sur la page : ticket (séparés par un trait de découpe) ou feuille
 * A4 découpée en cases A6, A5 ou petit format. */
export function ReceiptPages({ job, school }: { job: PrintJob; school: School }) {
  const { printer, sheet_size, copies } = school.receipt;
  const items = Array.from({ length: copies }, (_, index) => (
    <ReceiptCopy key={index} job={job} school={school} copy={copies > 1 ? index : undefined} />
  ));
  if (printer !== "sheet") {
    return (
      <div className={`receipt-roll receipt-roll--${printer}`}>
        <style>{"@page { margin: 0 }"}</style>
        {items.flatMap((item, index) =>
          index ? [<hr key={`cut-${index}`} className="receipt-cut" />, item] : [item],
        )}
      </div>
    );
  }
  return (
    <div className={`receipt-sheet receipt-sheet--${sheet_size}`}>
      <style>{"@page { size: A4 portrait; margin: 0 }"}</style>
      {items.map((item, index) => (
        <div key={index} className="receipt-cell">
          {item}
        </div>
      ))}
    </div>
  );
}

function imagesReady(root: Element | null): Promise<unknown> {
  const pending = [...(root?.querySelectorAll("img") ?? [])].filter((image) => !image.complete);
  const loaded = Promise.all(
    pending.map(
      (image) =>
        new Promise((done) => {
          image.addEventListener("load", done, { once: true });
          image.addEventListener("error", done, { once: true });
        }),
    ),
  );
  return Promise.race([loaded, new Promise((done) => setTimeout(done, IMAGE_WAIT_MS))]);
}

/** `print(job)` imprime le reçu ; `area` (zone d'impression) se place dans l'écran. */
export function useReceiptPrinter(): { print: (job: PrintJob) => void; area: ReactNode } {
  const school = useCurrentSchool();
  const [job, setJob] = useState<PrintJob | null>(null);

  useEffect(() => {
    if (!job) return;
    let current = true;
    void imagesReady(document.querySelector(".print-area")).then(() => {
      if (!current) return;
      window.print();
      setJob(null);
    });
    return () => {
      current = false;
    };
  }, [job]);

  const area = job
    ? createPortal(
        <div className="print-area">
          <ReceiptPages job={job} school={school} />
        </div>,
        document.body,
      )
    : null;
  return { print: setJob, area };
}

/** Reçu d'essai de l'imprimante (bouton « Test » de l'ouverture de caisse) : montant fictif dans
 * la devise de l'école, marqué « sans valeur ». */
export function sampleReceipt(
  school: School,
  cashier: Receipt["cashier"],
  registerName: string,
  t: TFunction,
): Receipt {
  const currency = school.default_currency;
  const amount = currency === "USD" ? 15000 : 285000;
  const now = new Date().toISOString();
  const nothing = { total_minor: 0, paid_minor: 0, next_due_minor: 0 };
  return {
    id: "00000000-0000-7000-8000-000000000000",
    receipt_number: t("cash.receipt.sample.number"),
    enrollment: "",
    student: { id: "", full_name: t("cash.receipt.sample.student"), matricule: "0000" },
    class_group: t("cash.receipt.sample.classGroup"),
    cash_register: "",
    cash_register_name: registerName,
    cashier,
    received_amount_minor: amount,
    received_currency: currency,
    rate_used: null,
    paid_at: now,
    method: "cash",
    note: "",
    cancelled: false,
    academic_year: "",
    allocations: [
      {
        student_charge: "",
        fee_type_name: t("cash.receipt.sample.fee"),
        label: t("cash.receipt.sample.label"),
        currency,
        due_on: now.slice(0, 10),
        received_minor: amount,
        amount_minor: amount,
      },
    ],
    balance: {
      situation: "up_to_date",
      next_due_on: null,
      currencies: [{ currency, remaining_minor: 0, overdue_minor: 0, ...nothing }],
    },
  };
}
