// Emploi du temps : éditeur d'un brouillon (EDT.2a, EDT.2b, maquettes `emploi-du-temps-classe`,
// `-enseignant`, `-general`). Vues par classe, par enseignant, par salle et horaire général, sur
// les mêmes données. Un geste (placer, déplacer, échanger, salle, verrou, retirer, annuler) = une
// requête ; le serveur renvoie l'état du brouillon avec ses conflits recalculés. Pendant le choix
// d'une heure (glisser, ou toucher une séance « À placer »), les cases se teintent d'après les
// séances déjà chargées. Ordinateur : la semaine en grille ; téléphone : un jour à la fois.
// Droit `timetable.manage`, en ligne seulement.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
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
import { useMemo, useState } from "react";
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
  useTeacherProfiles,
  useTimetableClasses,
  useTimetableCourses,
} from "./data";
import {
  type Entry,
  type Gesture,
  type Issue,
  type View,
  boardOf,
  colorOf,
  defaultRoom,
  entriesOf,
  focusOf,
  hoursOf,
  placedOf,
  shortNames,
} from "./editor";
import { DayList, IssueText, type Pick, WeekGrid, capitalized } from "./EditorParts";
import { EntryDialog, PlaceDialog } from "./EntryDialog";
import { GeneralView } from "./GeneralView";

