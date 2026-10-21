// Fenêtre d'une heure de l'horaire (EDT.2a, maquette `emploi-du-temps-classe`) : la déplacer,
// l'échanger, changer sa salle, la verrouiller, la retirer ; ou placer une séance « À placer ».
// Pour le téléphone, la tablette et le clavier ; à l'ordinateur, glisser fait la même chose. Une
// heure verrouillée ne bouge, ne s'échange, ne change de salle ni ne part (le serveur le refuse
// aussi).
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Select,
  Switch,
} from "@mwangaza/ui";
import { useState } from "react";

import {
  type Board,
  type EditorCourse,
  type Entry,
  type Gesture,
  type Placed,
  defaultRoom,
  tint,
} from "./editor";
import { dayName, hoursText } from "./rules";

const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

type Common = {
  board: Board;
  placed: Placed[];
  pending: boolean;
  onGesture(gesture: Gesture): Promise<unknown>;
  onClose: () => void;
};

/** Jour, puis heure de départ où la séance tient (libre ou en conflit), puis le bouton. */
function PositionPicker({
  board,
  placed,
  course,
  length,
  room,
  ignore,
  initialDay,
  label,
  button,
  disabled,
  onPick,
}: {
  board: Board;
  placed: Placed[];
  course: EditorCourse;
  length: number;
  room: string | null;
  ignore: string[];
  initialDay?: number;
  label: string;
  button: string;
  disabled: boolean;
  onPick: (weekday: number, first: number) => void;
}) {
  const { t, i18n } = useTranslation();
  const days = board.daysOfClass(course.class_group);
  const weekdays = [...days.keys()];
  const [weekday, setWeekday] = useState(initialDay ?? weekdays[0] ?? 1);
  const [first, setFirst] = useState<number | null>(null);
  const starts = (days.get(weekday) ?? [])
    .filter((slot) => slot.kind === "lesson" && slot.index)
    .map((slot) => {
      const index = slot.index ?? 0;
      return { index, tint: tint(board, placed, { course, length, room }, weekday, index, ignore) };
    })
    .filter((start) => start.tint.kind !== "short");
  const chosen =
    starts.find((start) => start.index === first)?.index ??
    starts.find((start) => start.tint.kind === "fits")?.index ??
    starts[0]?.index;

  return (
    <div className="flex flex-col gap-2">
      <b className="text-sm">{label}</b>
      <div className="flex flex-wrap gap-2">
        <Select
          aria-label={t("timetable.editor.dialog.day")}
          className="w-auto min-w-0 flex-1"
          value={weekday}
          disabled={disabled}
          onChange={(event) => {
            setWeekday(Number(event.target.value));
            setFirst(null);
          }}
        >
          {weekdays.map((day) => (
            <option key={day} value={day}>
              {capitalized(dayName(day, i18n.language))}
            </option>
          ))}
        </Select>
        <Select
          aria-label={t("timetable.editor.dialog.start")}
          className="w-auto min-w-0 flex-1"
          value={chosen ?? ""}
          disabled={disabled || !starts.length}
          onChange={(event) => setFirst(Number(event.target.value))}
        >
          {starts.map((start) => (
            <option key={start.index} value={start.index}>
              {t(
                start.tint.kind === "fits"
                  ? "timetable.editor.dialog.optionFree"
                  : "timetable.editor.dialog.optionConflict",
                { hours: hoursText(start.index, start.index + length - 1, t) },
              )}
            </option>
          ))}
        </Select>
        <Button
          disabled={disabled || chosen === undefined}
          onClick={() => chosen !== undefined && onPick(weekday, chosen)}
        >
          {button}
        </Button>
      </div>
      {!starts.length && (
        <p className="text-sm text-ink-3">{t("timetable.editor.dialog.noStart")}</p>
      )}
    </div>
  );
}

