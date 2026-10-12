import { errorMessage, formatDay, formatVisit, useTranslation } from "@mwangaza/i18n";
import { formatAmount } from "@mwangaza/money";
import { Banner, Button, buttonVariants, Card, CardContent, Icon, Skeleton } from "@mwangaza/ui";
import { useState } from "react";
import { Link, useOutletContext } from "react-router";

import type { Account } from "../../lib/account";
import { type Child, type LinkedFamily, useFamilies } from "../../lib/families";
import { shouldOfferInstall } from "../../lib/install";
import { LanguageLinks } from "../auth/AuthFrame";
import { useSummons } from "../calendar/data";
import { ChildAvatar } from "../child/ChildAvatar";
import { PortalFrame } from "./PortalFrame";

/** Accueil (maquette `accueil`, H2) : une carte par enfant, toutes écoles reliées ; chaque carte
 *  ne montre que les données de l'école de l'enfant et ouvre ses paiements ; annonces récentes :
 *  4.4.4. */
export function HomePage() {
  const { t } = useTranslation();
  const account = useOutletContext<Account>();
  const families = useFamilies();
  const [offerInstall] = useState(() => shouldOfferInstall());

  return (
    <PortalFrame subtitle={t("portal.home.greeting", { name: account.name })}>
      {offerInstall && (
        <Banner tone="lamp" icon="phone" className="items-center">
          <span className="flex-1">{t("portal.home.installBanner")}</span>
          <Link to="/install" className={buttonVariants({ variant: "outline", size: "sm" })}>
            {t("portal.home.installAction")}
          </Link>
        </Banner>
      )}
      <SummonsBanner />
      <h2 className="text-[1.25rem]">{t("portal.home.children")}</h2>
      {families.isPending && <Skeleton label={t("common.loading")} />}
      {families.isError && (
        <div className="flex flex-col gap-3">
          <Banner tone="due">{errorMessage(families.error, t)}</Banner>
          <Button variant="outline" onClick={() => void families.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {families.data?.map((family) => (
        <FamilyCards key={family.id} family={family} />
      ))}
      <Link to="/add-school" className={buttonVariants({ variant: "outline" })}>
        <Icon name="plus" size={16} />
        {t("portal.home.addSchool")}
      </Link>
      <LanguageLinks />
    </PortalFrame>
  );
}

/** Convocation à venir (5.7) : le parent la voit dès l'accueil, même sans notification. */
function SummonsBanner() {
  const { t } = useTranslation();
  const summons = useSummons().data?.results ?? [];
  const [next] = summons.filter((item) => new Date(item.meeting_at) >= new Date());
  if (!next) return null;
  return (
    <Banner tone="warn" icon="calendar" className="items-center">
      <span className="flex-1">{t("portal.home.summons", { name: next.student_name })}</span>
      <Link to="/calendar" className={buttonVariants({ variant: "outline", size: "sm" })}>
        {t("portal.home.summonsAction")}
      </Link>
    </Banner>
  );
}

/** Les enfants d'une famille ; école suspendue ou accès suspendu par l'école : son nom seul. */
function FamilyCards({ family }: { family: LinkedFamily }) {
  const { t } = useTranslation();
  if (family.status !== "active" || family.children.length === 0) {
    const message = {
      active: t("portal.home.noChildren"),
      suspended: t("portal.home.suspended"),
      school_unavailable: t("portal.home.unavailable"),
    }[family.status];
    return (
      <Card>
        <CardContent className="flex flex-col gap-3">
          <b>{family.school_name}</b>
          <Banner tone={family.status === "active" ? "info" : "warn"}>{message}</Banner>
        </CardContent>
      </Card>
    );
  }
  return family.children.map((child) => <ChildCard key={child.id} child={child} family={family} />);
}

function ChildCard({ child, family }: { child: Child; family: LinkedFamily }) {
  const { t, i18n } = useTranslation();
  const { balance, last_payment: last } = child;
  const overdue = balance.currencies.filter((line) => line.overdue_minor > 0);

  return (
    <Link to={`/children/${child.id}`} className="text-inherit no-underline">
      <Card>
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <ChildAvatar
              name={child.full_name}
              photo={child.photo}
              className="size-14 text-[1.1rem]"
            />
            <div className="min-w-0 flex-1">
              <b className="block">{child.full_name}</b>
              <span className="text-[.88rem] text-ink-3">
                {family.school_name} · {child.class_name}
              </span>
            </div>
          </div>
          {overdue.length > 0 ? (
            <Banner tone="due">
              <span>
                {t("portal.home.overdue")}{" "}
                <b>
                  {overdue
                    .map((line) => formatAmount(line.overdue_minor, line.currency))
                    .join(" + ")}
                </b>
                {child.first_overdue && ` (${child.first_overdue})`}
              </span>
            </Banner>
          ) : (
            <Banner tone="ok">
              {balance.next_due_on
                ? t("portal.home.upToDateNext", {
                    date: formatDay(balance.next_due_on, i18n.language),
                  })
                : t("portal.home.upToDate")}
            </Banner>
          )}
          {balance.currencies.map((line) => {
            const percent = line.total_minor ? (line.paid_minor * 100) / line.total_minor : 100;
            return (
              <div key={line.currency} className="text-[.88rem]">
                <div className="flex justify-between gap-3">
                  <span>{t("portal.home.paidThisYear")}</span>
                  <b className="tabular-nums">
                    {t("portal.home.paidOf", {
                      paid: formatAmount(line.paid_minor, line.currency),
                      total: formatAmount(line.total_minor, line.currency),
                    })}
                  </b>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-gray-50">
                  <div className="h-full rounded-full bg-ok" style={{ width: `${percent}%` }} />
                </div>
              </div>
            );
          })}
          {last && (
            <div className="flex justify-between gap-3 text-[.88rem]">
              <span className="text-ink-3">{t("portal.home.lastPayment")}</span>
              <span className="tabular-nums">
                {formatAmount(last.received_amount_minor, last.received_currency)} ·{" "}
                {formatVisit(last.paid_at, i18n.language, family.school_timezone, (time) =>
                  t("portal.home.today", { time }),
                )}
              </span>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
