// Grille horaire (EDT.1a, maquette `grille-horaire`) : les grilles de l'école (une par vacation),
// leurs réglages et leur semaine, la grille et la salle habituelle de chaque classe comparées à ses
// heures de cours, et les règles générales de l'emploi du temps. Une case se corrige à la main ;
// la semaine s'enregistre d'un bloc.
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
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Switch,
  Table,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import {
  gapOf,
  useGrids,
  useRooms,
  useTimetableClasses,
  useTimetableRules,
  type ClassRow,
  type Room,
  type Rules,
  type TimeGrid,
} from "./data";
import {
  buildWeek,
  cellKey,
  cellsOf,
  fromSlots,
  lessonCount,
  MAX_LESSONS_PER_DAY,
  rowKeys,
  setDayStart,
  setMinutes,
  shapeOf,
  toClock,
  toMinutes,
  toSlots,
  WEEKDAYS,
  type Cell,
  type Week,
} from "./week";

const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const dayKey = (weekday: number) => DAY_KEYS[weekday - 1] ?? "sun";

export function TimeGridPage() {
  const { t } = useTranslation();
  const grids = useGrids();
  const classes = useTimetableClasses();
  const rooms = useRooms();
  const rules = useTimetableRules();
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const queries = [grids, classes, rooms, rules];
  if (queries.some((query) => query.isPending)) return <Skeleton label={t("common.loading")} />;
  const failed = queries.find((query) => query.isError);
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;
  if (!grids.data || !classes.data || !rooms.data || !rules.data) return null;

  const list = grids.data;
  const current = list.find((grid) => grid.id === selected) ?? list[0];

  return (
    <>
      <PageHeader
        title={t("timetable.gridTitle")}
        subtitle={t("timetable.gridSubtitle")}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/rooms">{t("timetable.roomsLink")}</Link>
            </Button>
            {list.length > 0 && (
              <Button onClick={() => setCreating(true)}>{t("timetable.newGrid")}</Button>
            )}
          </>
        }
      />
      {current ? (
        <div className="flex flex-col gap-4">
          {list.length > 1 && (
            <Tabs value={current.id} onValueChange={setSelected}>
              <TabsList className="max-w-full overflow-x-auto">
                {list.map((grid) => (
                  <TabsTrigger key={grid.id} value={grid.id} className="gap-2">
                    {grid.name}
                    {grid.is_default && (
                      <StatusPill tone="info">{t("timetable.defaultTag")}</StatusPill>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}
          <GridEditor key={current.id} grid={current} onDeleted={() => setSelected(null)} />
        </div>
      ) : (
        <ProposedGrid />
      )}
      <ClassesCard grids={list} rows={classes.data} rooms={rooms.data} />
      <RulesCard rules={rules.data} />
      <NewGridDialog
        open={creating}
        template={list.find((grid) => grid.is_default)}
        onClose={() => setCreating(false)}
        onCreated={(grid) => {
          setCreating(false);
          setSelected(grid.id);
        }}
      />
    </>
  );
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: keys.timetable });
}

function ProposedGrid() {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const create = useMutation({
    mutationFn: () =>
      call(api.POST("/api/timetable/grids/", { body: { name: t("timetable.proposedName") } })),
    onSuccess: refresh,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("timetable.emptyTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-4">
        <p className="text-ink-3">{t("timetable.emptyText")}</p>
        {create.isError && <Banner tone="due">{firstErrorMessage(create.error, t)}</Banner>}
        <Button disabled={create.isPending} onClick={() => create.mutate()}>
          {t("timetable.createProposed")}
        </Button>
      </CardContent>
    </Card>
  );
}

type ShapeDraft = {
  lessonMinutes: string;
  start: string;
  lessons: Record<number, string>;
  breaks: { after: string; minutes: string }[];
};

function draftOf(grid: TimeGrid, week: Week): ShapeDraft {
  const shape = shapeOf(week, grid.lesson_minutes, toMinutes(grid.start_time));
  return {
    lessonMinutes: String(shape.lessonMinutes),
    start: toClock(shape.start),
    lessons: Object.fromEntries(WEEKDAYS.map((day) => [day, String(shape.lessons[day] ?? 0)])),
    breaks: shape.breaks.map((pause) => ({
      after: String(pause.after),
      minutes: String(pause.minutes),
    })),
  };
}

function GridEditor({ grid, onDeleted }: { grid: TimeGrid; onDeleted: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const [week, setWeek] = useState<Week>(() => fromSlots(grid.slots));
  const [name, setName] = useState(grid.name);
  const [isDefault, setIsDefault] = useState(grid.is_default);
  const [shape, setShape] = useState<ShapeDraft>(() => draftOf(grid, fromSlots(grid.slots)));
  const [editing, setEditing] = useState<{ weekday: number; cell: Cell } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [saved, setSaved] = useState(false);
  const changed = () => setSaved(false);

  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/timetable/grids/{id}/", {
          params: { path: { id: grid.id } },
          body: {
            name: name.trim(),
            lesson_minutes: Number(shape.lessonMinutes),
            start_time: shape.start,
            is_default: isDefault,
            slots: toSlots(week),
          },
        }),
      ),
    onSuccess: () => {
      setSaved(true);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/timetable/grids/{id}/", { params: { path: { id: grid.id } } })),
    onSuccess: () => {
      setDeleting(false);
      onDeleted();
      refresh();
    },
  });

  const apply = () => {
    changed();
    setWeek(
      buildWeek({
        lessonMinutes: Number(shape.lessonMinutes),
        start: toMinutes(shape.start),
        lessons: Object.fromEntries(
          Object.entries(shape.lessons).map(([day, count]) => [day, Number(count) || 0]),
        ),
        breaks: shape.breaks
          .filter((pause) => Number(pause.after) > 0 && Number(pause.minutes) > 0)
          .map((pause) => ({ after: Number(pause.after), minutes: Number(pause.minutes) })),
      }),
    );
  };
  const setBreak = (at: number, field: "after" | "minutes", value: string) =>
    setShape({
      ...shape,
      breaks: shape.breaks.map((pause, index) =>
        index === at ? { ...pause, [field]: value } : pause,
      ),
    });

  const days = WEEKDAYS.filter((day) => week[day]);
  const rows = rowKeys(week);
  const label = (key: string) => {
    const number = Number(key.slice(1));
    if (key.startsWith("B")) return t("timetable.break");
    return number === 1 ? t("timetable.lessonFirst") : t("timetable.lessonN", { n: number });
  };
  const cellAt = (weekday: number, key: string) => {
    const day = week[weekday];
    return day ? cellsOf(day).find((cell) => cellKey(day, cell) === key) : undefined;
  };
  const timeButton = (weekday: number, cell: Cell) => (
    <button
      type="button"
      className="whitespace-nowrap rounded-md px-1 py-0.5 text-left tabular-nums hover:bg-surface focus-visible:outline-2 focus-visible:outline-lake"
      onClick={() => setEditing({ weekday, cell })}
    >
      {toClock(cell.start)} – {toClock(cell.end)}
    </button>
  );

  return (
    <div className="grid items-start gap-4 min-[1200px]:grid-cols-[300px_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>{t("timetable.settings")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field id="grid-name" label={t("timetable.name")} required>
            {(control) => (
              <Input
                {...control}
                maxLength={60}
                value={name}
                onChange={(event) => {
                  changed();
                  setName(event.target.value);
                }}
              />
            )}
          </Field>
          <div className="grid grid-cols-2 items-end gap-3">
            <Field id="grid-minutes" label={t("timetable.lessonMinutes")}>
              {(control) => (
                <Input
                  {...control}
                  type="number"
                  min={30}
                  max={90}
                  inputMode="numeric"
                  value={shape.lessonMinutes}
                  onChange={(event) => setShape({ ...shape, lessonMinutes: event.target.value })}
                />
              )}
            </Field>
            <Field id="grid-start" label={t("timetable.start")}>
              {(control) => (
                <Input
                  {...control}
                  type="time"
                  value={shape.start}
                  onChange={(event) => setShape({ ...shape, start: event.target.value })}
                />
              )}
            </Field>
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-semibold">{t("timetable.lessonsPerDay")}</legend>
            <div className="grid grid-cols-7 gap-1.5 min-[1200px]:grid-cols-4">
              {WEEKDAYS.map((day) => (
                <label key={day} className="flex flex-col items-center gap-1 text-xs text-ink-3">
                  {t(`timetable.daysShort.${dayKey(day)}`)}
                  <Input
                    className="px-1 text-center"
                    type="number"
                    min={0}
                    max={MAX_LESSONS_PER_DAY}
                    inputMode="numeric"
                    value={shape.lessons[day]}
                    onChange={(event) =>
                      setShape({
                        ...shape,
                        lessons: { ...shape.lessons, [day]: event.target.value },
                      })
                    }
                  />
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-semibold">{t("timetable.breaks")}</legend>
            {shape.breaks.map((pause, at) => (
              <div key={at} className="flex items-end gap-2">
                <label className="flex flex-1 flex-col gap-1 text-xs text-ink-3">
                  {t("timetable.breakAfter")}
                  <Input
                    type="number"
                    min={1}
                    max={MAX_LESSONS_PER_DAY}
                    inputMode="numeric"
                    value={pause.after}
                    onChange={(event) => setBreak(at, "after", event.target.value)}
                  />
                </label>
                <label className="flex flex-1 flex-col gap-1 text-xs text-ink-3">
                  {t("timetable.breakMinutes")}
                  <Input
                    type="number"
                    min={5}
                    max={240}
                    inputMode="numeric"
                    value={pause.minutes}
                    onChange={(event) => setBreak(at, "minutes", event.target.value)}
                  />
                </label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setShape({ ...shape, breaks: shape.breaks.filter((_, index) => index !== at) })
                  }
                >
                  {t("timetable.removeBreak")}
                </Button>
              </div>
            ))}
            <Button
              variant="outline"
              onClick={() =>
                setShape({ ...shape, breaks: [...shape.breaks, { after: "", minutes: "15" }] })
              }
            >
              {t("timetable.addBreak")}
            </Button>
          </fieldset>
          <div className="flex items-center justify-between gap-3">
            <label htmlFor="grid-default" className="text-sm">
              {t("timetable.isDefault")}
            </label>
            <Switch
              id="grid-default"
              checked={isDefault}
              disabled={grid.is_default}
              onCheckedChange={(on) => {
                changed();
                setIsDefault(on);
              }}
            />
          </div>
          <p className="text-sm text-ink-3">{t("timetable.defaultHelp")}</p>
          <Button variant="outline" onClick={apply}>
            {t("timetable.apply")}
          </Button>
          <p className="text-sm text-ink-3">{t("timetable.applyHelp")}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3">
          <CardTitle>{t("timetable.week")}</CardTitle>
          <StatusPill tone="ok">
            {t("timetable.lessonCount", { count: lessonCount(week) })}
          </StatusPill>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {days.length === 0 ? (
            <p className="text-ink-3">{t("timetable.noDay")}</p>
          ) : (
            <>
              <div className="hidden overflow-x-auto lg:block">
                <Table className="text-sm [&_td]:px-2 [&_td]:py-2 [&_th]:px-2">
                  <thead>
                    <tr>
                      <th />
                      {days.map((day) => (
                        <th key={day}>{t(`timetable.days.${dayKey(day)}`)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((key) => (
                      <tr key={key} className={key.startsWith("B") ? "bg-surface text-ink-3" : ""}>
                        <td className="whitespace-nowrap font-semibold">{label(key)}</td>
                        {days.map((day) => {
                          const cell = cellAt(day, key);
                          return (
                            <td key={day}>
                              {cell ? timeButton(day, cell) : <span className="text-ink-3">—</span>}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
              <Tabs defaultValue={String(days[0])} className="lg:hidden">
                <TabsList className="w-full max-w-full overflow-x-auto">
                  {days.map((day) => (
                    <TabsTrigger key={day} value={String(day)} className="flex-1 px-1">
                      {t(`timetable.daysShort.${dayKey(day)}`)}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {days.map((day) => {
                  const current = week[day];
                  return (
                    <TabsContent key={day} value={String(day)}>
                      <ul className="flex flex-col divide-y divide-line">
                        {current &&
                          cellsOf(current).map((cell) => (
                            <li
                              key={cell.position}
                              className={`flex items-center justify-between gap-3 py-2 ${cell.kind === "break" ? "text-ink-3" : ""}`}
                            >
                              <span className="font-semibold">{label(cellKey(current, cell))}</span>
                              {timeButton(day, cell)}
                            </li>
                          ))}
                      </ul>
                    </TabsContent>
                  );
                })}
              </Tabs>
            </>
          )}
          <p className="text-sm text-ink-3">{t("timetable.weekHelp")}</p>
          {saved && <Banner tone="ok">{t("timetable.saved")}</Banner>}
          {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
          <div className="flex flex-wrap justify-end gap-2">
            {!grid.is_default && (
              <Button variant="outline" onClick={() => setDeleting(true)}>
                {t("timetable.delete")}
              </Button>
            )}
            <Button disabled={save.isPending || name.trim() === ""} onClick={() => save.mutate()}>
              {t("timetable.save")}
            </Button>
          </div>
        </CardContent>
      </Card>
      {editing && (
        <SlotDialog
          title={`${t(`timetable.days.${dayKey(editing.weekday)}`)} · ${label(
            cellKey(week[editing.weekday]!, editing.cell),
          )}`}
          cell={editing.cell}
          dayStart={editing.cell.position === 0 ? week[editing.weekday]!.start : null}
          onClose={() => setEditing(null)}
          onApply={(minutes, start) => {
            changed();
            let next = setMinutes(week, editing.weekday, editing.cell.position, minutes);
            if (start !== null) next = setDayStart(next, editing.weekday, start);
            setWeek(next);
            setEditing(null);
          }}
        />
      )}
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t("timetable.deleteTitle", { name: grid.name })}
        confirmLabel={t("timetable.delete")}
        cancelLabel={t("common.cancel")}
        pending={remove.isPending}
        destructive
        onConfirm={() => remove.mutate()}
      >
        <p>{t("timetable.deleteText", { count: grid.class_count })}</p>
        {remove.isError && <Banner tone="due">{firstErrorMessage(remove.error, t)}</Banner>}
      </ConfirmDialog>
    </div>
  );
}

function SlotDialog({
  title,
  cell,
  dayStart,
  onClose,
  onApply,
}: {
  title: string;
  cell: Cell;
  dayStart: number | null;
  onClose: () => void;
  onApply: (minutes: number, start: number | null) => void;
}) {
  const { t } = useTranslation();
  const [minutes, setMinutesValue] = useState(String(cell.end - cell.start));
  const [start, setStart] = useState(dayStart === null ? "" : toClock(dayStart));
  const value = Number(minutes);
  const valid = value >= 5 && value <= 240 && (dayStart === null || start !== "");
  const begins = dayStart === null ? cell.start : toMinutes(start || "00:00");
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={title}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button
              disabled={!valid}
              onClick={() => onApply(value, dayStart === null ? null : toMinutes(start))}
            >
              {t("timetable.applySlot")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {dayStart !== null && (
            <Field id="slot-start" label={t("timetable.dayStart")}>
              {(control) => (
                <Input
                  {...control}
                  type="time"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              )}
            </Field>
          )}
          <Field id="slot-minutes" label={t("timetable.slotMinutes")} required>
            {(control) => (
              <Input
                {...control}
                type="number"
                min={5}
                max={240}
                inputMode="numeric"
                value={minutes}
                onChange={(event) => setMinutesValue(event.target.value)}
              />
            )}
          </Field>
          {valid && (
            <p className="text-sm text-ink-3">
              {t("timetable.slotHelp", { start: toClock(begins), end: toClock(begins + value) })}
            </p>
          )}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}

function NewGridDialog({
  open,
  template,
  onClose,
  onCreated,
}: {
  open: boolean;
  template: TimeGrid | undefined;
  onClose: () => void;
  onCreated: (grid: TimeGrid) => void;
}) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const [name, setName] = useState("");
  const [minutes, setMinutes] = useState("");
  const [start, setStart] = useState("");
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/grids/", {
          body: {
            name: name.trim(),
            // Vides : ceux de la grille par défaut, sinon ceux que propose le serveur.
            ...(minutes || template
              ? { lesson_minutes: Number(minutes) || template?.lesson_minutes }
              : {}),
            ...(start || template ? { start_time: start || template?.start_time } : {}),
          },
        }),
      ),
    onSuccess: (grid) => {
      setName("");
      refresh();
      onCreated(grid);
    },
  });
  return (
    <DialogRoot open={open} onOpenChange={(next) => !next && onClose()}>
      {open && (
        <DialogContent
          title={t("timetable.newGrid")}
          footer={
            <>
              <DialogClose asChild>
                <Button variant="outline">{t("common.cancel")}</Button>
              </DialogClose>
              <Button
                disabled={create.isPending || name.trim() === ""}
                onClick={() => create.mutate()}
              >
                {t("timetable.create")}
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <Field id="new-grid-name" label={t("timetable.name")} required>
              {(control) => (
                <Input
                  {...control}
                  maxLength={60}
                  placeholder={t("timetable.newGridPlaceholder")}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              )}
            </Field>
            <div className="grid grid-cols-2 items-end gap-3">
              <Field id="new-grid-minutes" label={t("timetable.lessonMinutes")}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={30}
                    max={90}
                    inputMode="numeric"
                    placeholder={template ? String(template.lesson_minutes) : undefined}
                    value={minutes}
                    onChange={(event) => setMinutes(event.target.value)}
                  />
                )}
              </Field>
              <Field id="new-grid-start" label={t("timetable.start")}>
                {(control) => (
                  <Input
                    {...control}
                    type="time"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                  />
                )}
              </Field>
            </div>
            <p className="text-sm text-ink-3">{t("timetable.newGridHelp")}</p>
            {create.isError && <Banner tone="due">{firstErrorMessage(create.error, t)}</Banner>}
          </div>
        </DialogContent>
      )}
    </DialogRoot>
  );
}

function ClassesCard({
  grids,
  rows,
  rooms,
}: {
  grids: TimeGrid[];
  rows: ClassRow[];
  rooms: Room[];
}) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const update = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: { time_grid?: string | null; home_room?: string | null };
    }) => call(api.PATCH("/api/timetable/classes/{id}/", { params: { path: { id } }, body })),
    onSuccess: refresh,
  });
  const fallback = grids.find((grid) => grid.is_default);
  const others = grids.filter((grid) => !grid.is_default);
  const toReview = rows.filter((row) => gapOf(row)?.tone !== "ok").length;
  return (
    <Card className="mt-4">
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>{t("timetable.classes")}</CardTitle>
        {toReview > 0 && (
          <span className="text-sm text-ink-3">{t("timetable.toReview", { count: toReview })}</span>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {rows.length === 0 ? (
          <p className="text-ink-3">{t("timetable.noClasses")}</p>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>{t("timetable.class")}</th>
                <th>{t("timetable.grid")}</th>
                <th>{t("timetable.homeRoom")}</th>
                <th className="text-right">{t("timetable.courseHours")}</th>
                <th className="text-right">{t("timetable.places")}</th>
                <th>{t("timetable.gap")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const gap = gapOf(row);
                const choices = rooms.filter((room) => room.is_active || room.id === row.home_room);
                return (
                  <tr key={row.id}>
                    <td data-label={t("timetable.class")} className="font-semibold">
                      {row.name}
                    </td>
                    <td data-label={t("timetable.grid")}>
                      <Select
                        className="w-48 max-w-full"
                        aria-label={t("timetable.gridOf", { name: row.name })}
                        value={row.time_grid && row.time_grid !== fallback?.id ? row.time_grid : ""}
                        disabled={update.isPending}
                        onChange={(event) =>
                          update.mutate({
                            id: row.id,
                            body: { time_grid: event.target.value || null },
                          })
                        }
                      >
                        <option value="">{fallback?.name ?? t("timetable.noGrid")}</option>
                        {others.map((grid) => (
                          <option key={grid.id} value={grid.id}>
                            {grid.name}
                          </option>
                        ))}
                      </Select>
                    </td>
                    <td data-label={t("timetable.homeRoom")}>
                      <Select
                        className="w-48 max-w-full"
                        aria-label={t("timetable.roomOf", { name: row.name })}
                        value={row.home_room ?? ""}
                        disabled={update.isPending}
                        onChange={(event) =>
                          update.mutate({
                            id: row.id,
                            body: { home_room: event.target.value || null },
                          })
                        }
                      >
                        <option value="">{t("timetable.noRoom")}</option>
                        {choices.map((room) => (
                          <option key={room.id} value={room.id}>
                            {room.name}
                          </option>
                        ))}
                      </Select>
                    </td>
                    <td data-label={t("timetable.courseHours")} className="text-right tabular-nums">
                      {row.course_hours}
                    </td>
                    <td data-label={t("timetable.places")} className="text-right tabular-nums">
                      {row.capacity ?? "—"}
                    </td>
                    <td data-label={t("timetable.gap")}>
                      {gap ? (
                        <StatusPill tone={gap.tone}>
                          {t(`timetable.gaps.${gap.key as "over" | "missing" | "full" | "free"}`, {
                            count: gap.count,
                          })}
                        </StatusPill>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
        {update.isError && <Banner tone="due">{firstErrorMessage(update.error, t)}</Banner>}
        <p className="text-sm text-ink-3">{t("timetable.classesHelp")}</p>
      </CardContent>
    </Card>
  );
}

function RulesCard({ rules }: { rules: Rules }) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const [draft, setDraft] = useState({
    max_same_course_per_day: String(rules.max_same_course_per_day),
    teacher_max_day_hours: String(rules.teacher_max_day_hours),
    no_gaps: rules.no_gaps,
    main_courses_early: rules.main_courses_early,
  });
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/timetable/rules/", {
          body: {
            ...draft,
            max_same_course_per_day: Number(draft.max_same_course_per_day),
            teacher_max_day_hours: Number(draft.teacher_max_day_hours),
          },
        }),
      ),
    onSuccess: () => {
      setSaved(true);
      refresh();
    },
  });
  const set = (patch: Partial<typeof draft>) => {
    setSaved(false);
    setDraft({ ...draft, ...patch });
  };
  return (
    <Card className="mt-4 max-w-2xl">
      <CardHeader>
        <CardTitle>{t("timetable.rules")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {(
          [
            ["max_same_course_per_day", "maxSameCourse", 6],
            ["teacher_max_day_hours", "teacherMaxDay", MAX_LESSONS_PER_DAY],
          ] as const
        ).map(([field, key, most]) => (
          <div key={field} className="flex items-center justify-between gap-3">
            <label htmlFor={`rule-${field}`} className="text-sm">
              {t(`timetable.${key}`)}
            </label>
            <Input
              id={`rule-${field}`}
              className="w-20"
              type="number"
              min={1}
              max={most}
              inputMode="numeric"
              value={draft[field]}
              onChange={(event) => set({ [field]: event.target.value })}
            />
          </div>
        ))}
        {(
          [
            ["no_gaps", "noGaps"],
            ["main_courses_early", "mainEarly"],
          ] as const
        ).map(([field, key]) => (
          <div key={field} className="flex items-center justify-between gap-3">
            <label htmlFor={`rule-${field}`} className="text-sm">
              {t(`timetable.${key}`)}
            </label>
            <Switch
              id={`rule-${field}`}
              checked={draft[field]}
              onCheckedChange={(on) => set({ [field]: on })}
            />
          </div>
        ))}
        <p className="text-sm text-ink-3">{t("timetable.rulesHelp")}</p>
        {saved && <Banner tone="ok">{t("timetable.rulesSaved")}</Banner>}
        {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
        <div className="flex justify-end">
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {t("timetable.saveRules")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
