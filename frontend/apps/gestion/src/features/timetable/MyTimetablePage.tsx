import { errorMessage, formatDateTime, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  isoWeekday,
  PageHeader,
  Segmented,
  Skeleton,
  StateCard,
  StatusPill,
  toSchedule,
  WeekSchedule,
} from "@mwangaza/ui";
import { useState } from "react";

import { useSchool } from "../../lib/queries";
import { dayKey } from "./AvailabilityDialog";
import { useMyTimetable } from "./mine";

const WEEK = [1, 2, 3, 4, 5, 6, 7];

/** « Mon horaire » (EDT.4b, maquette `mon-horaire`) : ses séances dans l'horaire publié et,
 *  pour un titulaire, celles de sa classe ; un jour à la fois au téléphone, la semaine en
 *  colonnes sur un grand écran ; sans réseau, la copie gardée sur l'appareil, datée. */
export function MyTimetablePage() {
  const { t, i18n } = useTranslation();
  const timeZone = useSchool().data?.timezone ?? "Africa/Lubumbashi";
  const query = useMyTimetable();
  const [view, setView] = useState<"mine" | "homeroom">("mine");
  const data = query.data?.value;
  const version = data?.timetable;
  const homeroom = data?.homeroom;
  const showing = view === "homeroom" && homeroom ? homeroom.lessons : (data?.lessons ?? []);
  const dayNames = {
    long: WEEK.map((day) => t(`timetable.days.${dayKey(day)}`)),
    short: WEEK.map((day) => t(`timetable.daysShort.${dayKey(day)}`)),
  };
  const hours = (first: number, last: number) =>
    first === last
      ? t("timetable.mine.hour", { first })
      : t("timetable.mine.hours", { first, last });
  const lessons = toSchedule(
    showing,
    (lesson) =>
      view === "homeroom" ? [lesson.teacher, lesson.room] : [lesson.class_group, lesson.room],
    hours,
  );
  const weekHours = (data?.lessons ?? []).reduce((total, lesson) => total + lesson.length, 0);
  const classCount = new Set((data?.lessons ?? []).map((lesson) => lesson.class_group)).size;

  const subtitle =
    version?.valid_from &&
    t(
      version.valid_from <= new Date().toISOString().slice(0, 10)
        ? "timetable.mine.since"
        : "timetable.mine.from",
      { date: formatDay(version.valid_from, i18n.language) },
    );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("timetable.mine.title")}
        subtitle={subtitle}
        actions={
          homeroom && (
            <Segmented
              value={view}
              onValueChange={setView}
              label={t("timetable.mine.view")}
              className="w-full sm:w-auto"
              options={[
                { value: "mine", label: t("timetable.mine.mineTab") },
                { value: "homeroom", label: t("timetable.mine.homeroomTab") },
              ]}
            />
          )
        }
      />
      {query.isPending && <Skeleton label={t("common.loading")} />}
      {query.isError && (
        <div className="flex flex-col gap-3">
          <Banner tone="due">{errorMessage(query.error, t)}</Banner>
          <Button variant="outline" className="self-start" onClick={() => void query.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {query.data?.keptAt && (
        <Banner tone="warn" icon="wifioff">
          {t("timetable.mine.offline", {
            date: formatDateTime(new Date(query.data.keptAt), i18n.language, timeZone),
          })}
        </Banner>
      )}
      {data && (!version || showing.length === 0) && (
        <StateCard icon="calendar" tone="gray" title={t("timetable.mine.emptyTitle")}>
          {t(version ? "timetable.mine.emptyLessons" : "timetable.mine.emptyText")}
        </StateCard>
      )}
      {data && version && showing.length > 0 && (
        <>
          <div className="flex flex-wrap gap-2">
            {view === "homeroom" && homeroom ? (
              <StatusPill tone="info">{homeroom.class_group}</StatusPill>
            ) : (
              <>
                <StatusPill tone="info">
                  {t("timetable.mine.weekHours", { count: weekHours })}
                </StatusPill>
                <StatusPill tone="gray">
                  {t("timetable.mine.classes", { count: classCount })}
                </StatusPill>
              </>
            )}
          </div>
          <Card>
            <CardContent className="pt-5">
              <WeekSchedule
                key={view}
                columns
                dayNames={dayNames}
                lessons={lessons}
                label={t("timetable.mine.day")}
                today={isoWeekday()}
                todayLabel={t("timetable.mine.today")}
                emptyDay={t("timetable.mine.noLessons")}
              />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
