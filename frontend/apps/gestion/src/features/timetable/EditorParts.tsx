// Emploi du temps : pièces de l'éditeur communes aux vues par classe, par enseignant et par salle
// (EDT.2a, EDT.2b) : la semaine en grille (ordinateur), une journée en liste (téléphone), une séance,
// une case libre, la phrase d'un conflit.
import type { Schemas } from "@mwangaza/api";
import { type TFunction, useTranslation } from "@mwangaza/i18n";
import { Icon, cn } from "@mwangaza/ui";
import type { DragEvent } from "react";

import { type Absence, isBlocked } from "./availability";
import {
  type Board,
  type Days,
  type EditorCourse,
  type Entry,
  type Issue,
  type Placed,
  type Tint,
  type View,
  colorOf,
  lanesOf,
  rowsOf,
  tint,
} from "./editor";
import { dayName, hoursText } from "./rules";

/** Ce qu'on est en train de placer : une séance « À placer », ou une séance qu'on glisse. */
export type Pick = { course: EditorCourse; length: number; entry?: string; room: string | null };

export const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** Hachures d'une heure où l'enseignant est absent. */
export const ABSENT_CLASS =
  "border-solid bg-[repeating-linear-gradient(135deg,var(--color-line-soft)_0_6px,transparent_6px_12px)] font-semibold text-ink-2";

/** L'heure `index` d'un jour tombe-t-elle sur une absence ? */
export function absentAt(
  absences: Absence[] | undefined,
  slots: Schemas["TimeSlot"][],
  weekday: number,
  index: number,
): boolean {
  const slot = slots.find((item) => item.kind === "lesson" && item.index === index);
  return Boolean(absences?.length && slot && isBlocked(absences, weekday, slot));
}

/** Phrase d'un conflit, avec le jour, les heures et le type de règle ou de salle en mots. */
export function IssueText({ issue }: { issue: Issue }) {
  const { t, i18n } = useTranslation();
  const values = issue.values as Record<string, number | string>;
  const first = typeof values.first === "number" ? values.first : undefined;
  const last = typeof values.last === "number" ? values.last : first;
  const kind = String(values.kind ?? "");
  return (
    <>
      {t(`timetable.editor.codes.${issue.code as "same_class"}`, {
        ...values,
        ...(values.day ? { day: dayName(Number(values.day), i18n.language) } : {}),
        ...(first !== undefined ? { hours: hoursText(first, last ?? first, t) } : {}),
        ...(values.other
          ? { other: t(`timetable.constraints.kinds.${values.other as "fixed_lesson"}`) }
          : {}),
        ...(kind ? { kind: t(`timetable.kinds.${kind as "lab"}`) } : {}),
        defaultValue: issue.code,
      })}
    </>
  );
}

type GridProps = {
  board: Board;
  placed: Placed[];
  days: Days;
  entries: Entry[];
  marks: Map<string, Issue>;
  picked: Pick | null;
  onOpen: (entry: Entry) => void;
  onPick: (entry: Entry) => void;
  onUnpick: () => void;
  onDropAt: (weekday: number, first: number) => void;
  onDropOn: (entry: Entry) => void;
  /** Ce que dit chaque séance : la vue par classe tait la classe, etc. */
  context: View;
  /** Vue par enseignant : ses absences, en cases hachurées. */
  absences?: Absence[];
};

/** La semaine d'une classe, d'un enseignant ou d'une salle : jours en colonnes, heures et récréations en lignes ; une séance
 *  couvre ses heures (et la récréation qu'elle passe) ; deux séances en même temps se partagent
 *  la largeur. */
