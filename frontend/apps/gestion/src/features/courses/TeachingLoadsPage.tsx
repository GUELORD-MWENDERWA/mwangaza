// Charges des enseignants (8.1, maquette `charges-enseignants`) : heures par semaine des cours de
// l'année en cours attribués à chaque membre du personnel, et cours sans enseignant. Lecture
// seule : l'attribution se fait dans « Cours et maxima ». Droit `courses.configure`. Avec
// `timetable.manage` (EDT.1b) : charge au plus et absences de chacun, réglées dans une fenêtre.
import { useTranslation } from "@mwangaza/i18n";
import {
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  List,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  cn,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link } from "react-router";

import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { describe } from "../timetable/availability";
import { AvailabilityDialog, dayKey } from "../timetable/AvailabilityDialog";
import { useGrids, useTeacherProfiles, useTimetableRules } from "../timetable/data";
import { useTeachingLoads } from "./data";

// Le reste se voit classe par classe dans « Cours et maxima ».
const UNASSIGNED_SHOWN = 8;

export function TeachingLoadsPage() {
  const { t, i18n } = useTranslation();
  const years = useYears();
  const loads = useTeachingLoads();
  const canPlace = can(useCurrentMe(), ["timetable.manage"]);
  const profiles = useTeacherProfiles(canPlace);
  const grids = useGrids(canPlace);
  const rules = useTimetableRules(canPlace);
  const [editing, setEditing] = useState<{ id: string; name: string; hours: string } | null>(null);

  if (loads.isPending || years.isPending) return <Skeleton label={t("common.loading")} />;
  if (loads.isError) return <LoadError error={loads.error} onRetry={() => void loads.refetch()} />;

  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const hours = (count: number) => t("courses.hoursValue", { count, value: number(count) });
  const year = years.data?.find((item) => item.is_current);
  const teaching = loads.data.loads.filter((load) => load.courses.length > 0);
  const {
    unassigned,
    unassigned_count: unassignedCount,
    unassigned_hours: unassignedHours,
  } = loads.data;
  const assignedHours = teaching.reduce((sum, load) => sum + load.hours, 0);
  const profileOf = (id: string) => profiles.data?.find((profile) => profile.teacher === id);
  const dayName = (weekday: number) => t(`timetable.days.${dayKey(weekday)}`).toLowerCase();

  return (
    <>
      <PageHeader
        title={t("courses.loads.title")}
        subtitle={t("courses.loads.subtitle", { year: year?.name ?? "—" })}
        actions={
          <Button asChild variant="outline">
            <Link to="/courses">{t("courses.title")}</Link>
          </Button>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <Card>
          <Table>
            <thead>
              <tr>
                <th>{t("courses.loads.teacher")}</th>
                <th>{t("courses.loads.courses")}</th>
                <th className="text-right max-[600px]:hidden">{t("courses.loads.count")}</th>
                <th className="text-right">{t("courses.loads.hours")}</th>
                {canPlace && <th>{t("timetable.availability.column")}</th>}
              </tr>
            </thead>
            <tbody>
              {teaching.length === 0 && (
                <tr>
                  <td colSpan={canPlace ? 5 : 4} className="text-center text-ink-2">
                    {t("courses.loads.empty")}
                  </td>
                </tr>
              )}
              {teaching.map((load) => {
                const profile = profileOf(load.teacher.id);
                const max = profile?.max_week_hours ?? null;
                const absences = describe(profile?.unavailable ?? [], dayName);
                return (
                  <tr key={load.teacher.id}>
                    <td className="font-bold" data-wrap>
                      {fullName(load.teacher)}
                    </td>
                    <td data-wrap>
                      <ul className="flex flex-col gap-0.5 text-sm">
                        {load.courses.map((course) => (
                          <li key={course.id}>
                            <span className="text-ink-2">{course.class_name}</span> · {course.name}
                            {course.weekly_hours ? (
                              <span className="whitespace-nowrap">
                                {" "}
                                · {hours(course.weekly_hours)}
                              </span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </td>
                    <td className="text-right tabular-nums max-[600px]:hidden">
                      {load.courses.length}
                    </td>
                    <td className="text-right whitespace-nowrap tabular-nums">
                      <b className={cn(max !== null && load.hours > max && "text-due")}>
                        {hours(load.hours)}
                      </b>
                      {max !== null && (
                        <div className="text-xs text-ink-2">
                          {t("timetable.availability.atMost", { count: max })}
                        </div>
                      )}
                    </td>
                    {canPlace && (
                      <td data-wrap>
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <span className={cn(absences.length === 0 && "text-ink-2")}>
                            {absences.length > 0
                              ? t("timetable.availability.summary", { list: absences.join(", ") })
                              : t("timetable.availability.always")}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={t("timetable.availability.setFor", {
                              name: fullName(load.teacher),
                            })}
                            onClick={() =>
                              setEditing({
                                id: load.teacher.id,
                                name: fullName(load.teacher),
                                hours: hours(load.hours),
                              })
                            }
                          >
                            {t("timetable.availability.set")}
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
            {teaching.length > 0 && (
              <tfoot>
                <tr className="font-bold [&_td]:bg-table-head">
                  <td colSpan={2}>{t("courses.loads.total")}</td>
                  <td className="text-right tabular-nums max-[600px]:hidden">
                    {number(teaching.reduce((sum, load) => sum + load.courses.length, 0))}
                  </td>
                  <td className="text-right whitespace-nowrap tabular-nums">
                    {hours(assignedHours)}
                  </td>
                  {canPlace && <td />}
                </tr>
              </tfoot>
            )}
          </Table>
          <CardFooter>
            <p className="text-sm text-ink-2">{t("courses.loads.help")}</p>
          </CardFooter>
        </Card>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("courses.control.title")}</CardTitle>
            </CardHeader>
            <CardContent>
              <List className="text-sm">
                <div>
                  <span>{t("courses.loads.teachers")}</span>
                  <b>{number(teaching.length)}</b>
                </div>
                <div>
                  <span>{t("courses.loads.assignedHours")}</span>
                  <b className="tabular-nums">{hours(assignedHours)}</b>
                </div>
                <div>
                  <span>{t("courses.loads.unassigned")}</span>
                  <b className={cn("tabular-nums", unassignedCount > 0 && "text-warn")}>
                    {number(unassignedCount)} · {hours(unassignedHours)}
                  </b>
                </div>
              </List>
            </CardContent>
          </Card>
          {unassignedCount > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("courses.loads.unassigned")}</CardTitle>
                <StatusPill tone="warn">{number(unassignedCount)}</StatusPill>
              </CardHeader>
              <CardContent>
                <List className="text-sm">
                  {unassigned.slice(0, UNASSIGNED_SHOWN).map((course) => (
                    <div key={course.id}>
                      <span>
                        {course.class_name} · <b>{course.name}</b>
                      </span>
                      <span className="whitespace-nowrap tabular-nums">
                        {course.weekly_hours ? hours(course.weekly_hours) : "—"}
                      </span>
                    </div>
                  ))}
                </List>
              </CardContent>
              {unassignedCount > UNASSIGNED_SHOWN && (
                <CardFooter>
                  <p className="text-sm text-ink-2">
                    {t("courses.loads.more", { count: unassignedCount - UNASSIGNED_SHOWN })}
                  </p>
                </CardFooter>
              )}
            </Card>
          )}
        </div>
      </div>
      {editing && (
        <AvailabilityDialog
          teacher={editing}
          hours={editing.hours}
          profile={profileOf(editing.id)}
          grids={grids.data ?? []}
          schoolMaxDay={rules.data?.teacher_max_day_hours ?? 6}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}
