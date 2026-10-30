// Vue « Emploi du temps » de la grille des cours (EDT.1b, maquette `cours-placement`) : séances,
// heures au plus par jour, salle exigée, récréation, moment. Même brouillon que la vue « Bulletin »
// (`CoursesPage`) : « Enregistrer » envoie tout d'un bloc. Droit `timetable.manage`.
import { useTranslation } from "@mwangaza/i18n";
import { Input, Select, Switch, Table } from "@mwangaza/ui";

import { ROOM_KINDS, type Room } from "../timetable/data";
import { type Part, patternProblem, type PlacementDraft, proposedPattern } from "./placement";

export type PlacementRow = {
  key: string;
  name: string;
  weekly_hours: string;
  category: string;
  placement: PlacementDraft;
};

type Props<T extends PlacementRow> = {
  rows: T[];
  rooms: Room[];
  schoolMaxPerDay: number;
  errorsOf: (index: number) => string[];
  onChange: (row: T, change: { weekly_hours?: string; placement?: PlacementDraft }) => void;
};

export function PlacementTable<T extends PlacementRow>({
  rows,
  rooms,
  schoolMaxPerDay,
  errorsOf,
  onChange,
}: Props<T>) {
  const { t } = useTranslation();
  const place = (row: T, change: Partial<PlacementDraft>) =>
    onChange(row, { placement: { ...row.placement, ...change } });
  const active = rooms.filter((room) => room.is_active);

  return (
    <>
      <Table freeze>
        <thead>
          <tr>
            <th>{t("courses.columns.name")}</th>
            <th className="text-right">{t("courses.columns.hours")}</th>
            <th>{t("timetable.placement.lessons")}</th>
            <th>{t("timetable.placement.perDay")}</th>
            <th>{t("timetable.placement.room")}</th>
            <th>{t("timetable.placement.spanBreak")}</th>
            <th>{t("timetable.placement.part")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} className="text-center text-ink-2">
                {t("courses.empty")}
              </td>
            </tr>
          )}
          {rows.map((row, index) => {
            const label = row.name || t("courses.newCourse");
            const hours = Number(row.weekly_hours) || 0;
            const problem = patternProblem(row.placement.lesson_pattern, hours);
            const messages = [
              ...(problem?.key === "bad" ? [t("timetable.placement.patternBad")] : []),
              ...(problem?.key === "hours"
                ? [t("timetable.placement.patternHours", { sum: problem.sum, hours })]
                : []),
              ...errorsOf(index),
            ];
            const spans = row.placement.can_span_break ?? row.category === "practical";
            // Une salle retirée encore exigée reste montrée, pour pouvoir la changer.
            const kept = rooms.find(
              (room) => !room.is_active && row.placement.room === `room:${room.id}`,
            );
            return (
              <tr key={row.key}>
                <td data-wrap>
                  <b>{label}</b>
                  {messages.map((message) => (
                    <p key={message} role="alert" className="mt-1 text-xs text-due">
                      {message}
                    </p>
                  ))}
                </td>
                <td className="text-right">
                  <Input
                    aria-label={`${t("courses.columns.hours")} | ${label}`}
                    inputMode="numeric"
                    value={row.weekly_hours}
                    onChange={(event) =>
                      onChange(row, { weekly_hours: event.target.value.replace(/\D/g, "") })
                    }
                    className="ml-auto w-[64px] text-right"
                  />
                </td>
                <td>
                  <Input
                    aria-label={`${t("timetable.placement.lessons")} | ${label}`}
                    placeholder={proposedPattern(hours, row.category === "practical")}
                    value={row.placement.lesson_pattern}
                    aria-invalid={problem !== null}
                    onChange={(event) => place(row, { lesson_pattern: event.target.value })}
                    className="w-[100px]"
                  />
                </td>
                <td>
                  <Input
                    aria-label={`${t("timetable.placement.perDay")} | ${label}`}
                    inputMode="numeric"
                    placeholder={String(schoolMaxPerDay)}
                    value={row.placement.max_per_day}
                    onChange={(event) =>
                      place(row, { max_per_day: event.target.value.replace(/\D/g, "").slice(0, 2) })
                    }
                    className="w-[64px] text-right"
                  />
                </td>
                <td>
                  <Select
                    aria-label={`${t("timetable.placement.room")} | ${label}`}
                    value={row.placement.room}
                    onChange={(event) => place(row, { room: event.target.value })}
                    className="min-w-[210px]"
                  >
                    <option value="">{t("timetable.placement.homeRoom")}</option>
                    <optgroup label={t("timetable.placement.kinds")}>
                      {ROOM_KINDS.filter((kind) => kind !== "classroom").map((kind) => (
                        <option key={kind} value={`kind:${kind}`}>
                          {t("timetable.placement.kindOption", {
                            kind: t(`timetable.kinds.${kind}`),
                          })}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label={t("timetable.placement.rooms")}>
                      {[...active, ...(kept ? [kept] : [])].map((room) => (
                        <option key={room.id} value={`room:${room.id}`}>
                          {room.name}
                        </option>
                      ))}
                    </optgroup>
                  </Select>
                </td>
                <td>
                  <Switch
                    aria-label={`${t("timetable.placement.spanBreak")} | ${label}`}
                    checked={spans}
                    onCheckedChange={(checked) => place(row, { can_span_break: checked })}
                  />
                </td>
                <td>
                  <Select
                    aria-label={`${t("timetable.placement.part")} | ${label}`}
                    value={row.placement.preferred_part}
                    onChange={(event) => place(row, { preferred_part: event.target.value as Part })}
                    className="min-w-[130px]"
                  >
                    <option value="any">{t("timetable.placement.parts.any")}</option>
                    <option value="morning">{t("timetable.placement.parts.morning")}</option>
                  </Select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
      <p className="px-5 py-3 text-sm text-ink-3">{t("timetable.placement.spanBreakHelp")}</p>
    </>
  );
}
