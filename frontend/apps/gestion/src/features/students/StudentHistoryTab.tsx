// Onglet Historique de la fiche élève (M9, I1) : frise lue dans le journal de l'école (l'élève,
// ses inscriptions, sa famille), la plus récente en haut ; les filtres ne font que masquer.
// Parcours scolaire : les inscriptions de cette école seulement (Q10). Paiements : avec la caisse
// (3.x) ; notes et délibérations : V1.2.
import { formatDate, formatTime, useTranslation } from "@mwangaza/i18n";
import {
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link } from "react-router";

import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { fieldLabel, renderValue } from "../audit/values";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { type HistoryEntry, type Student, useStudentHistory } from "./data";

type Filter = "all" | "schooling" | "changes";
const SCHOOLING = new Set([
  "students.enrolled",
  "students.enrollment_updated",
  "students.student_imported",
]);
const PAGE_SIZE = 50;

function shown(entry: HistoryEntry, filter: Filter): boolean {
  if (filter === "all") return true;
  return SCHOOLING.has(entry.action) === (filter === "schooling");
}

export function StudentHistoryTab({ student }: { student: Student }) {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const history = useStudentHistory(student.id, page);
  const enrollments = [...student.enrollments].sort((a, b) =>
    b.academic_year_name.localeCompare(a.academic_year_name),
  );
  return (
    <div className="grid items-start gap-4 min-[1100px]:grid-cols-[1.6fr_1fr]">
      <Card>
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle>{t("students.history.title")}</CardTitle>
          <Segmented
            label={t("students.history.filter")}
            value={filter}
            onValueChange={setFilter}
            options={(["all", "schooling", "changes"] as const).map((value) => ({
              value,
              label: t(`students.history.filters.${value}`),
            }))}
          />
        </CardHeader>
        {history.error ? (
          <LoadError error={history.error} onRetry={() => void history.refetch()} />
        ) : !history.data ? (
          <Skeleton label={t("common.loading")} />
        ) : (
          <ol className="flex flex-col px-[18px]">
            {history.data.results
              .filter((entry) => shown(entry, filter))
              .map((entry) => (
                <Event key={entry.id} entry={entry} />
              ))}
            {history.data.count === 0 && (
              <li className="py-4 text-sm text-ink-3">{t("students.history.empty")}</li>
            )}
          </ol>
        )}
        {history.data && history.data.count > PAGE_SIZE && (
          <Pagination
            summary={t("students.list.range", {
              from: (page - 1) * PAGE_SIZE + 1,
              to: Math.min(page * PAGE_SIZE, history.data.count),
              count: history.data.count,
            })}
            page={page}
            hasPrevious={Boolean(history.data.previous)}
            hasNext={Boolean(history.data.next)}
            onPage={setPage}
          />
        )}
        <CardFooter>
          <span className="text-sm text-ink-3">
            {t("students.history.count", { count: history.data?.count ?? 0 })}
          </span>
          {can(me, ["audit.view"]) && (
            <Button asChild size="sm" variant="outline">
              <Link to="/audit">{t("students.history.openAudit")}</Link>
            </Button>
          )}
        </CardFooter>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("students.history.path")}</CardTitle>
        </CardHeader>
        <Table>
          <thead>
            <tr>
              <th>{t("students.history.columns.year")}</th>
              <th>{t("students.history.columns.class")}</th>
              <th>{t("students.history.columns.status")}</th>
            </tr>
          </thead>
          <tbody>
            {enrollments.map((enrollment) => (
              <tr key={enrollment.id}>
                <td className="font-bold">{enrollment.academic_year_name}</td>
                <td>{enrollment.class_group_name}</td>
                <td>
                  <StatusPill tone={enrollment.status === "active" ? "info" : "warn"}>
                    {t(`students.enrollmentStatus.${enrollment.status}`)}
                  </StatusPill>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        {enrollments.length === 0 && (
          <p className="px-[18px] py-3 text-sm text-ink-3">{t("students.history.noPath")}</p>
        )}
        <CardFooter className="text-sm text-ink-3">{t("students.history.later")}</CardFooter>
      </Card>
    </div>
  );
}

/** Une ligne de la frise : l'action, ce qui a changé (avant → après), qui et quand. */
function Event({ entry }: { entry: HistoryEntry }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const before = (entry.before ?? {}) as Record<string, unknown>;
  const after = (entry.after ?? {}) as Record<string, unknown>;
  const value = (field: string, data: Record<string, unknown>) =>
    renderValue(field, data[field], t, i18n.language, school.timezone);
  const changed = entry.action.endsWith("_updated") ? Object.keys(after) : [];
  const who = entry.by_support
    ? t("audit.support")
    : entry.actor
      ? fullName(entry.actor)
      : t("audit.system");
  return (
    <li className="flex flex-wrap items-start justify-between gap-2 border-b border-line-soft py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <b>{t(`audit.actions.${entry.action}` as "audit.actions.students.enrolled")}</b>
        {entry.action === "students.enrolled" && (
          <span>
            {" "}
            · {String(after.class ?? "")} · {String(after.school_year ?? "")}
          </span>
        )}
        {changed.map((field) => (
          <div key={field} className="text-sm">
            {fieldLabel(field, t)} : <span className="text-ink-3">{value(field, before)}</span> →{" "}
            <b>{value(field, after)}</b>
          </div>
        ))}
        <div className="text-sm text-ink-3">{t("students.history.by", { name: who })}</div>
      </div>
      <span className="text-xs whitespace-nowrap text-ink-3">
        {formatDate(entry.created_at, i18n.language, school.timezone)} ·{" "}
        {formatTime(entry.created_at, i18n.language, school.timezone)}
      </span>
    </li>
  );
}
