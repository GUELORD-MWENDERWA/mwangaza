// Reçu d'annulation (M15, maquette `recu-annulation`) imprimé dans le navigateur au format de
// reçu de l'école, comme le reçu du paiement : reçu annulé, élève, répartition annulée, montant
// en chiffres et en lettres, motif, reste dû juste après l'annulation, demandeur et validateur,
// QR code vers la vérification du reçu annulé (qui le dit annulé). Réimpression : DUPLICATA.
import type { Schemas } from "@mwangaza/api";
import { formatDateTime, useTranslation } from "@mwangaza/i18n";
import { amountInWords, type Currency, formatAmount } from "@mwangaza/money";
import type { ReactNode } from "react";

import { fullName } from "../../lib/people";
import type { School } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { QrCode } from "../auth/QrCode";
import { amounts, ReceiptPages, usePrintArea } from "../cash/Receipt";
import { headerLines } from "../settings/ReceiptCard";
import "../cash/receipt.css";

export type CancellationReceipt = Schemas["CancellationReceipt"];
/** `reprintedAt` : duplicata. */
export type CancellationJob = { cancellation: CancellationReceipt; reprintedAt?: string };

function CancellationCopy({
  job,
  school,
  copy,
}: {
  job: CancellationJob;
  school: School;
  copy?: number;
}) {
  const { t, i18n } = useTranslation();
  const { cancellation: item, reprintedAt } = job;
  const { payment } = item;
  const done = item.cancellation!;
  const thermal = school.receipt.printer !== "sheet";
  const logo = thermal ? (school.logo_monochrome ?? school.logo) : school.logo;
  const received = payment.received_currency as Currency;
  const when = (value: string) => formatDateTime(value, i18n.language, school.timezone);
  const url = `${window.location.origin}/v/${payment.id}`;
  const qr = (
    <div className="receipt__qr" data-url={url}>
      <QrCode value={url} label={t("cash.receipt.qr")} />
    </div>
  );
  const row = (label: string, value: ReactNode) => (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );

  return (
    <article className="receipt">
      {reprintedAt && (
        <p className="receipt__mark">
          <strong>{t("cash.receipt.duplicate")}</strong>
          {t("cash.receipt.reprinted", { date: when(reprintedAt) })}
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
      <p className="receipt__mark">
        <strong>{t("cancellations.receipt.mark")}</strong>
      </p>
      <p className="receipt__title">
        <b>{t("cancellations.receipt.title", { number: done.receipt_number })}</b>
        <span>{when(done.approved_at)}</span>
      </p>
      <p>
        {t("cancellations.receipt.cancels", {
          number: payment.receipt_number,
          date: when(payment.paid_at),
          register: payment.cash_register_name,
        })}
      </p>
      <dl className="receipt__rows">
        {row(t("cash.receipt.student"), <b>{payment.student.full_name}</b>)}
        {payment.student.matricule && row(t("cash.receipt.matricule"), payment.student.matricule)}
        {row(t("cash.receipt.classGroup"), payment.class_group)}
      </dl>
      <table className="receipt__lines">
        <tbody>
          {payment.allocations.map((line) => (
            <tr key={line.student_charge}>
              <td>{`${line.fee_type_name} · ${line.label}`}</td>
              <td>{`− ${formatAmount(line.amount_minor, line.currency as Currency)}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="receipt__total">
        <span>{t("cancellations.receipt.total")}</span>
        <span>{formatAmount(payment.received_amount_minor, received)}</span>
      </p>
      <p className="receipt__words">{amountInWords(payment.received_amount_minor, received)}</p>
      <p>{t("cancellations.receipt.reason", { reason: item.reason })}</p>
      <dl className="receipt__rows receipt__rule">
        {row(
          t("cancellations.receipt.remaining"),
          amounts(
            item.balance.currencies.map((c) => ({
              currency: c.currency,
              minor: c.remaining_minor,
            })),
            t("cash.receipt.nothing"),
          ),
        )}
      </dl>
      <div className="receipt__sign">
        <p>
          {t("cancellations.receipt.requestedBy")}
          <br />
          <b>{fullName(item.requested_by)}</b> · {payment.cash_register_name}
        </p>
        <p>
          {t("cancellations.receipt.approvedBy")}
          <br />
          <b>{fullName(done.approved_by)}</b>
        </p>
      </div>
      <p className="receipt__stamp">{t("cancellations.receipt.parent")}</p>
      {thermal && qr}
      <p className="receipt__foot receipt__verify">
        {t("cash.receipt.verify", {
          url: `${window.location.host}/v/${payment.id.slice(0, 4)}…${payment.id.slice(-3)}`,
        })}
      </p>
      <p className="receipt__foot">
        {t("cancellations.receipt.void", { number: payment.receipt_number })}
      </p>
      {copy !== undefined && (
        <p className="receipt__copy">
          {t(copy === 0 ? "cash.receipt.studentCopy" : "cash.receipt.schoolCopy")}
        </p>
      )}
    </article>
  );
}

/** `print(job)` imprime le reçu d'annulation ; `area` se place dans l'écran. */
export function useCancellationPrinter() {
  const school = useCurrentSchool();
  return usePrintArea<CancellationJob>((job) => (
    <ReceiptPages
      school={school}
      copy={(index) => <CancellationCopy job={job} school={school} copy={index} />}
    />
  ));
}