export function WeekGrid(props: GridProps) {
  const { t, i18n } = useTranslation();
  const { board, placed, days, entries, marks, picked } = props;
  const rows = rowsOf(days);
  const weekdays = [...days.keys()];
  const rowOf = (key: string) => rows.findIndex((row) => row.key === key) + 2;
  const allow = (event: DragEvent) => picked && event.preventDefault();
  const cells: React.ReactNode[] = [];

  weekdays.forEach((weekday, column) => {
    const slots = days.get(weekday) ?? [];
    const lessons = new Set(
      slots.filter((slot) => slot.kind === "lesson").map((slot) => slot.index),
    );
    const breaks = new Set<number>();
    let previous = 0;
    for (const slot of slots) {
      if (slot.kind === "lesson") previous = slot.index ?? previous;
      else breaks.add(previous);
    }
    const mine = entries.filter((entry) => entry.weekday === weekday);
    const lanes = lanesOf(mine);
    const covered = new Set<string>();
    for (const entry of mine) {
      const start = rowOf(`L${entry.first}`);
      const end = rowOf(`L${entry.first + entry.length - 1}`);
      rows.slice(start - 2, end - 1).forEach((row) => covered.add(row.key));
      cells.push(
        <Lesson
          key={entry.id}
          board={board}
          entry={entry}
          mark={marks.get(entry.id)}
          context={props.context}
          style={{
            gridColumn: column + 2,
            gridRow: `${start} / ${end + 1}`,
            width: `${100 / (lanes.get(entry.id)?.lanes ?? 1)}%`,
            marginLeft: `${(100 * (lanes.get(entry.id)?.lane ?? 0)) / (lanes.get(entry.id)?.lanes ?? 1)}%`,
          }}
          onOpen={() => props.onOpen(entry)}
          onDragStart={() => props.onPick(entry)}
          onDragEnd={props.onUnpick}
          onDragOver={(event) =>
            picked?.entry && picked.entry !== entry.id && !entry.locked && event.preventDefault()
          }
          onDrop={() => props.onDropOn(entry)}
        />,
      );
    }
    for (const row of rows) {
      if (covered.has(row.key)) continue;
      const place = { gridColumn: column + 2, gridRow: rowOf(row.key) };
      if (row.kind === "break") {
        if (breaks.has(row.index)) {
          cells.push(
            <div
              key={`${weekday}-${row.key}`}
              style={place}
              className="rounded-md bg-gray-50 text-center text-xs leading-5 text-ink-3"
            >
              {t("timetable.editor.break")}
            </div>,
          );
        }
        continue;
      }
      if (!lessons.has(row.index)) {
        cells.push(
          <div key={`${weekday}-${row.key}`} style={place} className="p-2 text-sm text-ink-3">
            {t("timetable.editor.none")}
          </div>,
        );
        continue;
      }
      const shade: Tint | null = picked
        ? tint(board, placed, picked, weekday, row.index, picked.entry ? [picked.entry] : [])
        : null;
      cells.push(
        <FreeCell
          key={`${weekday}-${row.key}`}
          style={place}
          shade={shade}
          absent={absentAt(props.absences, slots, weekday, row.index)}
          board={board}
          onDragOver={allow}
          onDrop={() => props.onDropAt(weekday, row.index)}
          onClick={() => picked && shade?.kind !== "short" && props.onDropAt(weekday, row.index)}
        />,
      );
    }
  });

  return (
    <div
      className="grid min-w-[640px] gap-1"
      style={{
        gridTemplateColumns: `4.5rem repeat(${weekdays.length}, minmax(0, 1fr))`,
        gridTemplateRows: [
          "auto",
          ...rows.map((row) => (row.kind === "lesson" ? "minmax(3.5rem, auto)" : "1.25rem")),
        ].join(" "),
      }}
    >
      {weekdays.map((weekday, column) => (
        <div
          key={weekday}
          style={{ gridColumn: column + 2, gridRow: 1 }}
          className="px-1 text-sm font-semibold text-ink-3"
        >
          {capitalized(dayName(weekday, i18n.language))}
        </div>
      ))}
      {rows.map((row) => (
        <div
          key={row.key}
          style={{ gridColumn: 1, gridRow: rowOf(row.key) }}
          className="px-1 py-1.5 text-xs text-ink-3"
        >
          {row.kind === "lesson" ? (
            <>
              <b className="block text-sm text-ink">
                {t("timetable.constraints.nth", { count: row.index })}
              </b>
              {row.start.slice(0, 5)}
            </>
          ) : (
            t("timetable.editor.breakRow")
          )}
        </div>
      ))}
      {cells}
    </div>
  );
}

