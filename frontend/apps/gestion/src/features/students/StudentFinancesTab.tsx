// Onglet « Finances » de la fiche élève : ce que doit l'élève cette année (2.6), avec sa part des
// réductions (E3), et, avec le droit `finance.grant_discount`, l'échéancier particulier (E4) et
// les réductions à accorder ou retirer. Payé, reste et paiements : 2.7 et caisse (3.1).
import { formatDate, formatDay, useTranslation } from "@mwangaza/i18n";
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
import { useState } from "react";
import { Link, useLocation } from "react-router";

import { can } from "../../lib/permissions";
import { fullName } from "../../lib/people";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { CHARGES_READ, type Discount, type Student, useCharges, useDiscounts } from "./data";
import { DiscountDialog, RevokeDiscountDialog } from "./DiscountDialog";

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
  const school = useCurrentSchool();
  const scheduled = (useLocation().state as { scheduled?: Scheduled } | null)?.scheduled;
  const [granting, setGranting] = useState(false);
  const [granted, setGranted] = useState(false);
  const [revoking, setRevoking] = useState<Discount | null>(null);
  const allowed = can(me, CHARGES_READ);
  const charges = useCharges(allowed ? enrollment?.id : undefined);
  const discounts = useDiscounts(allowed ? enrollment?.id : undefined);
  const title = t("students.card.tabs.finances");

  if (!allowed || !enrollment)
    return (
      <StateCard icon="wallet" tone="lake" title={title}>
        {t(allowed ? "students.finances.notEnrolled" : "students.card.financesRight")}
      </StateCard>
    );
  const error = charges.error ?? discounts.error;
  if (error)
    return (
      <LoadError
        error={error}
        onRetry={() => void Promise.all([charges.refetch(), discounts.refetch()])}
      />
    );
  if (!charges.data || !discounts.data) return <Skeleton label={t("common.loading")} />;
  const canGrant = can(me, ["finance.grant_discount"]);
  const canSchedule =
    enrollment.status === "active" &&
    canGrant &&
    charges.data.some((charge) => charge.status === "active");
  const live = discounts.data.filter((discount) => !discount.revoked_at);
  const discounted = charges.data.some((charge) => charge.discount_minor > 0);
  const describe = (discount: Discount) =>
    [
      t(`students.discount.reasons.${discount.reason_code}`),
      discount.kind === "percent"
        ? t("students.discount.percent", { value: discount.percent })
        : formatAmount(discount.amount_minor!, discount.currency as Currency),
      discount.fee_type_name ?? t("students.discount.allFees"),
    ].join(" · ");

  return (
    <>
      {scheduled && (
        <Banner tone="ok" role="status">
          {t("students.schedule.saved", scheduled)}
        </Banner>
      )}
      {granted && (
        <Banner tone="ok" role="status">
          {t("students.discount.granted")}
        </Banner>
      )}
      <Card>
        <CardHeader className="flex-wrap">
          <CardTitle>{t("students.finances.due")}</CardTitle>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-3">
            {live.length === 0 && t("students.discount.none")}
            {canSchedule && (
              <button
                type="button"
                className="text-lake underline"
                onClick={() => {
                  setGranted(false);
                  setGranting(true);
                }}
              >
                {t("students.discount.add")}
              </button>
            )}
            {canSchedule && (
              <Link
                to={`/students/${student.id}/finances/schedule`}
                className="text-lake underline"
              >
                {t("students.finances.schedule")}
              </Link>
            )}
          </span>
        </CardHeader>
        {live.length > 0 && (
          <CardContent>
            <ul className="flex flex-col divide-y divide-line">
              {live.map((discount) => (
                <li key={discount.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                  <span className="font-bold">{describe(discount)}</span>
                  <span className="text-sm text-ink-2">{discount.reason}</span>
                  <span className="text-sm text-ink-3">
                    {t("students.discount.grantedOn", {
                      name: discount.granted_by ? fullName(discount.granted_by) : "—",
                      date: formatDate(discount.granted_at, i18n.language, school.timezone),
                    })}
                  </span>
                  {canGrant && (
                    <button
                      type="button"
                      className="ml-auto text-sm text-due underline"
                      onClick={() => setRevoking(discount)}
                    >
                      {t("students.discount.revoke")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        )}
        {charges.data.length === 0 ? (
          <CardContent className="text-sm text-ink-3">{t("students.finances.empty")}</CardContent>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>{t("students.finances.columns.fee")}</th>
                <th>{t("students.finances.columns.dueOn")}</th>
                <th className="text-right">{t("students.finances.columns.amount")}</th>
                {discounted && (
                  <>
                    <th className="text-right">{t("students.discount.columns.discount")}</th>
                    <th className="text-right">{t("students.discount.columns.after")}</th>
                  </>
                )}
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
                  {discounted && (
                    <>
                      <td className="num">
                        {charge.discount_minor > 0 &&
                          `− ${formatAmount(charge.discount_minor, charge.currency as Currency)}`}
                      </td>
                      <td className="num font-bold">
                        {charge.status === "active" &&
                          formatAmount(
                            charge.amount_minor - charge.discount_minor,
                            charge.currency as Currency,
                          )}
                      </td>
                    </>
                  )}
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
      {granting && (
        <DiscountDialog
          student={student}
          enrollment={enrollment}
          charges={charges.data}
          discounts={discounts.data}
          onClose={() => setGranting(false)}
          onGranted={() => {
            setGranting(false);
            setGranted(true);
          }}
        />
      )}
      {revoking && <RevokeDiscountDialog discount={revoking} onClose={() => setRevoking(null)} />}
    </>
  );
}
