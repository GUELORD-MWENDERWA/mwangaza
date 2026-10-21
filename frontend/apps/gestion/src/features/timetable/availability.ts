// Absences d'un enseignant (EDT.1b) : un jour entier, ou une plage horaire de ce jour. Gardées en
// heures (« 07:30 »), pas en numéros d'heure : elles valent pour toutes les grilles de l'école.
// Mêmes règles que le serveur (`timetable/services.py`, `checks.py`).

export type Absence = { weekday: number; start?: string; end?: string };
export type Lesson = { start: string; end: string };

const clock = (value: string) => value.slice(0, 5);

export const isWholeDay = (list: Absence[], weekday: number) =>
  list.some((item) => item.weekday === weekday && !item.start);

/** L'heure tombe-t-elle sur une absence (jour entier, ou plage qui la chevauche) ? */
export function isBlocked(list: Absence[], weekday: number, lesson: Lesson): boolean {
  const start = clock(lesson.start);
  const end = clock(lesson.end);
  return list.some(
    (item) =>
      item.weekday === weekday && (!item.start || (item.start < end && (item.end ?? "") > start)),
  );
}

/** Toucher une heure : absente → libre, libre → absente. Dans une journée entière d'absence,
 *  seule cette heure redevient libre. */
export function toggleLesson(
  list: Absence[],
  weekday: number,
  lesson: Lesson,
  dayLessons: Lesson[],
): Absence[] {
  const others = list.filter((item) => item.weekday !== weekday);
  if (isWholeDay(list, weekday)) {
    const kept = dayLessons.filter((item) => clock(item.start) !== clock(lesson.start));
    return [...others, ...kept.map((item) => range(weekday, item))];
  }
  if (isBlocked(list, weekday, lesson)) {
    return list.filter((item) => item.weekday !== weekday || !isBlocked([item], weekday, lesson));
  }
  return [...list, range(weekday, lesson)];
}

/** Toucher un jour : toute la journée absente, ou de nouveau libre. */
export function toggleDay(list: Absence[], weekday: number): Absence[] {
  const others = list.filter((item) => item.weekday !== weekday);
  return isWholeDay(list, weekday) ? others : [...others, { weekday }];
}

const range = (weekday: number, lesson: Lesson): Absence => ({
  weekday,
  start: clock(lesson.start),
  end: clock(lesson.end),
});

/** « vendredi », « mardi 07:30–10:00 » : les plages qui se suivent sont réunies. */
export function describe(list: Absence[], dayName: (weekday: number) => string): string[] {
  const days = [...new Set(list.map((item) => item.weekday))].sort();
  return days.flatMap((weekday) => {
    if (isWholeDay(list, weekday)) return [dayName(weekday)];
    const ranges = list
      .filter((item) => item.weekday === weekday && item.start)
      .map((item) => ({ start: item.start!, end: item.end! }))
      .sort((a, b) => a.start.localeCompare(b.start));
    const merged: { start: string; end: string }[] = [];
    for (const item of ranges) {
      const last = merged.at(-1);
      if (last && last.end >= item.start) last.end = item.end > last.end ? item.end : last.end;
      else merged.push({ ...item });
    }
    return merged.map((item) => `${dayName(weekday)} ${item.start}–${item.end}`);
  });
}