function FreeCell({
  style,
  shade,
  absent,
  board,
  onDragOver,
  onDrop,
  onClick,
}: {
  style: React.CSSProperties;
  shade: Tint | null;
  absent: boolean;
  board: Board;
  onDragOver: (event: DragEvent) => void;
  onDrop: () => void;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  const text = !shade
    ? t(absent ? "timetable.editor.absent" : "timetable.editor.free")
    : shade.kind === "fits"
      ? t("timetable.editor.tint.fits")
      : shade.kind === "short"
        ? t("timetable.editor.tint.short")
        : shade.kind === "absent"
          ? t("timetable.editor.tint.absent", { name: shade.teacher })
          : conflictText(shade, board, t);
  return (
    <button
      type="button"
      style={style}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={onClick}
      disabled={!shade || shade.kind === "short"}
      className={cn(
        "rounded-lg border border-dashed border-line p-2 text-left text-xs text-ink-3",
        !shade && absent && ABSENT_CLASS,
        shade?.kind === "fits" &&
          "cursor-pointer border-solid border-ok-200 bg-ok-50 font-semibold text-ok",
        (shade?.kind === "conflict" || shade?.kind === "absent") &&
          "cursor-pointer border-solid border-due-200 bg-due-50 font-semibold text-due",
        shade?.kind === "short" && "bg-surface text-field",
      )}
    >
      {text}
    </button>
  );
}

function conflictText(shade: Extract<Tint, { kind: "conflict" }>, board: Board, t: TFunction) {
  const other = shade.other;
  const klass = board.classes.get(other.course.class_group)?.name ?? "";
  if (shade.reason === "teacher")
    return t("timetable.editor.tint.teacher", { name: other.course.teacher_name, class: klass });
  if (shade.reason === "room") {
    return t("timetable.editor.tint.room", {
      room: board.rooms.get(other.entry.room ?? "")?.name ?? "",
      class: klass,
    });
  }
  return t("timetable.editor.tint.class", { course: other.course.name });
}

/** Une séance placée : cours, enseignant (ou classe), salle, couleur du cours, cadenas, conflit. */
function Lesson({
  board,
  entry,
  mark,
  context,
  style,
  onOpen,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  board: Board;
  entry: Entry;
  mark: Issue | undefined;
  context: View;
  style?: React.CSSProperties;
  onOpen: () => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  onDragOver?: (event: DragEvent) => void;
  onDrop?: () => void;
}) {
  const { t } = useTranslation();
  const course = board.courses.get(entry.course);
  // Sans salle : « Salle à choisir » vient de la ligne du conflit (orange) quand un type est exigé.
  const room = entry.room ? board.rooms.get(entry.room)?.name : undefined;
  const group = course && board.classes.get(course.class_group)?.name;
  const details = (
    context === "class"
      ? [course?.teacher_name, room]
      : context === "teacher"
        ? [group, room]
        : [group, course?.teacher_name]
  )
    .filter(Boolean)
    .join(" · ");
  return (
    <button
      type="button"
      draggable={!entry.locked}
      style={{ ...style, borderLeftColor: colorOf(course?.name ?? "") }}
      onClick={onOpen}
      onDragStart={(event) => {
        event.dataTransfer.setData("text/plain", entry.id);
        onDragStart?.();
      }}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={cn(
        "relative flex min-h-14 min-w-0 flex-col gap-0.5 rounded-lg border border-l-4 border-line bg-card px-2 py-1.5 text-left shadow-xs",
        entry.locked ? "cursor-pointer" : "cursor-grab",
        mark?.level === "error" && "border-due ring-1 ring-due",
      )}
    >
      {entry.locked && (
        <Icon
          name="lock"
          size={14}
          className="absolute top-1.5 right-1.5 text-ink-2"
          aria-label={t("timetable.editor.locked")}
        />
      )}
      <b className="pr-4 text-sm leading-tight break-words hyphens-auto">{course?.name}</b>
      <span className="text-xs leading-tight text-ink-3">{details}</span>
      {mark && (
        <span
          className={cn(
            "text-xs leading-tight font-semibold",
            mark.level === "error" ? "text-due" : "text-warn",
          )}
        >
          {t(`timetable.editor.short.${mark.code as "same_class"}`, { defaultValue: "" })}
        </span>
      )}
    </button>
  );
}

/** Une journée d'une classe, d'un enseignant ou d'une salle, au téléphone : chaque heure (ou
 *  suite d'heures) dans l'ordre ; une séance qui commence pendant une autre s'ajoute à son heure. */
export function DayList({
  board,
  days,
  weekday,
  entries,
  marks,
  context,
  absences,
  onOpen,
}: {
  board: Board;
  days: Days;
  weekday: number;
  entries: Entry[];
  marks: Map<string, Issue>;
  context: View;
  absences?: Absence[];
  onOpen: (entry: Entry) => void;
}) {
  const { t } = useTranslation();
  const slots = days.get(weekday) ?? [];
  const mine = entries
    .filter((entry) => entry.weekday === weekday)
    .sort((a, b) => a.first - b.first);
  const items: React.ReactNode[] = [];
  // Dernière heure couverte par une séance déjà montrée, et dernière heure de cours passée.
  let until = 0;
  let previous = 0;
  for (const slot of slots) {
    if (slot.kind === "break") {
      if (until > previous) continue; // une séance passe cette récréation
      items.push(
        <div key={slot.id} className="rounded-md bg-gray-50 px-2 py-0.5 text-xs text-ink-3">
          {t("timetable.editor.breakAt", {
            start: slot.start.slice(0, 5),
            end: slot.end.slice(0, 5),
          })}
        </div>,
      );
      continue;
    }
    const index = slot.index ?? 0;
    previous = index;
    const starting = mine.filter((entry) => entry.first === index);
    if (index <= until && !starting.length) continue;
    const last = Math.max(index, ...starting.map((entry) => entry.first + entry.length - 1));
    until = Math.max(until, starting.length ? last : 0);
    const label =
      last > index
        ? t("timetable.editor.span", {
            first: t("timetable.constraints.nth", { count: index }),
            last: t("timetable.constraints.nth", { count: last }),
          })
        : t("timetable.constraints.nth", { count: index });
    items.push(
      <div key={slot.id} className="flex items-stretch gap-2">
        <div className="w-16 shrink-0 pt-1.5 text-xs text-ink-3">
          <b className="block text-sm text-ink">{label}</b>
          {slot.start.slice(0, 5)}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {starting.length ? (
            starting.map((entry) => (
              <Lesson
                key={entry.id}
                board={board}
                entry={entry}
                mark={marks.get(entry.id)}
                context={context}
                onOpen={() => onOpen(entry)}
              />
            ))
          ) : (
            <div
              className={cn(
                "min-h-14 rounded-lg border border-dashed border-line p-2 text-xs text-ink-3",
                absentAt(absences, slots, weekday, index) && ABSENT_CLASS,
              )}
            >
              {t(
                absentAt(absences, slots, weekday, index)
                  ? "timetable.editor.absent"
                  : "timetable.editor.free",
              )}
            </div>
          )}
        </div>
      </div>,
    );
  }
  return <div className="flex flex-col gap-2">{items}</div>;
}