/** Textes propres à chaque vue (sélecteur, précédent, suivant, rien à placer). */
const VIEW_TEXT = {
  class: {
    select: "timetable.editor.class",
    previous: "timetable.editor.previous",
    next: "timetable.editor.next",
    none: "timetable.editor.leftNone",
    empty: "timetable.editor.empty.class",
  },
  teacher: {
    select: "timetable.editor.teacher",
    previous: "timetable.editor.previousTeacher",
    next: "timetable.editor.nextTeacher",
    none: "timetable.editor.leftNoneTeacher",
    empty: "timetable.editor.empty.teacher",
  },
  room: {
    select: "timetable.editor.room",
    previous: "timetable.editor.previousRoom",
    next: "timetable.editor.nextRoom",
    none: "timetable.editor.leftNoneRoom",
    empty: "timetable.editor.empty.room",
  },
} as const;

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
  const profiles = useTeacherProfiles();
  const draftId = params.get("draft") ?? drafts.data?.[0]?.id;
  const draft = useDraft(draftId);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [opened, setOpened] = useState<{ entry: string } | { course: string; length: number }>();
  const [picked, setPicked] = useState<Pick | null>(null);
  const [day, setDay] = useState<number | null>(null);

  const board = useMemo(
    () =>
      boardOf(
        courses.data ?? [],
        classes.data ?? [],
        grids.data ?? [],
        rooms.data ?? [],
        profiles.data ?? [],
      ),
    [courses.data, classes.data, grids.data, rooms.data, profiles.data],
  );
  const codes = useMemo(() => shortNames(courses.data ?? []), [courses.data]);
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

  const queries = [years, drafts, courses, classes, grids, rooms, profiles];
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

  const view: View | "all" =
    params.get("view") === "teacher" ||
    params.get("view") === "room" ||
    params.get("view") === "all"
      ? (params.get("view") as View | "all")
      : "class";
  const kind: View = view === "all" ? "class" : view;
  const lists: Record<View, { id: string; name: string }[]> = {
    class: classes.data,
    teacher: state.teachers.map((row) => ({ id: row.teacher, name: row.name })),
    room: (rooms.data ?? [])
      .filter((room) => room.is_active)
      .sort((a, b) => a.name.localeCompare(b.name, i18n.language, { numeric: true })),
  };
  const list = lists[kind];
  const selectedId = list.find((row) => row.id === params.get(kind))?.id ?? list[0]?.id ?? "";
  const position = list.findIndex((row) => row.id === selectedId);
  const selected = list[position];
  const show = (next: View | "all", id?: string) =>
    setParams((current) => {
      if (next === "class") current.delete("view");
      else current.set("view", next);
      if (id && next !== "all") current.set(next, id);
      return current;
    });
  const focus = focusOf(board, state, kind, selectedId);
  const { days, entries: mine, left, issues } = focus;
  const weekdays = [...days.keys()];
  const shownDay = day && days.has(day) ? day : weekdays[0];
  const absences = kind === "teacher" ? board.absences.get(selectedId) : undefined;
  const marks = new Map<string, Issue>();
  for (const issue of state.issues) {
    for (const id of entriesOf(issue)) {
      const known = marks.get(id);
      if (!known || (known.level === "warning" && issue.level === "error")) marks.set(id, issue);
    }
  }
  const classLoad = state.classes.find((row) => row.class_group === selectedId);
  const teacherLoad = state.teachers.find((row) => row.teacher === selectedId);
  const over = Boolean(teacherLoad?.max && teacherLoad.placed > teacherLoad.max);
  const loadText =
    view === "all"
      ? t("timetable.editor.allLoad", {
          count: state.classes.length,
          placed: state.classes.reduce((sum, row) => sum + row.placed, 0),
          due: state.classes.reduce((sum, row) => sum + row.due, 0),
        })
      : kind === "room"
        ? t("timetable.editor.roomLoad", { count: hoursOf(mine) })
        : kind === "teacher" && teacherLoad
          ? [
              t("timetable.editor.placedOfDue", teacherLoad),
              teacherLoad.max ? t("timetable.editor.atMost", { max: teacherLoad.max }) : "",
            ]
              .filter(Boolean)
              .join(" · ")
          : classLoad
            ? t("timetable.editor.placedOfDue", classLoad)
            : "";
  const errors =
    view === "all" ? state.errors : issues.filter((issue) => issue.level === "error").length;
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
      <div className="mb-4 flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs value={view} onValueChange={(value) => show(value as View | "all")}>
            <TabsList aria-label={t("timetable.editor.views.label")}>
              {(["class", "teacher", "room", "all"] as const).map((item) => (
                <TabsTrigger key={item} value={item} className="px-2.5">
                  {t(`timetable.editor.views.${item}`)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <Button asChild variant="outline">
            <Link to="/timetable-checks">{t("timetable.editor.rulesLink")}</Link>
          </Button>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {view !== "all" && (
            <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
              <Button
                variant="outline"
                aria-label={t(VIEW_TEXT[kind].previous)}
                disabled={position <= 0}
                onClick={() => show(kind, list[position - 1]?.id)}
              >
                <Icon name="back" />
              </Button>
              <Select
                aria-label={t(VIEW_TEXT[kind].select)}
                className="w-auto min-w-0 flex-1 font-bold"
                value={selectedId}
                onChange={(event) => show(kind, event.target.value)}
              >
                {list.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </Select>
              <Button
                variant="outline"
                aria-label={t(VIEW_TEXT[kind].next)}
                disabled={position >= list.length - 1}
                onClick={() => show(kind, list[position + 1]?.id)}
              >
                <Icon name="chevron" />
              </Button>
            </div>
          )}
          {loadText && <StatusPill tone={over ? "due" : "info"}>{loadText}</StatusPill>}
          <StatusPill tone={errors ? "due" : "ok"}>
            {errors
              ? t("timetable.editor.conflicts", { count: errors })
              : t("timetable.editor.noConflict")}
          </StatusPill>
        </div>
      </div>
      {gesture.isError && (
        <Banner tone="due" className="mb-4">
          {errorMessage(gesture.error, t)}
        </Banner>
      )}
      {view === "all" ? (
        <div className="flex flex-col gap-4">
          {[true, false].map((week) => (
            <div key={String(week)} className={week ? "hidden md:block" : "md:hidden"}>
              <GeneralView
                board={board}
                placed={placed}
                state={state}
                marks={marks}
                picked={picked}
                codes={codes}
                week={week}
                onOpen={(entry) => setOpened({ entry: entry.id })}
                onPick={pickEntry}
                onUnpick={() => setPicked(null)}
                onDropAt={dropAt}
                onDropOn={dropOn}
                onShowClass={(id) => show("class", id)}
              />
            </div>
          ))}
          <IssuesCard issues={state.issues} className="max-w-3xl" />
        </div>
      ) : list.length === 0 ? (
        <Banner tone="warn">{t(VIEW_TEXT[kind].empty)}</Banner>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="hidden md:block">
            <CardHeader className="flex-wrap">
              <CardTitle>
                {t("timetable.editor.weekTitle", { name: selected?.name ?? "" })}
              </CardTitle>
              {picked ? (
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
              ) : absences?.length ? (
                <span className="text-sm text-ink-3">{t("timetable.editor.absentHint")}</span>
              ) : null}
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {focus.mixed && (
                <Banner tone="warn" className="mb-3">
                  {t("timetable.editor.mixedGrids")}
                </Banner>
              )}
              <WeekGrid
                board={board}
                placed={placed}
                days={days}
                entries={mine}
                marks={marks}
                picked={picked}
                context={kind}
                absences={absences}
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
              <CardTitle>{selected?.name}</CardTitle>
              {loadText && <StatusPill tone={over ? "due" : "info"}>{loadText}</StatusPill>}
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
              {focus.mixed && <Banner tone="warn">{t("timetable.editor.mixedGrids")}</Banner>}
              {shownDay !== undefined && (
                <DayList
                  board={board}
                  days={days}
                  weekday={shownDay}
                  entries={mine}
                  marks={marks}
                  context={kind}
                  absences={absences}
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
                  <p className="text-sm text-ink-3">{t(VIEW_TEXT[kind].none)}</p>
                )}
                {left.map((item) => {
                  const on =
                    picked &&
                    !picked.entry &&
                    picked.course.id === item.course.id &&
                    picked.length === item.length;
                  const group = board.classes.get(item.course.class_group)?.name;
                  const who = (
                    kind === "class"
                      ? [item.course.teacher_name]
                      : kind === "teacher"
                        ? [group]
                        : [group, item.course.teacher_name]
                  )
                    .filter(Boolean)
                    .join(" · ");
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
                        <span className="block truncate text-sm text-ink-3">{who}</span>
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
            <IssuesCard issues={issues} total={state.issues.length} />
            <Card>
              <CardHeader>
                <CardTitle>{t("timetable.editor.perDay")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
                {weekdays.map((weekday) => (
                  <span key={weekday}>
                    <b>{shortDay(weekday, i18n.language)}</b>{" "}
                    {t("timetable.editor.dayLoad", {
                      placed: hoursOf(mine, weekday),
                      lessons: (days.get(weekday) ?? []).filter((slot) => slot.kind === "lesson")
                        .length,
                    })}
                  </span>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
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

/** Les conflits d'une vue (`total` : ceux de tout le brouillon), en phrases. */
function IssuesCard({
  issues,
  total,
  className,
}: {
  issues: Issue[];
  total?: number;
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <Card className={className}>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("timetable.editor.conflictsTitle", { count: issues.length })}</CardTitle>
        {total !== undefined && (
          <span className="text-sm text-ink-3">
            {t("timetable.editor.conflictsAll", { count: total })}
          </span>
        )}
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
  );
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
