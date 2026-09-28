// Onglet « Finances » de la fiche élève : ce que doit l'élève cette année (2.6), avec le lien
// vers l'échéancier particulier (E4, droit `finance.grant_discount`). Payé, reste, paiements et
// réductions viendront avec la 2.5.2, la 2.7 et la caisse (3.1).
import { formatDay, useTranslation } from "@mwangaza/i18n";
import { formatAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  StateCard,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { Link, useLocation } from "react-router";

import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import { CHARGES_READ, type Student, useCharges } from "./data";

type Enrollment = Student["enrollments"][number];

/** Échéancier que l'écran « Échéancier particulier » vient d'enregistrer (état de navigation). */
export type Scheduled = { fee: string; count: number };

const TONES = { active: "info", removed: "gray", replaced: "warn" } as const;

export function StudentFinancesTab({
  student,
  enrollment,
}: {
  student: Student;
  enrollment: Enrollment | undefined;
}) {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const scheduled = (useLocation().state as { scheduled?: Scheduled } | null)?.scheduled;
  const allowed = can(me, CHARGES_READ);
  const charges = useCharges(allowed ? enrollment?.id : undefined);
  const title = t("students.card.tabs.finances");

  if (!allowed || !enrollment)
    return (
      <StateCard icon="wallet" tone="lake" title={title}>
        {t(allowed ? "students.finances.notEnrolled" : "students.card.financesRight")}
      </StateCard>
    );
  if (charges.error)
    return <LoadError error={charges.error} onRetry={() => void charges.refetch()} />;
  if (!charges.data) return <Skeleton label={t("common.loading")} />;
  const canSchedule =
    enrollment.status === "active" &&
    can(me, ["finance.grant_discount"]) &&
    charges.data.some((charge) => charge.status === "active");

  return (
    <>
      {scheduled && (
        <Banner tone="ok" role="status">
          {t("students.schedule.saved", scheduled)}
        </Banner>
      )}
      <Card>
        <CardHeader className="flex-wrap">
          <CardTitle>{t("students.finances.due")}</CardTitle>
          {canSchedule && (
            <Link
              to={`/students/${student.id}/finances/schedule`}
              className="text-sm text-lake underline"
            >
              {t("students.finances.schedule")}
            </Link>
          )}
        </CardHeader>
        {charges.data.length === 0 ? (
          <CardContent className="text-sm text-ink-3">{t("students.finances.empty")}</CardContent>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>{t("students.finances.columns.fee")}</th>
                <th>{t("students.finances.columns.dueOn")}</th>
                <th className="text-right">{t("students.finances.columns.amount")}</th>
                <th>{t("students.finances.columns.status")}</th>
              </tr>
            </thead>
            <tbody>
              {charges.data.map((charge) => (
                <tr key={charge.id} className={charge.status === "active" ? "" : "text-ink-3"}>
                  <td>
                    {charge.label === charge.fee_type_name
                      ? charge.label
                      : `${charge.fee_type_name} · ${charge.label}`}
                    {charge.source === "custom" && (
                      <Tag className="ml-2">{t("students.finances.custom")}</Tag>
                    )}
                  </td>
                  <td className="tabular-nums">{formatDay(charge.due_on, i18n.language)}</td>
                  <td className="num">
                    {formatAmount(charge.amount_minor, charge.currency as Currency)}
                  </td>
                  <td>
                    <StatusPill tone={TONES[charge.status]}>
                      {t(`students.finances.status.${charge.status}`)}
                    </StatusPill>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
        <CardContent className="text-sm text-ink-3">{t("students.finances.later")}</CardContent>
      </Card>
    </>
  );
}