export function EntryDialog({
  entry,
  entries,
  ...common
}: Common & { entry: Entry; entries: Entry[] }) {
  const { t, i18n } = useTranslation();
  const { board, placed, pending, onGesture, onClose } = common;
  const [other, setOther] = useState("");
  const course = board.courses.get(entry.course);
  if (!course) return null;
  const group = board.classes.get(course.class_group);
  const where = (item: Entry) => ({
    day: dayName(item.weekday, i18n.language),
    hours: hoursText(item.first, item.first + item.length - 1, t),
  });
  const others = entries.filter(
    (item) =>
      item.id !== entry.id &&
      !item.locked &&
      board.courses.get(item.course)?.class_group === course.class_group,
  );
  const swapWith = others.find((item) => item.id === other) ?? others[0];
  const rooms = [...board.rooms.values()]
    .filter((room) => room.is_active || room.id === entry.room)
    .sort((a, b) => a.name.localeCompare(b.name, i18n.language, { numeric: true }));
  const then = (gesture: Gesture) => void onGesture(gesture).then(onClose, () => undefined);

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("timetable.editor.dialog.title", { course: course.name, ...where(entry) })}
        description={t("timetable.editor.dialog.subtitle", {
          teacher: course.teacher_name || t("timetable.editor.dialog.noTeacher"),
          length: entry.length,
          class: group?.name ?? "",
        })}
        className="w-[min(480px,calc(100vw-32px))]"
        footer={
          <>
            <Button
              variant="outline"
              disabled={entry.locked || pending}
              onClick={() => then({ kind: "remove", entry: entry.id })}
            >
              {t("timetable.editor.dialog.remove")}
            </Button>
            <DialogClose asChild>
              <Button variant="outline">{t("timetable.editor.dialog.close")}</Button>
            </DialogClose>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {entry.locked && <Banner tone="info">{t("timetable.editor.dialog.lockedNote")}</Banner>}
          <PositionPicker
            board={board}
            placed={placed}
            course={course}
            length={entry.length}
            room={entry.room ?? null}
            ignore={[entry.id]}
            initialDay={entry.weekday}
            label={t("timetable.editor.dialog.moveTo")}
            button={t("timetable.editor.dialog.move")}
            disabled={entry.locked || pending}
            onPick={(weekday, first) => then({ kind: "move", entry: entry.id, weekday, first })}
          />
          <div className="flex flex-col gap-2">
            <b className="text-sm">{t("timetable.editor.dialog.swapWith")}</b>
            {others.length ? (
              <div className="flex flex-wrap gap-2">
                <Select
                  aria-label={t("timetable.editor.dialog.swapWith")}
                  className="w-auto min-w-0 flex-1"
                  value={swapWith?.id ?? ""}
                  disabled={entry.locked || pending}
                  onChange={(event) => setOther(event.target.value)}
                >
                  {others.map((item) => (
                    <option key={item.id} value={item.id}>
                      {t("timetable.editor.dialog.swapOption", {
                        course: board.courses.get(item.course)?.name ?? "",
                        ...where(item),
                      })}
                    </option>
                  ))}
                </Select>
                <Button
                  variant="outline"
                  disabled={entry.locked || pending || !swapWith}
                  onClick={() =>
                    swapWith && then({ kind: "swap", entry: entry.id, other: swapWith.id })
                  }
                >
                  {t("timetable.editor.dialog.swap")}
                </Button>
              </div>
            ) : (
              <p className="text-sm text-ink-3">{t("timetable.editor.dialog.swapNone")}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <b className="text-sm">{t("timetable.editor.dialog.room")}</b>
            <Select
              aria-label={t("timetable.editor.dialog.room")}
              value={entry.room ?? ""}
              disabled={entry.locked || pending}
              onChange={(event) =>
                void onGesture({
                  kind: "room",
                  entry: entry.id,
                  room: event.target.value || null,
                }).catch(() => undefined)
              }
            >
              <option value="">{t("timetable.editor.dialog.roomNone")}</option>
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  {room.name}
                </option>
              ))}
            </Select>
          </div>
          <label className="flex items-center justify-between gap-3 text-sm">
            <span>{t("timetable.editor.dialog.lock")}</span>
            <Switch
              checked={entry.locked}
              disabled={pending}
              onCheckedChange={(locked) =>
                void onGesture({ kind: "lock", entry: entry.id, locked }).catch(() => undefined)
              }
            />
          </label>
        </div>
      </DialogContent>
    </DialogRoot>
  );
}

export function PlaceDialog({
  course,
  length,
  ...common
}: Common & { course: EditorCourse; length: number }) {
  const { t } = useTranslation();
  const { board, placed, pending, onGesture, onClose } = common;
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("timetable.editor.dialog.placeTitle", { course: course.name, length })}
        description={t("timetable.editor.dialog.placeSubtitle", {
          teacher: course.teacher_name || t("timetable.editor.dialog.noTeacher"),
          class: board.classes.get(course.class_group)?.name ?? "",
        })}
        className="w-[min(480px,calc(100vw-32px))]"
        footer={
          <DialogClose asChild>
            <Button variant="outline">{t("timetable.editor.dialog.close")}</Button>
          </DialogClose>
        }
      >
        <PositionPicker
          board={board}
          placed={placed}
          course={course}
          length={length}
          room={defaultRoom(board, course)}
          ignore={[]}
          label={t("timetable.editor.dialog.moveTo")}
          button={t("timetable.editor.dialog.placeButton")}
          disabled={pending}
          onPick={(weekday, first) =>
            void onGesture({ kind: "place", course: course.id, weekday, first, length }).then(
              onClose,
              () => undefined,
            )
          }
        />
      </DialogContent>
    </DialogRoot>
  );
}
