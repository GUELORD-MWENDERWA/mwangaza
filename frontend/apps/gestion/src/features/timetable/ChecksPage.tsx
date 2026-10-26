// Règles et contrôles (EDT.1b et EDT.1c, maquettes `controles-emploi-du-temps` et
// `regle-emploi-du-temps`) : ce qui rendra l'horaire impossible (rouge) ou incomplet (orange),
// recalculé par le serveur à chaque ouverture, et les règles de l'horaire. Chaque ligne dit quoi,
// combien, et mène à l'écran où corriger (ou à la règle en cause). Droit `timetable.manage`.
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
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import {
  type CheckIssue,
  ROOM_KINDS,
  type RoomKind,
  type Rule,
  type RuleKind,
  useGrids,
  useRooms,
  useRuleChoices,
  useRules,
  useTimetableChecks,
  useTimetableRules,
} from "./data";
import { AssistantDialog } from "./AssistantDialog";
import { ReviewDialog } from "./ReviewDialog";
import { RuleDialog } from "./RuleDialog";
import { RulesCard } from "./RulesCard";
import { dayName, hoursText, lookupOf } from "./rules";

type Filter = "all" | "errors";
const CHECKS = [1, 2, 3, 4, 5, 6, 7] as const;
const KIND_CODES = new Set(["room_kind_missing", "room_kind_overloaded"]);

/** Où corriger : la règle en cause, la grille de cours de la classe, les disponibilités, ou les
 *  salles. */
function fixOf(issue: CheckIssue): { to: string; key: "class" | "teacher" | "room" | "rule" } {
  if (issue.rule) return { to: "", key: "rule" };
  if (issue.class_group) return { to: `/courses?class=${issue.class_group}`, key: "class" };
  if (issue.teacher) return { to: "/teaching-loads", key: "teacher" };
  return { to: "/rooms", key: "room" };
}

export function ChecksPage() {
  const { t, i18n } = useTranslation();
  const years = useYears();
  const checks = useTimetableChecks();
  const rules = useRules();
  const choices = useRuleChoices();
  const rooms = useRooms();
  const grids = useGrids();
  const general = useTimetableRules();
  const [filter, setFilter] = useState<Filter>("all");
  const [editing, setEditing] = useState<Rule | "new" | null>(null);
  const [assisting, setAssisting] = useState(false);
  const [advising, setAdvising] = useState(false);
  const me = useCurrentMe();
  const hasAssistant = me.school?.modules.includes("ai") && can(me, ["ai.use"]);
  // `?rule=` : une règle qui bloque un calcul (EDT.3b) ouvre sa fenêtre.
  const [params, setParams] = useSearchParams();
  const asked = params.get("rule");
  const open = editing ?? (asked ? rules.data?.find((rule) => rule.id === asked) : undefined);
  const close = () => {
    setEditing(null);
    if (asked)
      setParams(
        (current) => {
          current.delete("rule");
          return current;
        },
        { replace: true },
      );
  };
  const lookup = useMemo(() => lookupOf(choices.data, rooms.data), [choices.data, rooms.data]);
  const lessons = (grids.data ?? []).flatMap((grid) =>
    grid.slots.filter((slot) => slot.kind === "lesson"),
  );
  const days = [...new Set(lessons.map((slot) => slot.weekday))].sort((a, b) => a - b);
  const maxLessons = Math.max(0, ...lessons.map((slot) => slot.index ?? 0)) || 12;

  if (checks.isPending || years.isPending || rules.isPending || choices.isPending) {
    return <Skeleton label={t("common.loading")} />;
  }
  const failed = [checks, rules, choices].find((query) => query.isError);
  if (failed) {
    return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;
  }
  const report = checks.data;
  if (!report || !rules.data || !choices.data) return null;
  const ruleOf = (id: string | null | undefined) => rules.data.find((rule) => rule.id === id);
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const year = years.data?.find((item) => item.is_current);
  const shown = report.issues.filter((issue) => filter === "all" || issue.level === "error");
  const byCheck = (check: number) => report.issues.filter((issue) => issue.check === check);

  const subject = (issue: CheckIssue) => {
    if (issue.code === "rule_without_object") {
      return t(`timetable.constraints.kinds.${issue.subject as RuleKind}`);
    }
    return KIND_CODES.has(issue.code) && ROOM_KINDS.includes(issue.subject as RoomKind)
      ? t("timetable.checks.kindSubject", {
          kind: t(`timetable.kinds.${issue.subject as RoomKind}`),
        })
      : issue.subject;
  };
  const message = (issue: CheckIssue) => {
    const values = issue.values as Record<string, number | string>;
    // Contrôles 6 et 7 : jour, heures et type de règle en mots.
    const extra = {
      ...(issue.code === "class_overloaded"
        ? { over: Number(values.hours) - Number(values.capacity) }
        : {}),
      ...(values.day ? { day: dayName(Number(values.day), i18n.language) } : {}),
      ...(values.first ? { hours: hoursText(Number(values.first), Number(values.last), t) } : {}),
      ...(values.other
        ? { other: t(`timetable.constraints.kinds.${values.other as RuleKind}`) }
        : {}),
    };
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
            <Button asChild>
              <Link to="/timetable/calculate">{t("timetable.calculation.open")}</Link>
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
          value={`${number(report.classes)} · ${number(report.teachers)} · ${number(report.rooms)} · ${number(report.rules)}`}
          icon="check"
          chip="ok"
          sub={t("timetable.checks.checkedHelp")}
        />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.9fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader className="flex-wrap">
            <CardTitle>{t("timetable.checks.listTitle")}</CardTitle>
            {hasAssistant && report.issues.length > 0 && (
              <Button variant="outline" size="sm" onClick={() => setAdvising(true)}>
                {t("timetable.review.open")}
              </Button>
            )}
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
                      {fix.key === "rule" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditing(ruleOf(issue.rule) ?? null)}
                        >
                          {t("timetable.checks.fix.rule")}
                        </Button>
                      ) : (
                        <Button asChild variant="outline" size="sm">
                          <Link to={fix.to}>{t(`timetable.checks.fix.${fix.key}`)}</Link>
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
        <div className="flex min-w-0 flex-col gap-4">
          <RulesCard
            rules={rules.data}
            lookup={lookup}
            general={general.data}
            onAdd={() => setEditing("new")}
            onAssist={hasAssistant ? () => setAssisting(true) : undefined}
            onEdit={setEditing}
          />
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
      </div>
      {advising && <ReviewDialog onClose={() => setAdvising(false)} />}
      {assisting && <AssistantDialog lookup={lookup} onClose={() => setAssisting(false)} />}
      {open && (
        <RuleDialog
          rule={open === "new" ? null : open}
          choices={choices.data}
          rooms={rooms.data ?? []}
          days={days.length ? days : [1, 2, 3, 4, 5, 6]}
          maxLessons={maxLessons}
          onClose={close}
        />
      )}
    </>
  );
}
