import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  isoWeekday,
  toSchedule,
  WeekSchedule,
} from "@mwangaza/ui";

import { useChildTimetable } from "../../lib/families";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

/** Horaire de la classe (EDT.4b, maquette `enfant-horaire`) : la version publiée, un jour à la
 *  fois (aujourd'hui d'abord) ; chaque heure dit le cours, l'enseignant et la salle. Rien tant que
 *  l'école n'a pas le module ; « pas encore publié » sinon. */
export function ChildTimetable({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const query = useChildTimetable(id);
  const data = query.data;
  if (!data) return null;
  const version = data.timetable;
  const since = version?.valid_from;
  return (
    <Card className="mt-4">
      <CardHeader className="flex flex-row flex-wrap items-baseline justify-between gap-2">
        <CardTitle>{t("portal.child.timetableTitle")}</CardTitle>
        {since && (
          <span className="text-sm text-ink-3">
            {t(
              since <= new Date().toISOString().slice(0, 10)
                ? "portal.child.timetableSince"
                : "portal.child.timetableFrom",
              { date: formatDay(since, i18n.language) },
            )}
          </span>
        )}
      </CardHeader>
      <CardContent>
        {version ? (
          <WeekSchedule
            dayNames={{
              long: DAYS.map((day) => t(`timetable.days.${day}`)),
              short: DAYS.map((day) => t(`timetable.daysShort.${day}`)),
            }}
            lessons={toSchedule(
              data.lessons,
              (lesson) => [lesson.teacher, lesson.room],
              (first, last) =>
                first === last
                  ? t("portal.child.timetableHour", { first })
                  : t("portal.child.timetableHours", { first, last }),
            )}
            label={t("portal.child.timetableDay")}
            today={isoWeekday()}
            todayLabel={t("portal.child.timetableToday")}
            emptyDay={t("portal.child.timetableNoLessons")}
          />
        ) : (
          <p className="text-sm text-ink-3">{t("portal.child.timetableEmpty")}</p>
        )}
      </CardContent>
    </Card>
  );
}
