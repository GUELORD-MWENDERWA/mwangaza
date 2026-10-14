import {
  errorMessage,
  formatDate,
  formatDay,
  formatPhone,
  Trans,
  useTranslation,
} from "@mwangaza/i18n";
import { formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  Kpi,
  Skeleton,
  StatusPill,
} from "@mwangaza/ui";
import { useParams } from "react-router";

import { type ChildFee, type ChildPayments, receiptUrl, useChild } from "../../lib/families";
import { PortalFrame } from "../home/PortalFrame";
import { ChildAvatar } from "./ChildAvatar";

const TONES = {
  paid: "ok",
  paid_early: "ok",
  partial: "warn",
  overdue: "due",
  upcoming: "gray",
} as const satisfies Record<ChildFee["state"], string>;

/** Paiements d'un enfant (maquette `enfant-paiements`, H3) : payé et reste par devise (jamais
 *  additionnés), retard, prochaine échéance, détail des frais, reçus en PDF. Onglets Scolarité
 *  (V1.2) et Profil : pas encore. */
export function ChildPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const child = useChild(id);
  const data = child.data;

  return (
    <PortalFrame
      wide
      title={data?.full_name ?? ""}
      subtitle={data && `${data.school_name} · ${data.class_name} · ${data.academic_year}`}
      aside={data && <ChildAvatar name={data.full_name} photo={data.photo} className="size-10" />}
      childId={id}
    >
      {child.isPending && <Skeleton label={t("common.loading")} />}
      {child.isError && (
        <div className="flex flex-col gap-3">
          <Banner tone="due">{errorMessage(child.error, t)}</Banner>
          <Button variant="outline" onClick={() => void child.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {data && <Payments child={data} />}
    </PortalFrame>
  );
}

/** « 330,00 $ » en grand, « + 30 000 FC » en dessous. */
function kpi(amounts: string[]) {
  const [value = "—", ...rest] = amounts;
  return { value, sub: rest.length ? `+ ${rest.join(" + ")}` : undefined };
}

function Payments({ child }: { child: ChildPayments }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { balance, fees, payments } = child;
  const lines = balance.currencies;
  const overdue = lines.filter((line) => line.overdue_minor > 0);
  const firstOverdue = fees.find((fee) => fee.state === "overdue");
  const next = fees.filter(
    (fee) => fee.due_on === balance.next_due_on && fee.state !== "paid_early",
  );

  // Ordinateur : résumé à gauche, détail et reçus à droite ; téléphone : le même ordre en colonne.
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[360px_minmax(0,1fr)] lg:items-start lg:gap-6">
      <div className="flex flex-col gap-4">
        {lines.length > 0 && (
          <div className="grid gap-2.5 sm:grid-cols-2">
            <Kpi
              label={t("portal.child.paid")}
              tone="ok"
              {...kpi(lines.map((line) => formatAmount(line.paid_minor, line.currency)))}
            />
            <Kpi
              label={t("portal.child.remaining")}
              {...kpi(lines.map((line) => formatAmount(line.remaining_minor, line.currency)))}
            />
          </div>
        )}
        {overdue.length > 0 && firstOverdue && (
          <Banner tone="due">
            <span>
              <Trans
                i18nKey="portal.child.overdueSince"
                values={{
                  amount: overdue
                    .map((line) => formatAmount(line.overdue_minor, line.currency))
                    .join(" + "),
                  date: formatDay(firstOverdue.due_on, language),
                }}
                components={{ b: <b /> }}
              />
            </span>
          </Banner>
        )}
        {next.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>{t("portal.child.nextDue")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {next.map((fee) => (
                <div key={fee.id} className="flex justify-between gap-3">
                  <span>
                    {formatDay(fee.due_on, language)} · {fee.fee}
                  </span>
                  <b className="tabular-nums">{formatAmount(fee.remaining_minor, fee.currency)}</b>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
        {child.homeroom_teacher && (
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-2 py-3.5">
              <div className="min-w-0">
                <span className="block text-xs text-ink-3">{t("portal.child.teacher")}</span>
                <b>{child.homeroom_teacher.name}</b>
              </div>
              {child.homeroom_teacher.phone && (
                <a
                  href={`tel:${child.homeroom_teacher.phone}`}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  <Icon name="phone" size={16} />
                  {formatPhone(child.homeroom_teacher.phone)}
                </a>
              )}
            </CardContent>
          </Card>
        )}
      </div>
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("portal.child.fees")}</CardTitle>
          </CardHeader>
          <CardContent className="py-1">
            {fees.length === 0 && <p className="py-3 text-ink-3">{t("portal.child.noFees")}</p>}
            <ul className="divide-y divide-line">
              {fees.map((fee) => (
                <li key={fee.id} className="flex justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <b className="block text-md">{fee.fee}</b>
                    <span className="text-xs text-ink-3">
                      {t("portal.child.dueOn", { date: formatDay(fee.due_on, language) })}
                    </span>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <b className="text-md whitespace-nowrap tabular-nums">
                      {fee.remaining_minor > 0 && fee.remaining_minor < fee.amount_minor
                        ? t("portal.child.left", {
                            amount: formatAmount(fee.remaining_minor, fee.currency),
                          })
                        : formatAmount(fee.amount_minor, fee.currency)}
                    </b>
                    <StatusPill tone={TONES[fee.state]}>
                      {t(`portal.child.states.${fee.state}`)}
                    </StatusPill>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("portal.child.receipts")}</CardTitle>
          </CardHeader>
          <CardContent className="py-1">
            {payments.length === 0 && (
              <p className="py-3 text-ink-3">{t("portal.child.noReceipts")}</p>
            )}
            <ul className="divide-y divide-line">
              {payments.map((payment) => (
                <li key={payment.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <b className="block text-md break-all">
                      {payment.origin === "prior"
                        ? t("portal.child.prior")
                        : payment.receipt_number}
                    </b>
                    <span className="text-xs text-ink-3 tabular-nums">
                      {formatDate(payment.paid_at, language, child.school_timezone)} ·{" "}
                      {formatAmount(payment.received_amount_minor, payment.received_currency)}
                    </span>
                  </div>
                  {payment.cancelled ? (
                    <StatusPill tone="gray">{t("portal.child.cancelled")}</StatusPill>
                  ) : payment.origin === "prior" ? null : (
                    <a
                      href={receiptUrl(payment.id)}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={t("portal.child.pdfLabel", { number: payment.receipt_number })}
                      className={buttonVariants({ variant: "outline", size: "sm" })}
                    >
                      <Icon name="download" size={16} />
                      {t("portal.child.pdf")}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
