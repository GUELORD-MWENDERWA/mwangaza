// Reçu imprimé dans le navigateur (F3, F6 ; maquette `recu`) au format choisi par l'école
// (`school.receipt`, carte « Reçus et documents ») : ticket thermique 80 ou 58 mm, ou reçus A6,
// A5 ou petit format sur une feuille A4 avec traits de découpe ; 1 exemplaire, ou 2 avec la
// souche de l'école. Tout vient du paiement (solde juste après lui compris) et de l'école, pour
// qu'il s'imprime aussi hors ligne (3.5). QR code signé par l'appareil mémorisé (3.5.2). Zone
// cachée à l'écran, puis `window.print()`.
import type { Schemas } from "@mwangaza/api";
import { formatDateTime, formatDay, type TFunction, useTranslation } from "@mwangaza/i18n";
import { amountInWords, type Currency, formatAmount, formatRate } from "@mwangaza/money";
import { Fragment, type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { localDevice } from "../../lib/device";
import { fullName } from "../../lib/people";
import { type School, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { QrCode } from "../auth/QrCode";
import { headerLines } from "../settings/ReceiptCard";
import "./receipt.css";
import { receiptQr } from "./receiptQr";

export type Receipt = Schemas["PaymentReceipt"];
/** `reprintedAt` : duplicata (F6) ; `test` : reçu d'essai de l'imprimante, sans valeur. */
export type PrintJob = { payment: Receipt; reprintedAt?: string; test?: boolean };
/** `qr` : adresse du QR code, signée sur un appareil mémorisé. */
type Printing = PrintJob & { qr: string };

// Au-delà, le logo manquant ne retient plus l'impression.
const IMAGE_WAIT_MS = 2000;

export function amounts(items: { currency: string; minor: number }[], nothing: string): string {
  const due = items.filter((item) => item.minor > 0);
  if (!due.length) return nothing;
  return due.map((item) => formatAmount(item.minor, item.currency as Currency)).join(" + ");
}

function ReceiptCopy({ job, school, copy }: { job: Printing; school: School; copy?: number }) {
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
  const { host } = window.location;
  const id = payment.id;
  // Signé : plus de modules, dessinés plus grands pour rester lisibles sur un ticket thermique.
  const qr = (
    <div
      className={job.qr.includes("?") ? "receipt__qr receipt__qr--dense" : "receipt__qr"}
      data-url={job.qr}
    >
      <QrCode value={job.qr} label={t("cash.receipt.qr")} />
    </div>
  );
  const when = (value: string) => formatDateTime(value, i18n.language, school.timezone);
  const balance = payment.balance.currencies;

  return (
    <article className="receipt">
      {school.environment !== "live" && (
        <p className="receipt__mark">
          <strong>{t("space.specimen")}</strong>
        </p>
      )}
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
        {payment.student.matricule && (
          <div>
            <dt>{t("cash.receipt.matricule")}</dt>
            <dd>{payment.student.matricule}</dd>
          </div>
        )}
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

/** Les exemplaires d'un reçu sur la page (`copy(index)` : un exemplaire ; reçu de paiement ou
 * d'annulation) : ticket (séparés par un trait de découpe) ou feuille A4 découpée en cases A6,
 * A5 ou petit format. */
export function ReceiptPages({
  school,
  copy,
}: {
  school: School;
  copy: (index: number | undefined) => ReactNode;
}) {
  const { printer, sheet_size, copies } = school.receipt;
  const items = Array.from({ length: copies }, (_, index) => (
    <Fragment key={index}>{copy(copies > 1 ? index : undefined)}</Fragment>
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

/** Adresse du QR code, signée avec la clé de l'appareil mémorisé du compte s'il y en a un ;
 *  jamais pour le reçu d'essai, sans valeur. */
async function withQr(job: PrintJob, user: string): Promise<Printing> {
  const { origin } = window.location;
  try {
    const key = job.test ? undefined : (await localDevice(user))?.privateKey;
    return { ...job, qr: await receiptQr(origin, job.payment, key) };
  } catch {
    // Clé illisible : le reçu s'imprime quand même, vérifiable une fois synchronisé.
    return { ...job, qr: await receiptQr(origin, job.payment) };
  }
}

/** Impression dans le navigateur : `print(job)` place `render(job)` dans la zone d'impression
 *  (cachée à l'écran) et, les images chargées, lance `window.print()` ; `area` se place dans
 *  l'écran. */
export function usePrintArea<T extends object>(
  render: (job: T) => ReactNode,
): { print: (job: T) => void; area: ReactNode } {
  const [job, setJob] = useState<T | null>(null);

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
    ? createPortal(<div className="print-area">{render(job)}</div>, document.body)
    : null;
  return { print: setJob, area };
}

/** `print(job)` imprime le reçu ; `area` (zone d'impression) se place dans l'écran. */
export function useReceiptPrinter(): { print: (job: PrintJob) => void; area: ReactNode } {
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const { print, area } = usePrintArea<Printing>((job) => (
    <ReceiptPages
      school={school}
      copy={(index) => <ReceiptCopy job={job} school={school} copy={index} />}
    />
  ));
  return { print: (next) => void withQr(next, me.id).then(print), area };
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
    origin: "cash",
    enrollment: "",
    student: { id: "", full_name: t("cash.receipt.sample.student"), matricule: "0000" },
    class_group: t("cash.receipt.sample.classGroup"),
    cash_register: "",
    cash_register_name: registerName,
    cash_session: "",
    cashier,
    received_amount_minor: amount,
    received_currency: currency,
    rate_used: null,
    paid_at: now,
    method: "cash",
    note: "",
    cancelled: false,
    cancelled_at: null,
    cancellation_pending: false,
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
