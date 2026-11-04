// Affaires de la plateforme (CON.1, maquette `console/affaires`) : écoles par état, élèves
// facturés, facturé / encaissé / dû par devise, contrats à renouveler, prospects. Un seul appel ;
// le serveur ne renvoie que les sections permises par les droits de l'équipier (une section absente
// n'est pas affichée) et garde le résultat 5 minutes.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  Kpi,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  buttonVariants,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { RIGHTS, useCan } from "../../lib/rights";

type Business = Schemas["ConsoleBusiness"];

const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
const EXPORTS = [
  { kind: "schools", right: RIGHTS.schoolsView },
  { kind: "invoices", right: RIGHTS.billingManage },
  { kind: "payments", right: RIGHTS.billingManage },
] as const;

export function BusinessPage() {
  const { t, i18n } = useTranslation();
  const can = useCan();
  const business = useQuery({
    queryKey: keys.business,
    queryFn: () => call(api.GET("/api/console/business/")),
    refetchInterval: 5 * 60_000,
  });

  if (business.isPending) return <Skeleton label={t("common.loading")} />;
  if (business.isError) {
    return (
      <>
        <Banner tone="due">{errorMessage(business.error, t)}</Banner>
        <Button variant="outline" className="w-fit" onClick={() => void business.refetch()}>
          {t("common.retry")}
        </Button>
      </>
    );
  }
  const data: Business = business.data;
  const { schools, renewals, money: rows } = data;

  return (
    <>
      <PageHeader
        title={t("console.business.title")}
        subtitle={t("console.business.subtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            {EXPORTS.filter((item) => can(item.right)).map((item) => (
              <a
                key={item.kind}
                href={`/api/console/business/export/${item.kind}/`}
                download
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                {t(`console.business.export.${item.kind}`)}
              </a>
            ))}
          </div>
        }
      />
      <div className="grid grid-cols-2 gap-3.5 min-[820px]:grid-cols-4">
        {schools && (
          <Kpi
            label={t("console.business.paying")}
            value={schools.active + schools.readonly}
            sub={[
              t("console.business.activeSub", { count: schools.active }),
              schools.trial > 0 && t("console.business.trialSub", { count: schools.trial }),
              schools.readonly > 0 &&
                t("console.business.readonlySub", { count: schools.readonly }),
              schools.suspended > 0 &&
                t("console.business.suspendedSub", { count: schools.suspended }),
            ].filter((line): line is string => Boolean(line))}
          />
        )}
        {data.billed_students !== null && (
          <Kpi
            label={t("console.business.students")}
            value={data.billed_students.toLocaleString(i18n.language)}
            sub={t("console.business.studentsSub")}
          />
        )}
        {data.prospects_open !== null && (
          <Kpi
            label={t("console.business.prospects")}
            value={data.prospects_open}
            sub={
              <Link to="/demo-requests" className="text-brand underline">
                {t("console.business.prospectsLink")}
              </Link>
            }
          />
        )}
        {renewals && (
          <Kpi
            label={t("console.business.renewals")}
            value={renewals.count}
            sub={
              data.trials_ending
                ? t("console.business.trialsEnding", { count: data.trials_ending })
                : undefined
            }
          />
        )}
      </div>
      <div className="grid gap-4 min-[820px]:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {rows && (
          <Card>
            <CardHeader>
              <CardTitle>{t("console.business.monthTitle")}</CardTitle>
            </CardHeader>
            {rows.length === 0 ? (
              <p className="px-4 py-5 text-ink-3">{t("console.business.noMoney")}</p>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <th>{t("console.business.currency")}</th>
                    <th className="text-right">{t("console.business.invoiced")}</th>
                    <th className="text-right">{t("console.business.collected")}</th>
                    <th className="text-right">{t("console.business.outstanding")}</th>
                    <th className="text-right">{t("console.business.overdue")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.currency}>
                      <td>
                        <b>{row.currency}</b>
                      </td>
                      <td className="text-right whitespace-nowrap tabular-nums">
                        {money(row.invoiced, row.currency)}
                      </td>
                      <td className="text-right whitespace-nowrap tabular-nums">
                        {money(row.collected, row.currency)}
                      </td>
                      <td className="text-right whitespace-nowrap tabular-nums">
                        {money(row.outstanding, row.currency)}
                      </td>
                      <td className="text-right whitespace-nowrap tabular-nums">
                        {row.overdue > 0 ? (
                          <StatusPill tone="due">{money(row.overdue, row.currency)}</StatusPill>
                        ) : (
                          money(0, row.currency)
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            <p className="px-4 py-3 text-sm text-ink-3">{t("console.business.neverAdded")}</p>
          </Card>
        )}
        {renewals && (
          <Card>
            <CardHeader>
              <CardTitle>{t("console.business.renewalsTitle")}</CardTitle>
            </CardHeader>
            {renewals.items.length === 0 ? (
              <p className="px-4 py-5 text-ink-3">{t("console.business.noRenewal")}</p>
            ) : (
              <ul className="m-0 list-none p-0">
                {renewals.items.map((item) => (
                  <li
                    key={item.school_id}
                    className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-line px-4 py-2.5 first:border-t-0"
                  >
                    <Link to={`/schools/${item.school_id}`} className="min-w-0 break-words">
                      <b>{item.name}</b> <span className="text-sm text-ink-3">{item.code}</span>
                    </Link>
                    <span className="text-sm text-ink-3">
                      {formatDay(item.end_date, i18n.language)}
                      {item.auto_renew ? ` · ${t("console.business.auto")}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>
    </>
  );
}
