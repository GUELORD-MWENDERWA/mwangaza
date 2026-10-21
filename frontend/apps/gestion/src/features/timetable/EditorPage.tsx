// Emploi du temps : éditeur d'un brouillon, vue par classe (EDT.2a, maquette
// `emploi-du-temps-classe`). Un geste (placer, déplacer, échanger, salle, verrou, retirer, annuler)
// = une requête ; le serveur renvoie l'état du brouillon avec ses conflits recalculés. Pendant le
// choix d'une heure (glisser, ou toucher une séance « À placer »), les cases se teintent d'après
// les séances déjà chargées. Ordinateur : la semaine en grille ; téléphone : un jour à la fois.
// Droit `timetable.manage`, en ligne seulement.
import { api, call } from "@mwangaza/api";
import { type TFunction, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Icon,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StateCard,
  StatusPill,
  Tabs,
  TabsList,
  TabsTrigger,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type DragEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { errorMessage } from "../../lib/errors";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import {
  type DraftState,
  draftKey,
  draftListKey,
  sendGesture,
  useDraft,
  useDrafts,
  useGrids,
  useRooms,
  useTimetableClasses,
  useTimetableCourses,
} from "./data";
import {
  type Board,
  type Days,
  type EditorCourse,
  type Entry,
  type Gesture,
  type Issue,
  type Placed,
  type Tint,
  boardOf,
  colorOf,
  defaultRoom,
  entriesOf,
  lanesOf,
  placedOf,
  rowsOf,
  tint,
} from "./editor";
import { EntryDialog, PlaceDialog } from "./EntryDialog";
import { dayName, hoursText } from "./rules";

/** Ce qu'on est en train de placer : une séance « À placer », ou une séance qu'on glisse. */
type Pick = { course: EditorCourse; length: number; entry?: string; room: string | null };

const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** « Lun », « Mar »… (1er janvier 2024 = un lundi). */
const shortDay = (weekday: number, language: string) =>
  capitalized(
    new Intl.DateTimeFormat(language, { weekday: "short", timeZone: "UTC" }).format(
      new Date(Date.UTC(2024, 0, weekday)),
    ),
  );

export function EditorPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const years = useYears();
  const drafts = useDrafts();
  const courses = useTimetableCourses();
  const classes = useTimetableClasses();
  const grids = useGrids();
  const rooms = useRooms();
  const draftId = params.get("draft") ?? drafts.data?.[0]?.id;
  const draft = useDraft(draftId);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [opened, setOpened] = useState<{ entry: string } | { course: string; length: number }>();
  const [picked, setPicked] = useState<Pick | null>(null);
  const [day, setDay] = useState<number | null>(null);

  const board = useMemo(
    () => boardOf(courses.data ?? [], classes.data ?? [], grids.data ?? [], rooms.data ?? []),
    [courses.data, classes.data, grids.data, rooms.data],
  );
  const state = draft.data;
  const placed = useMemo(() => placedOf(board, state?.entries ?? []), [board, state]);

  const gesture = useMutation({
    mutationFn: (item: Gesture) => sendGesture(draftId ?? "", item),
    onSuccess: (next: DraftState) => {
      queryClient.setQueryData(draftKey(next.id), next);
      void queryClient.invalidateQueries({ queryKey: draftListKey });
    },
  });
  const run = (item: Gesture) => {
    setPicked(null);
    return gesture.mutateAsync(item);
  };
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/timetable/drafts/{id}/", { params: { path: { id: draftId ?? "" } } })),
    onSuccess: async () => {
      setDeleting(false);
      setParams((current) => {
        current.delete("draft");
        return current;
      });
      await queryClient.invalidateQueries({ queryKey: draftListKey });
    },
  });

  const queries = [years, drafts, courses, classes, grids, rooms];
  if (queries.some((query) => query.isPending) || (draftId && draft.isPending)) {
    return <Skeleton label={t("common.loading")} />;
  }
  const failed = [...queries, draft].find((query) => query.isError);
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;
  const year = years.data?.find((item) => item.is_current);
  const header = (actions?: React.ReactNode) => (
    <PageHeader
      title={t("timetable.editor.title")}
      subtitle={t("timetable.editor.subtitle", { year: year?.name ?? "—" })}
      actions={actions}
    />
  );
  const createDialog = creating && (
    <CreateDraftDialog
      drafts={drafts.data ?? []}
      onClose={() => setCreating(false)}
      onCreated={(created) => {
        queryClient.setQueryData(draftKey(created.id), created);
        void queryClient.invalidateQueries({ queryKey: draftListKey });
        setCreating(false);
        setParams((current) => {
          current.set("draft", created.id);
          return current;
        });
      }}
    />
  );
  if (!year || !grids.data?.length || !classes.data?.length) {
    const message = !year
      ? "timetable.editor.noYear"
      : !grids.data?.length
        ? "timetable.editor.noGrid"
        : "timetable.editor.noClass";
    return (
      <>
        {header()}
        <Banner tone="warn">
          {t(message)}{" "}
          {year && !grids.data?.length && (
            <Link to="/time-grid" className="font-bold underline">
              {t("shell.menu.timeGrid")}
            </Link>
          )}
        </Banner>
      </>
    );
  }
  if (!state) {
    return (
      <>
        {header()}
        <StateCard
          icon="calendar"
          tone="lake"
          title={t("timetable.editor.emptyTitle")}
          actions={
            <Button onClick={() => setCreating(true)}>{t("timetable.editor.createFirst")}</Button>
          }
        >
          {t("timetable.editor.emptyText")}
        </StateCard>
        {createDialog}
      </>
    );
  }

  const classList = classes.data;
  const classId =
    classList.find((row) => row.id === params.get("class"))?.id ?? classList[0]?.id ?? "";
  const position = classList.findIndex((row) => row.id === classId);
  const klass = classList[position];
  const showClass = (id: string | undefined) =>
    id &&
    setParams((current) => {
      current.set("class", id);
      return current;
    });
  const days = board.daysOfClass(classId);
  const weekdays = [...days.keys()];
  const shownDay = day && days.has(day) ? day : weekdays[0];
  const classOf = (entryId: string) => {
    const entry = state.entries.find((item) => item.id === entryId);
    return entry ? board.courses.get(entry.course)?.class_group : undefined;
  };
  const issues = state.issues.filter(
    (issue) =>
      issue.class_group === classId || entriesOf(issue).some((id) => classOf(id) === classId),
  );
  const marks = new Map<string, Issue>();
  for (const issue of state.issues) {
    for (const id of entriesOf(issue)) {
      const known = marks.get(id);
      if (!known || (known.level === "warning" && issue.level === "error")) marks.set(id, issue);
    }
  }
  const mine = state.entries.filter(
    (entry) => board.courses.get(entry.course)?.class_group === classId,
  );
  const load = state.classes.find((row) => row.class_group === classId);
  const left = state.left.flatMap((row) => {
    const course = board.courses.get(row.course);
    return course && course.class_group === classId
      ? row.lengths.map((length, index) => ({ course, length, key: `${row.course}-${index}` }))
      : [];
  });
  const errors = issues.filter((issue) => issue.level === "error").length;
  const open =
    opened && "entry" in opened
      ? state.entries.find((item) => item.id === opened.entry)
      : undefined;
  const placing = opened && "course" in opened ? board.courses.get(opened.course) : undefined;
  const dropAt = (weekday: number, first: number) => {
    if (!picked) return;
    void run(
      picked.entry
        ? { kind: "move", entry: picked.entry, weekday, first }
        : { kind: "place", course: picked.course.id, weekday, first, length: picked.length },
    ).catch(() => undefined);
  };
  const dropOn = (entry: Entry) => {
    if (picked?.entry && picked.entry !== entry.id && !entry.locked) {
      void run({ kind: "swap", entry: picked.entry, other: entry.id }).catch(() => undefined);
    }
  };
  const pickEntry = (entry: Entry) => {
    const course = board.courses.get(entry.course);
    if (course && !entry.locked) {
      setPicked({ course, length: entry.length, entry: entry.id, room: entry.room ?? null });
    }
  };
  const common = {
    board,
    placed,
    pending: gesture.isPending,
    onGesture: run,
    onClose: () => setOpened(undefined),
  };

  return (
    <>
      {header(
        <>
          <Select
            aria-label={t("timetable.editor.draft")}
            className="w-full min-w-0 sm:w-auto"
            value={state.id}
            onChange={(event) =>
              setParams((current) => {
                current.set("draft", event.target.value);
                return current;
              })
            }
          >
            {(drafts.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
          <Button
            variant="outline"
            disabled={!state.can_undo || gesture.isPending}
            onClick={() => void run({ kind: "undo" }).catch(() => undefined)}
          >
            {t("timetable.editor.undo")}
          </Button>
          <Button variant="outline" onClick={() => setDeleting(true)}>
            {t("timetable.editor.deleteDraft")}
          </Button>
          <Button onClick={() => setCreating(true)}>{t("timetable.editor.newDraft")}</Button>
        </>,
      )}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
            <Button
              variant="outline"
              aria-label={t("timetable.editor.previous")}
              disabled={position <= 0}
              onClick={() => showClass(classList[position - 1]?.id)}
            >
              <Icon name="back" />
            </Button>
            <Select
              aria-label={t("timetable.editor.class")}
              className="w-auto min-w-0 flex-1 font-bold"
              value={classId}
              onChange={(event) => showClass(event.target.value)}
            >
              {classList.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </Select>
            <Button
              variant="outline"
              aria-label={t("timetable.editor.next")}
              disabled={position >= classList.length - 1}
              onClick={() => showClass(classList[position + 1]?.id)}
            >
              <Icon name="chevron" />
            </Button>
          </div>
          {load && (
            <StatusPill tone="info">
              {t("timetable.editor.placedOfDue", { placed: load.placed, due: load.due })}
            </StatusPill>
          )}
          <StatusPill tone={errors ? "due" : "ok"}>
            {errors
              ? t("timetable.editor.conflicts", { count: errors })
              : t("timetable.editor.noConflict")}
          </StatusPill>
        </div>
        <Button asChild variant="outline">
          <Link to="/timetable-checks">{t("timetable.editor.rulesLink")}</Link>
        </Button>
      </div>
      {gesture.isError && (
        <Banner tone="due" className="mb-4">
          {errorMessage(gesture.error, t)}
        </Banner>
      )}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="hidden md:block">
          <CardHeader className="flex-wrap">
            <CardTitle>{t("timetable.editor.weekTitle", { name: klass?.name ?? "" })}</CardTitle>
            {picked && (
              <div className="flex flex-wrap items-center gap-2 text-sm text-ink-3">
                <span>
                  {t("timetable.editor.picked", {
                    course: picked.course.name,
                    length: picked.length,
                  })}
                </span>
                <Button variant="outline" size="sm" onClick={() => setPicked(null)}>
                  {t("timetable.editor.cancelPick")}
                </Button>
              </div>
            )}
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <WeekGrid
              board={board}
              placed={placed}
              days={days}
              entries={mine}
              marks={marks}
              picked={picked}
              onOpen={(entry) => setOpened({ entry: entry.id })}
              onPick={pickEntry}
              onUnpick={() => setPicked(null)}
              onDropAt={dropAt}
              onDropOn={dropOn}
            />
            <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-3">
              <span>{t("timetable.editor.hint")}</span>
              <span>{t("timetable.editor.lockHint")}</span>
            </p>
          </CardContent>
        </Card>
        <Card className="md:hidden">
          <CardHeader>
            <CardTitle>{klass?.name}</CardTitle>
            {load && (
              <StatusPill tone="info">
                {t("timetable.editor.placedOfDue", { placed: load.placed, due: load.due })}
              </StatusPill>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Tabs value={String(shownDay)} onValueChange={(value) => setDay(Number(value))}>
              <TabsList aria-label={t("timetable.editor.days")}>
                {weekdays.map((weekday) => (
                  <TabsTrigger key={weekday} value={String(weekday)} className="px-2">
                    {shortDay(weekday, i18n.language)}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            {shownDay !== undefined && (
              <DayList
                board={board}
                days={days}
                weekday={shownDay}
                entries={mine}
                marks={marks}
                onOpen={(entry) => setOpened({ entry: entry.id })}
              />
            )}
            <p className="text-sm text-ink-3">{t("timetable.editor.dayHint")}</p>
          </CardContent>
        </Card>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>
                {t("timetable.editor.leftTitle", {
                  count: left.reduce((sum, item) => sum + item.length, 0),
                })}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {left.length === 0 && (
                <p className="text-sm text-ink-3">{t("timetable.editor.leftNone")}</p>
              )}
              {left.map((item) => {
                const on =
                  picked &&
                  !picked.entry &&
                  picked.course.id === item.course.id &&
                  picked.length === item.length;
                return (
                  <div
                    key={item.key}
                    className={cn(
                      "flex items-center gap-2 rounded-lg border border-line border-l-4 bg-card px-3 py-2",
                      on && "ring-2 ring-lake",
                    )}
                    style={{ borderLeftColor: colorOf(item.course.name) }}
                  >
                    <button
                      type="button"
                      draggable
                      className="min-w-0 flex-1 cursor-grab text-left"
                      aria-label={t("timetable.editor.pick", {
                        course: item.course.name,
                        length: item.length,
                      })}
                      aria-pressed={Boolean(on)}
                      onClick={() =>
                        setPicked(
                          on
                            ? null
                            : {
                                course: item.course,
                                length: item.length,
                                room: defaultRoom(board, item.course),
                              },
                        )
                      }
                      onDragStart={(event) => {
                        event.dataTransfer.setData("text/plain", item.course.id);
                        setPicked({
                          course: item.course,
                          length: item.length,
                          room: defaultRoom(board, item.course),
                        });
                      }}
                    >
                      <b className="block text-sm">
                        {item.course.name} · {item.length} h
                      </b>
                      <span className="block truncate text-sm text-ink-3">
                        {item.course.teacher_name}
                      </span>
                    </button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setOpened({ course: item.course.id, length: item.length })}
                    >
                      {t("timetable.editor.place")}
                    </Button>
                  </div>
                );
              })}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-wrap">
              <CardTitle>
                {t("timetable.editor.conflictsTitle", { count: issues.length })}
              </CardTitle>
              <span className="text-sm text-ink-3">
                {t("timetable.editor.conflictsAll", { count: state.issues.length })}
              </span>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {issues.length === 0 && (
                <p className="text-sm text-ink-3">{t("timetable.editor.noConflict")}</p>
              )}
              {issues.map((issue, index) => (
                <div key={`${issue.code}-${index}`} className="flex items-start gap-2 text-sm">
                  <StatusPill tone={issue.level === "error" ? "due" : "warn"} className="shrink-0">
                    {t(`timetable.checks.level.${issue.level}`)}
                  </StatusPill>
                  <span className="min-w-0">
                    <b>{issue.subject}</b> · <IssueText issue={issue} />
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("timetable.editor.perDay")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
              {weekdays.map((weekday) => {
                const lessons = (days.get(weekday) ?? []).filter(
                  (slot) => slot.kind === "lesson",
                ).length;
                const hours = new Set(
                  mine
                    .filter((entry) => entry.weekday === weekday)
                    .flatMap((entry) =>
                      Array.from({ length: entry.length }, (_, k) => entry.first + k),
                    ),
                ).size;
                return (
                  <span key={weekday}>
                    <b>{shortDay(weekday, i18n.language)}</b>{" "}
                    {t("timetable.editor.dayLoad", { placed: hours, lessons })}
                  </span>
                );
              })}
            </CardContent>
          </Card>
        </div>
      </div>
      {open && <EntryDialog entry={open} entries={state.entries} {...common} />}
      {placing && opened && "length" in opened && (
        <PlaceDialog course={placing} length={opened.length} {...common} />
      )}
      {createDialog}
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t("timetable.editor.deleteTitle", { name: state.name })}
        confirmLabel={t("timetable.editor.deleteDraft")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      >
        {t("timetable.editor.deleteText")}
      </ConfirmDialog>
    </>
  );
}

/** Phrase d'un conflit, avec le jour, les heures et le type de règle ou de salle en mots. */
function IssueText({ issue }: { issue: Issue }) {
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
};

/** La semaine d'une classe : jours en colonnes, heures et récréations en lignes ; une séance
 *  couvre ses heures (et la récréation qu'elle passe) ; deux séances en même temps se partagent
 *  la largeur. */
function WeekGrid(props: GridProps) {
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
  board,
  onDragOver,
  onDrop,
  onClick,
}: {
  style: React.CSSProperties;
  shade: Tint | null;
  board: Board;
  onDragOver: (event: DragEvent) => void;
  onDrop: () => void;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  const text = !shade
    ? t("timetable.editor.free")
    : shade.kind === "fits"
      ? t("timetable.editor.tint.fits")
      : shade.kind === "short"
        ? t("timetable.editor.tint.short")
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
        shade?.kind === "fits" &&
          "cursor-pointer border-solid border-ok-200 bg-ok-50 font-semibold text-ok",
        shade?.kind === "conflict" &&
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

/** Une séance placée : cours, enseignant, salle, couleur du cours, cadenas, conflit. */
function Lesson({
  board,
  entry,
  mark,
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
  const details = [course?.teacher_name, room].filter(Boolean).join(" · ");
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

/** Une journée d'une classe, au téléphone : chaque heure (ou suite d'heures) dans l'ordre. */
function DayList({
  board,
  days,
  weekday,
  entries,
  marks,
  onOpen,
}: {
  board: Board;
  days: Days;
  weekday: number;
  entries: Entry[];
  marks: Map<string, Issue>;
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
    if (index <= until) continue;
    const starting = mine.filter((entry) => entry.first === index);
    const last = Math.max(index, ...starting.map((entry) => entry.first + entry.length - 1));
    until = starting.length ? last : until;
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
                onOpen={() => onOpen(entry)}
              />
            ))
          ) : (
            <div className="min-h-14 rounded-lg border border-dashed border-line p-2 text-xs text-ink-3">
              {t("timetable.editor.free")}
            </div>
          )}
        </div>
      </div>,
    );
  }
  return <div className="flex flex-col gap-2">{items}</div>;
}

/** Nouveau brouillon : un nom, puis les verrous des règles ou la copie d'un brouillon. */
function CreateDraftDialog({
  drafts,
  onClose,
  onCreated,
}: {
  drafts: { id: string; name: string }[];
  onClose: () => void;
  onCreated: (state: DraftState) => void;
}) {
  const { t, i18n } = useTranslation();
  const today = new Intl.DateTimeFormat(i18n.language, { day: "numeric", month: "long" }).format(
    new Date(),
  );
  const [name, setName] = useState(t("timetable.editor.create.nameDefault", { date: today }));
  const [from, setFrom] = useState("");
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/drafts/", { body: { name: name.trim(), based_on: from || null } }),
      ),
    onSuccess: onCreated,
  });
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("timetable.editor.create.title")}
        className="w-[min(440px,calc(100vw-32px))]"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
              {t("timetable.editor.create.create")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          {create.isError && <Banner tone="due">{errorMessage(create.error, t)}</Banner>}
          <Field id="draft-name" label={t("timetable.editor.create.name")}>
            {(control) => (
              <Input
                {...control}
                maxLength={80}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            )}
          </Field>
          <Field id="draft-from" label={t("timetable.editor.create.from")}>
            {(control) => (
              <Select {...control} value={from} onChange={(event) => setFrom(event.target.value)}>
                <option value="">{t("timetable.editor.create.fromLocks")}</option>
                {drafts.map((item) => (
                  <option key={item.id} value={item.id}>
                    {t("timetable.editor.create.fromDraft", { name: item.name })}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
