// Suivi des présences (lot 10, 6.5 · maquette `presences-suivi.html`) : le jour à l'entrée (présents,
// retards, absents, personnel), par classe, absents à suivre, journal des corrections et
// justifications des parents. Les absents sont calculés par le serveur, jamais stockés.
import { formatDay, formatTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardHeader,
  CardTitle,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@mwangaza/ui";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { useCurrentSchool } from "../../lib/school";
import { useMe } from "../../lib/queries";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { AbsentsTab, CorrectionsTab, JustificationsTab } from "./FollowTabs";
import { CorrectDialog, type Target } from "./CorrectDialog";
import { exportUrl, shiftDay, today, useDay, useStaffDay } from "./follow";

const TONES = { present: "ok", late: "warn", absent: "due" } as const;

export function FollowPage() {
  const { t, i18n } = useTranslation();
  const [date, setDate] = useState(today);
  const [tab, setTab] = useState("classes");
  const [target, setTarget] = useState<Target | null>(null);
  const school = useCurrentSchool();
  const day = useDay(date);
  const me = useMe();
  const mayCorrect = me.data ? can(me.data, ["attendance.correct"]) : false;
  const data = day.data;
  const isToday = date === today();

  if (day.isError && !data) {
    return <LoadError error={day.error} onRetry={() => void day.refetch()} />;
  }
  return (
    <>
      <PageHeader
        title={t("follow.title")}
        subtitle={t("follow.subtitle", { date: formatDay(date, i18n.language) })}
        actions={
          <>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                aria-label={t("follow.previous")}
                onClick={() => setDate(shiftDay(date, -1))}
              >
                <span aria-hidden="true">‹</span>
              </Button>
              <Input
                type="date"
                aria-label={t("follow.date")}
                value={date}
                max={today()}
                onChange={(event) => event.target.value && setDate(event.target.value)}
              />
              <Button
                variant="outline"
                size="sm"
                aria-label={t("follow.next")}
                disabled={isToday}
                onClick={() => setDate(shiftDay(date, 1))}
              >
                <span aria-hidden="true">›</span>
              </Button>
            </div>
            <a
              href={exportUrl(date, date, "")}
              download
              className={buttonVariants({ variant: "outline" })}
            >
              <Icon name="download" size={16} />
              {t("follow.export")}
            </a>
          </>
        }
      />
      {data && !data.school_day && (
        <Banner tone="info" className="mt-4">
          {t(data.holiday ? "follow.holiday" : "follow.noClass")}
        </Banner>
      )}
      <div className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(min(100%,180px),1fr))] gap-4">
        <Kpi
          label={t("follow.kpi.present")}
          tone="ok"
          value={data?.present ?? "–"}
          sub={data?.rate != null ? t("follow.kpi.rate", { rate: data.rate }) : undefined}
        />
        <Kpi
          label={t("follow.kpi.late")}
          tone="warn"
          value={data?.late ?? "–"}
          sub={data ? t("follow.kpi.lateAfter", { time: data.late_after }) : undefined}
        />
        <Kpi
          label={t("follow.kpi.absent")}
          tone="due"
          value={data?.absent ?? "–"}
          sub={data ? t("follow.kpi.justified", { count: data.justified }) : undefined}
        />
        <Kpi
          label={t("follow.kpi.staff")}
          value={data ? `${data.staff_present} / ${data.staff_total}` : "–"}
        />
      </div>
      {data && data.parents_notified_at && (
        <p className="mt-2 text-sm text-ink-3">
          {t("follow.parentsNotified", {
            time: formatTime(data.parents_notified_at, i18n.language, school.timezone),
          })}
        </p>
      )}
      <Tabs value={tab} onValueChange={setTab} className="mt-4">
        <TabsList>
          <TabsTrigger value="classes">{t("follow.tabs.classes")}</TabsTrigger>
          <TabsTrigger value="absents">{t("follow.tabs.absents")}</TabsTrigger>
          <TabsTrigger value="staff">{t("follow.tabs.staff")}</TabsTrigger>
          <TabsTrigger value="justifications">
            {t("follow.tabs.justifications")}
            {data && data.pending > 0 ? ` (${data.pending})` : ""}
          </TabsTrigger>
          <TabsTrigger value="corrections">{t("follow.tabs.corrections")}</TabsTrigger>
        </TabsList>
        <TabsContent value="classes">
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>{t("follow.tabs.classes")}</CardTitle>
            </CardHeader>
            {!data ? (
              <Skeleton label={t("common.loading")} />
            ) : data.classes.length === 0 ? (
              <p className="px-[18px] py-6 text-ink-3">{t("follow.noClasses")}</p>
            ) : (
              <Table stacked>
                <thead>
                  <tr>
                    <th>{t("follow.columns.class")}</th>
                    <th className="text-right">{t("follow.columns.enrolled")}</th>
                    <th className="text-right">{t("follow.columns.present")}</th>
                    <th className="text-right">{t("follow.columns.late")}</th>
                    <th className="text-right">{t("follow.columns.absent")}</th>
                    <th className="text-right">{t("follow.columns.justified")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.classes.map((group) => (
                    <tr key={group.id}>
                      <td>
                        <b>{group.name}</b>
                      </td>
                      <Num label={t("follow.columns.enrolled")} value={group.enrolled} />
                      <Num label={t("follow.columns.present")} value={group.present} />
                      <Num label={t("follow.columns.late")} value={group.late} />
                      <Num label={t("follow.columns.absent")} value={group.absent} />
                      <Num label={t("follow.columns.justified")} value={group.justified} />
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        </TabsContent>
        <TabsContent value="absents">
          <AbsentsTab
            date={date}
            alertAfter={data?.alert_after ?? 0}
            mayCorrect={mayCorrect}
            onCorrect={setTarget}
          />
        </TabsContent>
        <TabsContent value="staff">
          <StaffTab date={date} mayCorrect={mayCorrect} onCorrect={setTarget} />
        </TabsContent>
        <TabsContent value="justifications">
          <JustificationsTab mayCorrect={mayCorrect} />
        </TabsContent>
        <TabsContent value="corrections">
          <CorrectionsTab />
        </TabsContent>
      </Tabs>
      <CorrectDialog date={date} target={target} onClose={() => setTarget(null)} />
    </>
  );
}

function Num({ label, value }: { label: string; value: number }) {
  return (
    <td data-label={label} className="text-right tabular-nums">
      {value}
    </td>
  );
}

function StaffTab({
  date,
  mayCorrect,
  onCorrect,
}: {
  date: string;
  mayCorrect: boolean;
  onCorrect: (target: Target) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [page, setPage] = useState(1);
  const list = useStaffDay(date, page);
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * 50 + 1 : 0;
  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>{t("follow.tabs.staff")}</CardTitle>
      </CardHeader>
      {list.isError && <Banner tone="due">{errorMessage(list.error, t)}</Banner>}
      {list.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : rows.length === 0 ? (
        <p className="px-[18px] py-6 text-ink-3">{t("follow.noStaff")}</p>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("follow.columns.member")}</th>
              <th>{t("follow.columns.status")}</th>
              <th>{t("follow.columns.seenAt")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.member_id}>
                <td data-label={t("follow.columns.member")}>
                  <b>{row.name}</b>
                </td>
                <td data-label={t("follow.columns.status")}>
                  <StatusPill tone={TONES[row.status]}>
                    {t(`follow.status.${row.status}`)}
                  </StatusPill>
                </td>
                <td data-label={t("follow.columns.seenAt")} className="tabular-nums">
                  {row.seen_at ? formatTime(row.seen_at, i18n.language, school.timezone) : "—"}
                </td>
                <td>
                  {mayCorrect && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        onCorrect({
                          kind: "member",
                          id: row.member_id,
                          name: row.name,
                          status: row.status,
                        })
                      }
                    >
                      {t("follow.correct")}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Pagination
        summary={t("follow.range", { from, to: from + rows.length - (rows.length ? 1 : 0), count })}
        page={page}
        hasPrevious={Boolean(list.data?.previous)}
        hasNext={Boolean(list.data?.next)}
        onPage={setPage}
      />
    </Card>
  );
}
