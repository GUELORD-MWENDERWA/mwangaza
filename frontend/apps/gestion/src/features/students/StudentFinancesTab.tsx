// Onglet « Finances » de la fiche élève : chiffres clés de l'année et ce que doit l'élève (2.6),
// avec sa part des réductions (E3), le payé, le reste et l'état de chaque échéance (2.7) ; avec
// le droit `finance.grant_discount`, l'échéancier particulier (E4) et les réductions à accorder
// ou retirer ; ses crédits à traiter (M14, 3.6.2), avec un lien pour qui peut les traiter.
// Paiements : caisse (3.1).
import { formatDate, formatDay, useTranslation } from "@mwangaza/i18n";
import { formatAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Kpi,
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
import { StudentCredits } from "../credits/StudentCredits";
import { LoadError } from "../status/StatusPages";
import {
  type Balance,
  CHARGES_READ,
  type Discount,
  type Student,
  useBalance,
  useCharges,
  useDiscounts,
  useStudentCredits,
} from "./data";
import { DiscountDialog, RevokeDiscountDialog } from "./DiscountDialog";

type Enrollment = Student["enrollments"][number];

/** Échéancier que l'écran « Échéancier particulier » vient d'enregistrer (état de navigation). */
export type Scheduled = { fee: string; count: number };

const TONES = { active: "info", removed: "gray", replaced: "warn" } as const;
const STATE_TONES = { paid: "ok", overdue: "due", upcoming: "gray" } as const;

type Amounts = (item: Balance["currencies"][number]) => number;

/** Chiffres clés de l'année (maquette `eleve-fiche`), par devise sans jamais les additionner :
 * la première en grand, l'autre en dessous (« + 30 000 FC »). */
function BalanceKpis({ balance }: { balance: Balance }) {
  const { t, i18n } = useTranslation();
  const amounts = (pick: Amounts) => {
    const listed = balance.currencies.filter((item) => pick(item) > 0);
    const [first, ...others] = (listed.length ? listed : balance.currencies.slice(0, 1)).map(
      (item) => formatAmount(pick(item), item.currency as Currency),
    );
    return { value: first, sub: others.map((text) => `+ ${text}`).join(" ") || undefined };
  };
  const overdue = balance.currencies.some((item) => item.overdue_minor > 0);
  const next = amounts((item) => item.next_due_minor);
  return (
    <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
      <Kpi label={t("students.finances.kpi.total")} {...amounts((item) => item.total_minor)} />
      <Kpi
        label={t("students.finances.kpi.paid")}
        tone="ok"
        {...amounts((item) => item.paid_minor)}
      />
      <Kpi
        label={t("students.finances.kpi.overdue")}
        tone={overdue ? "due" : undefined}
        {...amounts((item) => item.overdue_minor)}
      />
      <Kpi
        label={t("students.finances.kpi.next")}
        value={
          balance.next_due_on
            ? formatDay(balance.next_due_on, i18n.language)
            : t("students.finances.kpi.none")
        }
        sub={balance.next_due_on ? [next.value, next.sub].filter(Boolean).join(" ") : undefined}
      />
    </div>
  );
}

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
  const balance = useBalance(allowed ? enrollment?.id : undefined);
  const credits = useStudentCredits(allowed ? enrollment?.id : undefined);
  const title = t("students.card.tabs.finances");

  if (!allowed || !enrollment)
    return (
      <StateCard icon="wallet" tone="lake" title={title}>
        {t(allowed ? "students.finances.notEnrolled" : "students.card.financesRight")}
      </StateCard>
    );
  const error = charges.error ?? discounts.error ?? balance.error ?? credits.error;
  if (error)
    return (
      <LoadError
        error={error}
        onRetry={() =>
          void Promise.all([
            charges.refetch(),
            discounts.refetch(),
            balance.refetch(),
            credits.refetch(),
          ])
        }
      />
    );
  if (!charges.data || !discounts.data || !balance.data || !credits.data)
    return <Skeleton label={t("common.loading")} />;
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
      <StudentCredits
        credits={credits.data}
        canProcess={can(me, ["finance.view_reports", "finance.approve_cancellation"])}
      />
      {balance.data.currencies.length > 0 && <BalanceKpis balance={balance.data} />}
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
                  <th className="text-right">{t("students.discount.columns.discount")}</th>
                )}
                <th className="text-right">{t("students.finances.columns.paid")}</th>
                <th className="text-right">{t("students.finances.columns.left")}</th>
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
                    <td className="num">
                      {charge.discount_minor > 0 &&
                        `− ${formatAmount(charge.discount_minor, charge.currency as Currency)}`}
                    </td>
                  )}
                  <td className="num">
                    {charge.state && formatAmount(charge.paid_minor, charge.currency as Currency)}
                  </td>
                  <td className="num font-bold">
                    {charge.state &&
                      formatAmount(charge.remaining_minor, charge.currency as Currency)}
                  </td>
                  <td>
                    {charge.state ? (
                      <StatusPill tone={STATE_TONES[charge.state]}>
                        {t(`students.finances.state.${charge.state}`)}
                      </StatusPill>
                    ) : (
                      <StatusPill tone={TONES[charge.status]}>
                        {t(`students.finances.status.${charge.status}`)}
                      </StatusPill>
                    )}
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
