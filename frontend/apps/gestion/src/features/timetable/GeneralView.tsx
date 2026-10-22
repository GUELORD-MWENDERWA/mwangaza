// Emploi du temps : horaire général (EDT.2b, maquette `emploi-du-temps-general`). Toutes les classes
// en lignes, les heures en colonnes. Semaine (ordinateur) : noms courts ; un jour (onglets, toujours
// au téléphone) : nom entier et enseignant. Mêmes gestes que les autres vues : toucher une séance
// ouvre sa fenêtre ; glisser une séance la déplace dans la ligne de sa classe ou l'échange.
import { useTranslation } from "@mwangaza/i18n";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  Tabs,
  TabsList,
  TabsTrigger,
  cn,
} from "@mwangaza/ui";
import { type DragEvent, useState } from "react";

import {
  type Board,
  type DraftState,
  type Entry,
  type Issue,
  type Placed,
  type Tint,
  colorOf,
  hoursOf,
  lanesOf,
  tint,
} from "./editor";
import { type Pick, capitalized } from "./EditorParts";
import { dayName, hoursText } from "./rules";

type Props = {
  board: Board;
  placed: Placed[];
  state: DraftState;
  marks: Map<string, Issue>;
  picked: Pick | null;
  codes: Map<string, string>;
  /** Ordinateur : l'onglet « Semaine » ; téléphone : un jour à la fois. */
  week: boolean;
  onOpen: (entry: Entry) => void;
  onPick: (entry: Entry) => void;
  onUnpick: () => void;
  onDropAt: (weekday: number, first: number) => void;
  onDropOn: (entry: Entry) => void;
  onShowClass: (id: string) => void;
};

const shortDay = (weekday: number, language: string) =>
  capitalized(
    new Intl.DateTimeFormat(language, { weekday: "short", timeZone: "UTC" }).format(
      new Date(Date.UTC(2024, 0, weekday)),
    ),
  );

