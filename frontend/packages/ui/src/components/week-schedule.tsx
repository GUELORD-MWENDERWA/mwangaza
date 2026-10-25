import { useState } from "react";

import { cn } from "../lib/cn";
import { Segmented } from "./segmented";

export type ScheduleLesson = {
  key: string;
  /** 1 = lundi … 7 = dimanche. */
  weekday: number;
  /** « 07:30 – 09:10 », ou les numéros d'heure quand la grille ne donne plus l'horaire. */
  time: string;
  title: string;
  detail: string;
};

/** Noms des jours, du lundi au dimanche. */
export type DayNames = { long: string[]; short: string[] };

/** Séance de l'horaire publié telle que l'API la donne (`ScheduleLesson` du schéma). */
type PublishedLesson = {
  weekday: number;
  first: number;
  length: number;
  start: string | null;
  end: string | null;
  course: string;
};

/** Séances de l'API → lignes de la semaine : « 07:30 – 09:10 », ou les numéros d'heure quand la
 *  grille ne donne plus l'horaire ; `detail` dit le reste (classe, enseignant, salle). */
export function toSchedule<L extends PublishedLesson>(
  lessons: L[],
  detail: (lesson: L) => string[],
  hours: (first: number, last: number) => string,
): ScheduleLesson[] {
  return lessons.map((lesson, index) => ({
    key: `${lesson.weekday}-${lesson.first}-${index}`,
    weekday: lesson.weekday,
    time:
      lesson.start && lesson.end
        ? `${lesson.start} – ${lesson.end}`
        : hours(lesson.first, lesson.first + lesson.length - 1),
    title: lesson.course,
    detail: detail(lesson).filter(Boolean).join(" · "),
  }));
}

/** Jour de la semaine d'aujourd'hui, 1 = lundi … 7 = dimanche. */
export const isoWeekday = (date = new Date()) => date.getDay() || 7;

/** Jours montrés : du lundi au vendredi, puis jusqu'au dernier jour qui a cours (samedi…). */
export function weekdaysOf(lessons: { weekday: number }[]): number[] {
  const last = Math.max(5, ...lessons.map((lesson) => lesson.weekday));
  return Array.from({ length: last }, (_, index) => index + 1);
}

/** Horaire publié en lecture (maquettes `gestion/mon-horaire`, `portail/enfant-horaire`) : un
 *  jour à la fois (aujourd'hui d'abord, sinon le premier jour) ; avec `columns`, la semaine en
 *  colonnes sur un grand écran. Les séances arrivent déjà rangées par jour et par heure. */
export function WeekSchedule({
  dayNames,
  lessons,
  label,
  today,
  todayLabel,
  emptyDay,
  columns = false,
}: {
  dayNames: DayNames;
  lessons: ScheduleLesson[];
  /** Nom du choix du jour, pour les lecteurs d'écran. */
  label: string;
  today: number;
  todayLabel: string;
  emptyDay: string;
  columns?: boolean;
}) {
  const days = weekdaysOf(lessons).map((weekday) => ({
    weekday,
    label: dayNames.long[weekday - 1] ?? "",
    short: dayNames.short[weekday - 1] ?? "",
  }));
  const first = days.some((day) => day.weekday === today) ? today : 1;
  const [picked, setPicked] = useState(String(first));
  const of = (weekday: number) => lessons.filter((lesson) => lesson.weekday === weekday);

  return (
    <>
      <div className={cn("flex flex-col gap-3", columns && "lg:hidden")}>
        <Segmented
          value={picked}
          onValueChange={setPicked}
          label={label}
          className="w-full *:px-1"
          options={days.map((day) => ({ value: String(day.weekday), label: day.short }))}
        />
        <DayList lessons={of(Number(picked))} emptyDay={emptyDay} />
      </div>
      {columns && (
        <div
          className="hidden gap-2.5 lg:grid"
          style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}
        >
          {days.map((day) => {
            const isToday = day.weekday === today;
            return (
              <section key={day.weekday} className="flex min-w-0 flex-col gap-2">
                <h3
                  className={cn(
                    "px-0.5 py-1 text-xs font-bold tracking-wide text-ink-3 uppercase",
                    isToday && "text-lake-700",
                  )}
                >
                  {isToday ? `${day.label} · ${todayLabel}` : day.label}
                </h3>
                {of(day.weekday).map((lesson) => (
                  <article
                    key={lesson.key}
                    className={cn(
                      "flex flex-col gap-0.5 rounded-field border border-l-4 border-line border-l-lake bg-card px-2.5 py-2",
                      isToday && "bg-lake-50",
                    )}
                  >
                    <span className="text-xs text-ink-3 tabular-nums">{lesson.time}</span>
                    <b className="text-sm">{lesson.title}</b>
                    <span className="text-xs text-ink-3">{lesson.detail}</span>
                  </article>
                ))}
                {of(day.weekday).length === 0 && (
                  <p className="px-0.5 py-2 text-xs text-ink-3">{emptyDay}</p>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}

function DayList({ lessons, emptyDay }: { lessons: ScheduleLesson[]; emptyDay: string }) {
  if (lessons.length === 0) return <p className="text-sm text-ink-3">{emptyDay}</p>;
  return (
    <ul className="flex flex-col">
      {lessons.map((lesson) => (
        <li
          key={lesson.key}
          className="grid grid-cols-[4rem_minmax(0,1fr)] items-start gap-2.5 border-b border-line py-2 last:border-b-0"
        >
          {/* Début et fin l'un sous l'autre : la colonne reste étroite au téléphone. */}
          <span className="flex flex-col text-sm leading-snug text-ink-3 tabular-nums">
            {lesson.time.split(" – ").map((part) => (
              <span key={part}>{part}</span>
            ))}
          </span>
          <span className="flex min-w-0 flex-col">
            <b className="text-md">{lesson.title}</b>
            <span className="text-sm text-ink-3">{lesson.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
