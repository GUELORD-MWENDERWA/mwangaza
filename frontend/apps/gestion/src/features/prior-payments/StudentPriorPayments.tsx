// Onglet Finances de la fiche élève : ce qui a été repris en cours d'année (E6), avec la
// demande d'annulation habituelle pour corriger une erreur. Rien si l'élève n'a pas de reprise.
import { formatDate, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import { Button, Card, CardHeader, CardTitle, StatusPill, Table } from "@mwangaza/ui";
import { Link } from "react-router";

import { useCurrentSchool } from "../../lib/school";
import { usePriorPayments } from "./data";

export function StudentPriorPayments({
  enrollment,
  canRequest,
}: {
  enrollment: string | undefined;
  canRequest: boolean;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const payments = usePriorPayments(enrollment);
  const results = payments.data?.results ?? [];
  if (results.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("priorPayments.label")}</CardTitle>
      </CardHeader>
      <Table>
        <tbody>
          {results.map((payment) => (
            <tr key={payment.id}>
              <td>
                <b>{payment.receipt_number}</b>
                <span className="block text-sm text-ink-3">
                  {t("priorPayments.student.recordedOn", {
                    date: formatDate(payment.paid_at, i18n.language, school.timezone),
                  })}
                </span>
              </td>
              <td className="text-right font-bold tabular-nums">
                {formatAmount(payment.received_amount_minor, payment.received_currency as Currency)}
              </td>
              <td className="text-right">
                {payment.cancelled ? (
                  <StatusPill tone="gray">{t("priorPayments.student.cancelled")}</StatusPill>
                ) : payment.cancellation_pending ? (
                  <StatusPill tone="warn">{t("priorPayments.student.pending")}</StatusPill>
                ) : (
                  canRequest && (
                    <Button asChild variant="outline" size="sm">
                      <Link to={`/cancellations?payment=${payment.id}`}>
                        {t("priorPayments.student.cancel")}
                      </Link>
                    </Button>
                  )
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}