export function GeneralView(props: Props) {
  const { t, i18n } = useTranslation();
  const { board, state, marks, picked, codes } = props;
  const classes = [...board.classes.values()];
  // Colonnes : les heures de cours de chaque jour, toutes grilles des classes confondues.
  const lessons = new Map<number, Set<number>>();
  for (const grid of new Set(classes.map((row) => board.gridOf(row.id)))) {
    for (const [weekday, slots] of board.daysOfGrid(grid)) {
      for (const slot of slots) {
        if (slot.kind === "lesson" && slot.index) {
          lessons.set(weekday, (lessons.get(weekday) ?? new Set()).add(slot.index));
        }
      }
    }
  }
  const weekdays = [...lessons.keys()].sort((a, b) => a - b);
  const [chosen, setChosen] = useState<string>(props.week ? "week" : String(weekdays[0] ?? 1));
  const shown =
    chosen === "week" || !lessons.has(Number(chosen))
      ? props.week
        ? weekdays
        : weekdays.slice(0, 1)
      : [Number(chosen)];
  const oneDay = shown.length === 1 && (chosen !== "week" || !props.week);
  const today = oneDay ? shown[0] : undefined;

  const template = ["minmax(7.5rem, 9rem)"];
  const column = new Map<string, number>();
  shown.forEach((weekday, at) => {
    for (const index of [...(lessons.get(weekday) ?? [])].sort((a, b) => a - b)) {
      template.push(oneDay ? "minmax(7rem, 1fr)" : "minmax(2.5rem, 1fr)");
      column.set(`${weekday}-${index}`, template.length);
    }
    if (at < shown.length - 1) template.push("0.5rem");
  });
  const times = board.daysOfGrid(undefined);

  const cells: React.ReactNode[] = [];
  let row = 3;
  for (const group of classes) {
    const days = board.daysOfClass(group.id);
    const mine = state.entries.filter(
      (entry) =>
        shown.includes(entry.weekday) && board.courses.get(entry.course)?.class_group === group.id,
    );
    const lanes = new Map<string, { lane: number; lanes: number }>();
    for (const weekday of shown) {
      for (const [id, lane] of lanesOf(mine.filter((entry) => entry.weekday === weekday))) {
        lanes.set(id, lane);
      }
    }
    const height = Math.max(1, ...[...lanes.values()].map((lane) => lane.lanes));
    const load = state.classes.find((item) => item.class_group === group.id);
    const dayLessons = today
      ? (days.get(today) ?? []).filter((slot) => slot.kind === "lesson").length
      : 0;
    cells.push(
      <div
        key={group.id}
        style={{ gridColumn: 1, gridRow: `${row} / span ${height}` }}
        className="sticky left-0 z-10 flex flex-col justify-center bg-card pr-2"
      >
        <button
          type="button"
          className="truncate text-left text-sm font-bold text-ink hover:underline"
          onClick={() => props.onShowClass(group.id)}
        >
          {group.name}
        </button>
        <span className="text-xs text-ink-3">
          {today
            ? t("timetable.editor.general.dayLoad", {
                placed: hoursOf(mine, today),
                lessons: dayLessons,
              })
            : t("timetable.editor.general.weekLoad", {
                placed: load?.placed ?? 0,
                due: load?.due ?? 0,
              })}
        </span>
      </div>,
    );
    const covered = new Set(
      mine.flatMap((entry) =>
        Array.from({ length: entry.length }, (_, k) => `${entry.weekday}-${entry.first + k}`),
      ),
    );
    for (const entry of mine) {
      const at = column.get(`${entry.weekday}-${entry.first}`);
      const course = board.courses.get(entry.course);
      if (!at || !course) continue;
      const room = entry.room ? board.rooms.get(entry.room)?.name : undefined;
      const detail = [
        course.name,
        course.teacher_name,
        room,
        `${dayName(entry.weekday, i18n.language)}, ${hoursText(entry.first, entry.first + entry.length - 1, t)}`,
      ]
        .filter(Boolean)
        .join(" · ");
      const mark = marks.get(entry.id);
      cells.push(
        <button
          key={entry.id}
          type="button"
          draggable={!entry.locked}
          title={detail}
          aria-label={detail}
          style={{
            gridColumn: `${at} / span ${entry.length}`,
            gridRow: row + (lanes.get(entry.id)?.lane ?? 0),
            borderLeftColor: colorOf(course.name),
          }}
          className={cn(
            "flex min-w-0 overflow-hidden rounded-md border border-l-[3px] border-line bg-card px-1 text-left text-xs shadow-xs",
            oneDay
              ? "min-h-12 flex-col justify-center py-1"
              : "min-h-7 items-center gap-0.5 font-semibold whitespace-nowrap",
            entry.locked ? "cursor-pointer" : "cursor-grab",
            mark?.level === "error" && "border-due ring-1 ring-due",
          )}
          onClick={() => props.onOpen(entry)}
          onDragStart={(event) => {
            event.dataTransfer.setData("text/plain", entry.id);
            props.onPick(entry);
          }}
          onDragEnd={props.onUnpick}
          onDragOver={(event) =>
            picked?.entry && picked.entry !== entry.id && !entry.locked && event.preventDefault()
          }
          onDrop={() => props.onDropOn(entry)}
        >
          {oneDay ? (
            <>
              <b className="leading-tight break-words hyphens-auto">
                {entry.locked && (
                  <Icon name="lock" size={10} className="mr-0.5 inline text-ink-2" aria-hidden />
                )}
                {course.name}
              </b>
              <span className="truncate text-ink-3">{course.teacher_name}</span>
            </>
          ) : (
            <>
              {entry.locked && (
                <Icon name="lock" size={10} className="shrink-0 text-ink-2" aria-hidden />
              )}
              <span className="truncate">{codes.get(course.id)}</span>
            </>
          )}
        </button>,
      );
    }
    const mineToPlace = picked && picked.course.class_group === group.id;
    for (const weekday of shown) {
      const own = new Set(
        (days.get(weekday) ?? []).flatMap((slot) => (slot.kind === "lesson" ? [slot.index] : [])),
      );
      for (const index of lessons.get(weekday) ?? []) {
        const at = column.get(`${weekday}-${index}`);
        if (!at || !own.has(index) || covered.has(`${weekday}-${index}`)) continue;
        const style = { gridColumn: at, gridRow: `${row} / span ${height}` };
        if (!mineToPlace) {
          cells.push(
            <div
              key={`${group.id}-${weekday}-${index}`}
              style={style}
              className={cn(
                "rounded-md border border-dashed border-line",
                oneDay ? "min-h-12" : "min-h-7",
              )}
            />,
          );
          continue;
        }
        const shade = tint(
          board,
          props.placed,
          picked,
          weekday,
          index,
          picked.entry ? [picked.entry] : [],
        );
        cells.push(
          <FreeMini
            key={`${group.id}-${weekday}-${index}`}
            style={style}
            shade={shade}
            tall={oneDay}
            onDrop={() => props.onDropAt(weekday, index)}
          />,
        );
      }
    }
    row += height;
  }

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>
          {today && !props.week
            ? t("timetable.editor.general.titleDay", { day: dayName(today, i18n.language) })
            : t("timetable.editor.general.title")}
        </CardTitle>
        <Tabs value={chosen} onValueChange={setChosen}>
          <TabsList aria-label={t("timetable.editor.days")} className="max-w-full overflow-x-auto">
            {props.week && (
              <TabsTrigger value="week" className="px-2">
                {t("timetable.editor.general.week")}
              </TabsTrigger>
            )}
            {weekdays.map((weekday) => (
              <TabsTrigger key={weekday} value={String(weekday)} className="px-2">
                {shortDay(weekday, i18n.language)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto pb-1">
          <div
            className="grid w-max min-w-full gap-0.5"
            style={{ gridTemplateColumns: template.join(" ") }}
          >
            {shown.map((weekday) => {
              const indexes = [...(lessons.get(weekday) ?? [])].sort((a, b) => a - b);
              const first = column.get(`${weekday}-${indexes[0]}`) ?? 2;
              return [
                !oneDay && (
                  <div
                    key={`d${weekday}`}
                    style={{ gridColumn: `${first} / span ${indexes.length}`, gridRow: 1 }}
                    className="border-b-2 border-line px-1 text-sm font-semibold text-ink"
                  >
                    {capitalized(dayName(weekday, i18n.language))}
                  </div>
                ),
                ...indexes.map((index) => {
                  const start = times
                    .get(weekday)
                    ?.find((slot) => slot.kind === "lesson" && slot.index === index)?.start;
                  return (
                    <div
                      key={`h${weekday}-${index}`}
                      style={{ gridColumn: column.get(`${weekday}-${index}`), gridRow: 2 }}
                      className="px-1 text-xs whitespace-nowrap text-ink-3"
                    >
                      {oneDay
                        ? [t("timetable.constraints.nth", { count: index }), start?.slice(0, 5)]
                            .filter(Boolean)
                            .join(" · ")
                        : index}
                    </div>
                  );
                }),
              ];
            })}
            <div
              style={{ gridColumn: 1, gridRow: 2 }}
              className="sticky left-0 z-10 bg-card pr-2 text-xs text-ink-3"
            >
              {t(
                oneDay ? "timetable.editor.general.classDay" : "timetable.editor.general.classWeek",
              )}
            </div>
            {cells}
          </div>
        </div>
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-3">
          {!oneDay && <span>{t("timetable.editor.general.codesHint")}</span>}
          <span>{t("timetable.editor.general.dragHint")}</span>
          <span>{t("timetable.editor.general.classHint")}</span>
        </p>
      </CardContent>
    </Card>
  );
}

/** Une heure libre de la classe de la séance choisie : teinte, lâcher ou toucher pour placer. */
function FreeMini({
  style,
  shade,
  tall,
  onDrop,
}: {
  style: React.CSSProperties;
  shade: Tint;
  tall: boolean;
  onDrop: () => void;
}) {
  const { t } = useTranslation();
  const label =
    shade.kind === "fits"
      ? t("timetable.editor.tint.fits")
      : shade.kind === "short"
        ? t("timetable.editor.tint.short")
        : shade.kind === "absent"
          ? t("timetable.editor.tint.absent", { name: shade.teacher })
          : t("timetable.editor.general.taken");
  return (
    <button
      type="button"
      style={style}
      title={label}
      aria-label={label}
      disabled={shade.kind === "short"}
      onDragOver={(event: DragEvent) => shade.kind !== "short" && event.preventDefault()}
      onDrop={onDrop}
      onClick={onDrop}
      className={cn(
        "rounded-md border",
        tall ? "min-h-12" : "min-h-7",
        shade.kind === "fits" && "cursor-pointer border-ok-200 bg-ok-50",
        (shade.kind === "conflict" || shade.kind === "absent") &&
          "cursor-pointer border-due-200 bg-due-50",
        shade.kind === "short" && "border-line bg-surface",
      )}
    />
  );
}
