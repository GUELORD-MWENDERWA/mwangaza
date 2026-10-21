// Contrôles avant le calcul (EDT.1b, maquette `controles-emploi-du-temps`) : ce qui rendra
// l'horaire impossible (rouge) ou incomplet (orange), recalculé par le serveur à chaque ouverture.
// Chaque ligne dit quoi, combien, et mène à l'écran où corriger. Droit `timetable.manage`.
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Kpi,
  List,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link } from "react-router";

import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { type CheckIssue, ROOM_KINDS, type RoomKind, useTimetableChecks } from "./data";

type Filter = "all" | "errors";
const CHECKS = [1, 2, 3, 4, 5] as const;
const KIND_CODES = new Set(["room_kind_missing", "room_kind_overloaded"]);

/** Où corriger : la grille de cours de la classe, les disponibilités, ou les salles. */
function fixOf(issue: CheckIssue): { to: string; key: "class" | "teacher" | "room" } {
  if (issue.class_group) return { to: `/courses?class=${issue.class_group}`, key: "class" };
  if (issue.teacher) return { to: "/teaching-loads", key: "teacher" };
  return { to: "/rooms", key: "room" };
}

export function ChecksPage() {
  const { t, i18n } = useTranslation();
  const years = useYears();
  const checks = useTimetableChecks();
  const [filter, setFilter] = useState<Filter>("all");

  if (checks.isPending || years.isPending) return <Skeleton label={t("common.loading")} />;
  if (checks.isError) {
    return <LoadError error={checks.error} onRetry={() => void checks.refetch()} />;
  }
  const report = checks.data;
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const year = years.data?.find((item) => item.is_current);
  const shown = report.issues.filter((issue) => filter === "all" || issue.level === "error");
  const byCheck = (check: number) => report.issues.filter((issue) => issue.check === check);

  const subject = (issue: CheckIssue) =>
    KIND_CODES.has(issue.code) && ROOM_KINDS.includes(issue.subject as RoomKind)
      ? t("timetable.checks.kindSubject", {
          kind: t(`timetable.kinds.${issue.subject as RoomKind}`),
        })
      : issue.subject;
  const message = (issue: CheckIssue) => {
    const values = issue.values as Record<string, number | string>;
    const extra =
      issue.code === "class_overloaded"
        ? { over: Number(values.hours) - Number(values.capacity) }
        : {};
    const text = t(`timetable.checks.codes.${issue.code as "no_hours"}`, {
      ...values,
      ...extra,
      defaultValue: issue.code,
    });
    const more = Number(values.more ?? 0);
    return more > 0
      ? `${text.replace(/\.$/, "")}${t("timetable.checks.more", { count: more })}`
      : text;
  };

  return (
    <>
      <PageHeader
        title={t("timetable.checks.title")}
        subtitle={t("timetable.checks.subtitle", { year: year?.name ?? "—" })}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/time-grid">{t("shell.menu.timeGrid")}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/rooms">{t("shell.menu.rooms")}</Link>
            </Button>
          </>
        }
      />
      <div className="mb-4 grid grid-cols-1 gap-4 min-[600px]:grid-cols-3">
        <Kpi
          label={t("timetable.checks.errors")}
          value={number(report.errors)}
          tone={report.errors ? "due" : "ok"}
          icon="alert"
          chip={report.errors ? "due" : "ok"}
          sub={t("timetable.checks.errorsHelp")}
        />
        <Kpi
          label={t("timetable.checks.warnings")}
          value={number(report.warnings)}
          tone={report.warnings ? "warn" : "ok"}
          icon="info"
          chip={report.warnings ? "warn" : "ok"}
          sub={t("timetable.checks.warningsHelp")}
        />
        <Kpi
          label={t("timetable.checks.checked")}
          value={`${number(report.classes)} · ${number(report.teachers)} · ${number(report.rooms)}`}
          icon="check"
          chip="ok"
          sub={t("timetable.checks.checkedHelp")}
        />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.9fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader className="flex-wrap">
            <CardTitle>{t("timetable.checks.listTitle")}</CardTitle>
            {report.issues.length > 0 && (
              <Segmented<Filter>
                label={t("timetable.checks.filter")}
                value={filter}
                onValueChange={setFilter}
                options={[
                  {
                    value: "all",
                    label: t("timetable.checks.all", { number: report.issues.length }),
                  },
                  {
                    value: "errors",
                    label: t("timetable.checks.onlyErrors", { number: report.errors }),
                  },
                ]}
                className="max-[600px]:w-full"
              />
            )}
          </CardHeader>
          <CardContent>
            {report.issues.length === 0 ? (
              <Banner tone="ok">{t("timetable.checks.ready")}</Banner>
            ) : (
              <ul className="flex flex-col">
                {shown.map((issue, index) => {
                  const fix = fixOf(issue);
                  return (
                    <li
                      key={`${issue.code}-${issue.subject}-${index}`}
                      className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-line-soft py-3 last:border-b-0"
                    >
                      <div className="flex min-w-0 flex-1 basis-[260px] flex-col gap-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <StatusPill tone={issue.level === "error" ? "due" : "warn"}>
                            {t(`timetable.checks.level.${issue.level}`)}
                          </StatusPill>
                          <b>{subject(issue)}</b>
                        </span>
                        <span className="text-sm text-ink-2">{message(issue)}</span>
                      </div>
                      <Button asChild variant="outline" size="sm">
                        <Link to={fix.to}>{t(`timetable.checks.fix.${fix.key}`)}</Link>
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("timetable.checks.whatTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <List className="text-sm">
              {CHECKS.map((check) => {
                const found = byCheck(check);
                const errors = found.some((issue) => issue.level === "error");
                return (
                  <div key={check}>
                    <span>{t(`timetable.checks.what.c${check}`)}</span>
                    <StatusPill tone={found.length === 0 ? "ok" : errors ? "due" : "warn"}>
                      {number(found.length)}
                    </StatusPill>
                  </div>
                );
              })}
            </List>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
