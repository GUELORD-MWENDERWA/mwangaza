import { errorMessage, formatDate, formatDay, formatVisit, useTranslation } from "@mwangaza/i18n";
import { formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardContent,
  CardFooter,
  DESKTOP,
  Icon,
  Skeleton,
  useMediaQuery,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link, useOutletContext } from "react-router";

import type { Account } from "../../lib/account";
import { type Child, type LinkedFamily, useFamilies } from "../../lib/families";
import { shouldOfferInstall } from "../../lib/install";
import { useAnnouncements } from "../announcements/data";
import { LanguageLinks } from "../auth/AuthFrame";
import { useSummons } from "../calendar/data";
import { ChildAvatar } from "../child/ChildAvatar";
import { PlaceOffers } from "./PlaceOffers";
import { PortalFrame } from "./PortalFrame";

/** Accueil (maquette `accueil`, H2) : une carte par enfant, toutes écoles reliées ; chaque carte
 *  ne montre que les données de l'école de l'enfant et ouvre ses paiements ; annonces récentes :
 *  4.4.4. */
export function HomePage() {
  const { t } = useTranslation();
  const account = useOutletContext<Account>();
  const families = useFamilies();
  const [offerInstall] = useState(() => shouldOfferInstall());
  const desktop = useMediaQuery(DESKTOP);

  return (
    <PortalFrame wide subtitle={t("portal.home.greeting", { name: account.name })}>
      {offerInstall && (
        <Banner
          tone="lamp"
          icon="phone"
          action={
            <Link to="/install" className={buttonVariants({ variant: "outline", size: "sm" })}>
              {t("portal.home.installAction")}
            </Link>
          }
        >
          {t("portal.home.installBanner")}
        </Banner>
      )}
      <SummonsBanner />
      {/* Ordinateur : enfants à gauche (deux par rangée dès la tablette), annonces à droite. */}
      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start lg:gap-6">
        <div className="flex flex-col gap-4">
          <PlaceOffers />
          <h2 className="text-xl">{t("portal.home.children")}</h2>
          {families.isPending && <Skeleton label={t("common.loading")} />}
          {families.isError && (
            <div className="flex flex-col gap-3">
              <Banner tone="due">{errorMessage(families.error, t)}</Banner>
              <Button variant="outline" onClick={() => void families.refetch()}>
                {t("common.retry")}
              </Button>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {families.data?.map((family) => (
              <FamilyCards key={family.id} family={family} />
            ))}
          </div>
          <Link
            to="/add-school"
            className={buttonVariants({ variant: "outline", className: "lg:self-start" })}
          >
            <Icon name="plus" size={16} />
            {t("portal.home.addSchool")}
          </Link>
        </div>
        {desktop && <RecentAnnouncements />}
      </div>
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
    <Banner
      tone="warn"
      icon="calendar"
      action={
        <Link to="/calendar" className={buttonVariants({ variant: "outline", size: "sm" })}>
          {t("portal.home.summonsAction")}
        </Link>
      }
    >
      {t("portal.home.summons", { name: next.student_name })}
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
    <Link to={`/children/${child.id}`} className="block h-full text-inherit no-underline">
      <Card className="h-full transition-shadow hover:shadow-raised">
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <ChildAvatar name={child.full_name} photo={child.photo} className="size-14 text-lg" />
            <div className="min-w-0 flex-1">
              <b className="block">{child.full_name}</b>
              <span className="text-sm text-ink-3">
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
              <div key={line.currency} className="text-sm">
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
            <div className="flex justify-between gap-3 text-sm">
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

/** Ordinateur : dernières annonces des écoles reliées, à côté des enfants (maquette `accueil`). */
function RecentAnnouncements() {
  const { t, i18n } = useTranslation();
  const families = useFamilies();
  const announcements = useAnnouncements();
  const offered = families.data?.some(
    (family) => family.status === "active" && family.school_modules.includes("communication"),
  );
  if (!offered) return null;
  const items = announcements.data?.pages[0]?.results.slice(0, 4) ?? [];
  return (
    <aside className="flex flex-col gap-4">
      <h2 className="text-xl">{t("portal.home.recentAnnouncements")}</h2>
      <Card>
        <CardContent className="py-1">
          {announcements.isPending ? (
            <Skeleton label={t("common.loading")} />
          ) : items.length === 0 ? (
            <p className="py-3 text-ink-3">{t("portal.home.noAnnouncements")}</p>
          ) : (
            <ul className="divide-y divide-line-soft">
              {items.map((item) => (
                <li key={item.id}>
                  <Link
                    to="/announcements"
                    className="flex items-center justify-between gap-3 py-3 text-ink no-underline hover:text-lake"
                  >
                    <span className="min-w-0">
                      <b className="block truncate">{item.title}</b>
                      <span className="text-sm text-ink-3">
                        {item.school_name} ·{" "}
                        {formatDate(item.published_at, i18n.language, item.school_timezone)}
                      </span>
                    </span>
                    <Icon name="chevron" size={18} className="shrink-0 text-ink-3" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
        <CardFooter>
          <Link to="/announcements" className="font-semibold">
            {t("portal.home.allAnnouncements")}
          </Link>
        </CardFooter>
      </Card>
    </aside>
  );
}
