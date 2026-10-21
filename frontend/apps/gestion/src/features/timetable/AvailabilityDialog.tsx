// Disponibilités d'un enseignant (EDT.1b, maquette `disponibilites-enseignant`) : charge au plus
// par semaine, heures au plus par jour, absences touchées sur la semaine d'une grille. Ouverte
// depuis « Charges des enseignants ». Droit `timetable.manage`.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Select,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { type Absence, isBlocked, isWholeDay, toggleDay, toggleLesson } from "./availability";
import type { TeacherProfile, TimeGrid } from "./data";

export const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export const dayKey = (weekday: number) => DAY_KEYS[weekday - 1] ?? "sun";

type Props = {
  teacher: { id: string; name: string };
  hours: string;
  profile: TeacherProfile | undefined;
  grids: TimeGrid[];
  schoolMaxDay: number;
  onClose: () => void;
};

export function AvailabilityDialog({
  teacher,
  hours,
  profile,
  grids,
  schoolMaxDay,
  onClose,
}: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [maxWeek, setMaxWeek] = useState(String(profile?.max_week_hours ?? ""));
  const [maxDay, setMaxDay] = useState(String(profile?.max_day_hours ?? ""));
  const [absences, setAbsences] = useState<Absence[]>(profile?.unavailable ?? []);
  const [gridId, setGridId] = useState(grids[0]?.id ?? "");
  const grid = grids.find((item) => item.id === gridId) ?? grids[0];

  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/timetable/teachers/{id}/", {
          params: { path: { id: teacher.id } },
          body: {
            max_week_hours: Number(maxWeek) || null,
            max_day_hours: Number(maxDay) || null,
            unavailable: absences,
          },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.timetable });
      onClose();
    },
  });

  const lessons = (grid?.slots ?? []).filter((slot) => slot.kind === "lesson");
  const days = [...new Set(lessons.map((slot) => slot.weekday))].sort();
  const indexes = [...new Set(lessons.map((slot) => slot.index ?? 0))].sort((a, b) => a - b);
  const lessonAt = (weekday: number, index: number) =>
    lessons.find((slot) => slot.weekday === weekday && slot.index === index);
  const dayLessons = (weekday: number) => lessons.filter((slot) => slot.weekday === weekday);
  const digits = (value: string) => value.replace(/\D/g, "").slice(0, 2);

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("timetable.availability.title")}
        description={t("timetable.availability.subtitle", { name: teacher.name, hours })}
        className="w-[min(760px,calc(100vw-32px))]"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button disabled={save.isPending} onClick={() => save.mutate()}>
              {t("timetable.availability.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
            <Field
              id="availability-week"
              label={t("timetable.availability.maxWeek")}
              help={t("timetable.availability.maxWeekHelp")}
            >
              {(control) => (
                <Input
                  {...control}
                  inputMode="numeric"
                  value={maxWeek}
                  onChange={(event) => setMaxWeek(digits(event.target.value))}
                />
              )}
            </Field>
            <Field id="availability-day" label={t("timetable.availability.maxDay")}>
              {(control) => (
                <Input
                  {...control}
                  inputMode="numeric"
                  placeholder={t("timetable.availability.maxDayPlaceholder", {
                    count: schoolMaxDay,
                  })}
                  value={maxDay}
                  onChange={(event) => setMaxDay(digits(event.target.value))}
                />
              )}
            </Field>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <b className="text-sm">{t("timetable.availability.absences")}</b>
            {grids.length > 1 && (
              <Select
                aria-label={t("timetable.availability.grid")}
                value={grid?.id}
                onChange={(event) => setGridId(event.target.value)}
                className="w-auto"
              >
                {grids.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            )}
          </div>
          {lessons.length === 0 ? (
            <Banner tone="info">{t("timetable.availability.noGrid")}</Banner>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-separate border-spacing-1 text-sm">
                <thead>
                  <tr>
                    <th />
                    {days.map((day) => (
                      <th key={day}>
                        <button
                          type="button"
                          className={cn(
                            "w-full rounded-input px-2 py-1 font-bold underline-offset-2 hover:underline",
                            isWholeDay(absences, day) && "text-due",
                          )}
                          aria-pressed={isWholeDay(absences, day)}
                          aria-label={t("timetable.availability.wholeDay", {
                            day: t(`timetable.days.${dayKey(day)}`),
                          })}
                          onClick={() => setAbsences(toggleDay(absences, day))}
                        >
                          {t(`timetable.daysShort.${dayKey(day)}`)}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {indexes.map((index) => (
                    <tr key={index}>
                      <th className="pr-2 text-left font-bold whitespace-nowrap">
                        {t("timetable.availability.lesson", { count: index })}
                      </th>
                      {days.map((day) => {
                        const lesson = lessonAt(day, index);
                        if (!lesson) {
                          return (
                            <td key={day} className="text-center text-ink-3">
                              —
                            </td>
                          );
                        }
                        const absent = isBlocked(absences, day, lesson);
                        const time = lesson.start.slice(0, 5);
                        return (
                          <td key={day}>
                            <button
                              type="button"
                              aria-pressed={absent}
                              aria-label={`${t(`timetable.days.${dayKey(day)}`)} ${time}`}
                              title={`${time}–${lesson.end.slice(0, 5)}`}
                              onClick={() =>
                                setAbsences(toggleLesson(absences, day, lesson, dayLessons(day)))
                              }
                              className={cn(
                                "w-full min-w-[56px] rounded-pill px-2 py-1 text-xs font-bold ring-1 ring-inset",
                                absent
                                  ? "bg-due-50 text-due ring-due-200"
                                  : "bg-gray-50 text-ink-2 ring-line",
                              )}
                            >
                              {absent
                                ? t("timetable.availability.absent")
                                : t("timetable.availability.free")}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-sm text-ink-3">{t("timetable.availability.help")}</p>
          {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
