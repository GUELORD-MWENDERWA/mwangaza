// « Heures prestées » (EDT.6, maquettes `heures-prestees` et `fiche-heures-prestees`) : les heures
// prévues viennent de l'horaire publié et du calendrier de l'école ; on ne note que les
// exceptions (absence, remplacement, annulation, heure en plus). Le total du mois est calculé à
// la demande, jamais stocké ; Excel et fiche PDF par enseignant pour la paie. Droit
// `timetable.record_exceptions`. Une exception ne se supprime pas : « Annuler » (motif, journal).
import { formatDay, formatMonth, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  DialogContent,
  DialogRoot,
  Field,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@mwangaza/ui";
import { useState } from "react";

import { errorMessage, firstErrorMessage } from "../../lib/errors";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { useTimetableCourses } from "./data";
import {
  type ExceptionKind,
  type LessonException,
  exportUrl,
  sheetUrl,
  shiftMonth,
  useCancelException,
  useDayLessons,
  useExceptions,
  useRecordException,
  useWorkedMonth,
} from "./worked";

const KINDS: ExceptionKind[] = ["teacher_absent", "replaced", "cancelled", "extra"];
const TONES = { teacher_absent: "due", replaced: "info", cancelled: "gray", extra: "ok" } as const;
const currentMonth = () => new Date().toISOString().slice(0, 7);

export function WorkedHoursPage() {
  const { t, i18n } = useTranslation();
  const [month, setMonth] = useState(currentMonth());
  const [kind, setKind] = useState<ExceptionKind | "">("");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [recording, setRecording] = useState(false);
  const [cancelling, setCancelling] = useState<LessonException | null>(null);
  const [reason, setReason] = useState("");
  const worked = useWorkedMonth(month);
  const exceptions = useExceptions(month, kind, page);
  const cancel = useCancelException();
  const data = worked.data;
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const change = (delta: number) => {
    setMonth(shiftMonth(month, delta));
    setPage(1);
  };
  const teachers = (data?.teachers ?? []).filter((row) =>
    row.name.toLowerCase().includes(search.trim().toLowerCase()),
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("timetable.worked.title")}
        subtitle={t("timetable.worked.subtitle", { month: formatMonth(month, i18n.language) })}
        actions={
          <>
            <span className="flex items-center gap-1 rounded-field border border-line bg-card p-0.5">
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("timetable.worked.previous")}
                onClick={() => change(-1)}
              >
                ‹
              </Button>
              <b className="min-w-[120px] text-center text-sm capitalize">
                {formatMonth(month, i18n.language)}
              </b>
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("timetable.worked.next")}
                disabled={month >= currentMonth()}
                onClick={() => change(1)}
              >
                ›
              </Button>
            </span>
            <Button asChild variant="outline">
              <a href={exportUrl(month)}>
                <Icon name="download" size={16} />
                {t("timetable.worked.export")}
              </a>
            </Button>
            <Button onClick={() => setRecording(true)}>{t("timetable.worked.record")}</Button>
          </>
        }
      />
      {worked.isPending && <Skeleton label={t("common.loading")} />}
      {worked.isError && <LoadError error={worked.error} onRetry={() => void worked.refetch()} />}
      {data && (
        <>
          <div className="grid gap-3 min-[700px]:grid-cols-3">
            <Kpi
              label={t("timetable.worked.planned")}
              value={number(data.totals.planned)}
              sub={t("timetable.worked.days", { count: data.school_days })}
            />
            <Kpi
              label={t("timetable.worked.missed")}
              value={number(data.totals.missed)}
              sub={t("timetable.worked.missedSub")}
            />
            <Kpi
              label={t("timetable.worked.added")}
              value={number(data.totals.added)}
              sub={t("timetable.worked.addedSub")}
            />
          </div>
          {data.holidays.length > 0 && (
            <Banner tone="info">
              {t("timetable.worked.holidays", {
                days: data.holidays.map((day) => formatDay(day, i18n.language)).join(", "),
              })}
            </Banner>
          )}
          <Tabs defaultValue="teachers">
            <TabsList>
              <TabsTrigger value="teachers">{t("timetable.worked.byTeacher")}</TabsTrigger>
              <TabsTrigger value="exceptions">{t("timetable.worked.exceptions")}</TabsTrigger>
            </TabsList>
            <TabsContent value="teachers">
              <Card>
                <CardHeader className="flex-wrap gap-2">
                  <CardTitle>
                    {t("timetable.worked.teachersCount", { count: data.teachers.length })}
                  </CardTitle>
                  <Input
                    type="search"
                    aria-label={t("timetable.worked.search")}
                    placeholder={t("timetable.worked.search")}
                    className="w-auto min-w-[200px]"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </CardHeader>
                <CardContent className="p-0">
                  <Table stacked>
                    <thead>
                      <tr>
                        <th>{t("timetable.worked.teacher")}</th>
                        {(
                          [
                            "planned",
                            "absent",
                            "cancelled",
                            "replacements",
                            "extra",
                            "given",
                          ] as const
                        ).map((key) => (
                          <th key={key} className="text-right">
                            {t(`timetable.worked.columns.${key}`)}
                          </th>
                        ))}
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {teachers.map((row) => (
                        <tr key={row.teacher}>
                          <td data-label={t("timetable.worked.teacher")} data-wrap>
                            <b>{row.name}</b>
                          </td>
                          {(
                            ["planned", "absent", "cancelled", "replacements", "extra"] as const
                          ).map((key) => (
                            <td
                              key={key}
                              className="text-right tabular-nums"
                              data-label={t(`timetable.worked.columns.${key}`)}
                            >
                              {row[key]}
                            </td>
                          ))}
                          <td
                            className="text-right font-bold tabular-nums"
                            data-label={t("timetable.worked.columns.given")}
                          >
                            {row.given}
                          </td>
                          <td className="text-right">
                            <Button asChild variant="outline" size="sm">
                              <a href={sheetUrl(month, row.teacher)} target="_blank" rel="noopener">
                                {t("timetable.worked.sheet")}
                              </a>
                            </Button>
                          </td>
                        </tr>
                      ))}
                      {teachers.length === 0 && (
                        <tr>
                          <td colSpan={8} className="text-center text-ink-3">
                            {t("timetable.worked.noTeacher")}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="exceptions">
              <Card>
                <CardHeader className="flex-wrap gap-2">
                  <CardTitle>
                    {t("timetable.worked.exceptionsCount", { count: exceptions.data?.count ?? 0 })}
                  </CardTitle>
                  <Select
                    aria-label={t("timetable.worked.allKinds")}
                    className="w-auto min-w-[160px]"
                    value={kind}
                    onChange={(event) => {
                      setKind(event.target.value as ExceptionKind | "");
                      setPage(1);
                    }}
                  >
                    <option value="">{t("timetable.worked.allKinds")}</option>
                    {KINDS.map((value) => (
                      <option key={value} value={value}>
                        {t(`timetable.worked.kinds.${value}`)}
                      </option>
                    ))}
                  </Select>
                </CardHeader>
                <CardContent className="p-0">
                  {exceptions.isPending && <Skeleton label={t("common.loading")} />}
                  {exceptions.data && (
                    <>
                      {exceptions.data.results.length === 0 ? (
                        <p className="px-6 py-8 text-center text-ink-3">
                          {t("timetable.worked.noException")}
                        </p>
                      ) : (
                        <Table stacked>
                          <thead>
                            <tr>
                              <th>{t("timetable.worked.course")}</th>
                              <th>{t("timetable.worked.day")}</th>
                              <th>{t("timetable.worked.hour")}</th>
                              <th>{t("timetable.worked.type")}</th>
                              <th>{t("timetable.worked.reason")}</th>
                              <th>{t("timetable.worked.by")}</th>
                              <th />
                            </tr>
                          </thead>
                          <tbody>
                            {exceptions.data.results.map((item) => (
                              <tr key={item.id}>
                                <td data-label={t("timetable.worked.course")} data-wrap>
                                  <b>{item.label}</b>
                                  <span className="block text-sm text-ink-3">
                                    {item.teacher_name}
                                    {item.replacement_name && ` → ${item.replacement_name}`}
                                  </span>
                                </td>
                                <td data-label={t("timetable.worked.day")}>
                                  {formatDay(item.date, i18n.language)}
                                </td>
                                <td
                                  className="tabular-nums"
                                  data-label={t("timetable.worked.hour")}
                                >
                                  {item.first != null
                                    ? t(
                                        item.hours > 1
                                          ? "timetable.worked.hours"
                                          : "timetable.worked.oneHour",
                                        {
                                          first: item.first,
                                          last: item.first + item.hours - 1,
                                        },
                                      )
                                    : t("timetable.worked.hoursCount", { count: item.hours })}
                                </td>
                                <td data-label={t("timetable.worked.type")}>
                                  <StatusPill tone={TONES[item.kind]}>
                                    {t(`timetable.worked.kinds.${item.kind}`)}
                                  </StatusPill>
                                </td>
                                <td data-label={t("timetable.worked.reason")} data-wrap>
                                  {item.reason}
                                </td>
                                <td data-label={t("timetable.worked.by")}>
                                  {item.created_by_name}
                                </td>
                                <td className="text-right">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                      setReason("");
                                      setCancelling(item);
                                    }}
                                  >
                                    {t("timetable.worked.cancel")}
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      )}
                      <Pagination
                        summary={t("timetable.worked.exceptionsCount", {
                          count: exceptions.data.count,
                        })}
                        page={page}
                        hasPrevious={Boolean(exceptions.data.previous)}
                        hasNext={Boolean(exceptions.data.next)}
                        onPage={setPage}
                      />
                    </>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
      {recording && <ExceptionDialog onClose={() => setRecording(false)} />}
      <ConfirmDialog
        open={cancelling !== null}
        onOpenChange={(open) => !open && setCancelling(null)}
        title={t("timetable.worked.cancelTitle")}
        confirmLabel={t("timetable.worked.cancel")}
        cancelLabel={t("common.cancel")}
        pending={cancel.isPending}
        confirmDisabled={reason.trim().length === 0}
        onConfirm={() =>
          cancelling &&
          cancel.mutate({ id: cancelling.id, reason }, { onSuccess: () => setCancelling(null) })
        }
      >
        <div className="flex flex-col gap-3">
          {cancelling && <b>{cancelling.label}</b>}
          {cancel.isError && <Banner tone="due">{errorMessage(cancel.error, t)}</Banner>}
          <Field
            id="cancel-reason"
            label={t("timetable.worked.reason")}
            help={t("timetable.worked.cancelHelp")}
          >
            {(control) => (
              <Input
                {...control}
                maxLength={200}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
        </div>
      </ConfirmDialog>
    </div>
  );
}

function ExceptionDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const courses = useTimetableCourses();
  const record = useRecordException();
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [teacher, setTeacher] = useState("");
  const [kind, setKind] = useState<ExceptionKind>("teacher_absent");
  const [entries, setEntries] = useState<string[]>([]);
  const [replacement, setReplacement] = useState("");
  const [course, setCourse] = useState("");
  const [hours, setHours] = useState("1");
  const [reason, setReason] = useState("");
  const fromTimetable = kind !== "extra";
  const lessons = useDayLessons(fromTimetable ? date : "", teacher);

  const people = new Map<string, string>();
  for (const item of courses.data ?? [])
    if (item.teacher) people.set(item.teacher, item.teacher_name);
  const sorted = [...people].sort((a, b) => a[1].localeCompare(b[1]));
  const own = (courses.data ?? []).filter((item) => item.teacher === teacher);
  const valid =
    Boolean(date && teacher && reason.trim()) &&
    (kind === "extra" ? Boolean(course && Number(hours) >= 1) : entries.length > 0) &&
    (kind !== "replaced" || Boolean(replacement));

  const toggle = (entry: string) =>
    setEntries((current) =>
      current.includes(entry) ? current.filter((item) => item !== entry) : [...current, entry],
    );
  const submit = () =>
    record.mutate(
      {
        date,
        kind,
        teacher,
        reason: reason.trim(),
        ...(fromTimetable ? { entries } : { course, hours: Number(hours) }),
        ...(kind === "replaced" ? { replacement } : {}),
      },
      { onSuccess: onClose },
    );

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("timetable.worked.recordTitle")}
        description={t("timetable.worked.recordSubtitle")}
        footer={
          <>
            <Button variant="outline" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button disabled={!valid || record.isPending} onClick={submit}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {record.isError && <Banner tone="due">{firstErrorMessage(record.error, t)}</Banner>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="exception-date" label={t("timetable.worked.day")}>
              {(control) => (
                <Input
                  {...control}
                  type="date"
                  max={today}
                  value={date}
                  onChange={(event) => {
                    setDate(event.target.value);
                    setEntries([]);
                  }}
                />
              )}
            </Field>
            <Field id="exception-teacher" label={t("timetable.worked.teacher")}>
              {(control) => (
                <Select
                  {...control}
                  value={teacher}
                  onChange={(event) => {
                    setTeacher(event.target.value);
                    setEntries([]);
                    setCourse("");
                  }}
                >
                  <option value="" />
                  {sorted.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-bold text-ink-2">
              {t("timetable.worked.whatHappened")}
            </span>
            <Segmented
              value={kind}
              onValueChange={(next) => {
                setKind(next);
                setEntries([]);
              }}
              label={t("timetable.worked.whatHappened")}
              options={KINDS.map((value) => ({
                value,
                label: t(`timetable.worked.kinds.${value}`),
              }))}
            />
          </div>
          {fromTimetable && teacher && (
            <fieldset className="flex flex-col gap-1">
              <legend className="mb-1 text-sm font-bold">{t("timetable.worked.dayLessons")}</legend>
              {lessons.isPending && <Skeleton label={t("common.loading")} />}
              {lessons.data?.results.length === 0 && (
                <p className="text-sm text-ink-3">{t("timetable.worked.noLesson")}</p>
              )}
              {lessons.data?.results.map((lesson) => (
                <label
                  key={lesson.entry}
                  className="flex cursor-pointer items-start gap-3 border-b border-line-soft py-2"
                >
                  <input
                    type="checkbox"
                    className="mt-1 size-4"
                    checked={entries.includes(lesson.entry)}
                    disabled={Boolean(lesson.recorded)}
                    onChange={() => toggle(lesson.entry)}
                  />
                  <span className="text-sm">
                    <b className="tabular-nums">
                      {t("timetable.worked.oneHour", { first: lesson.first })}
                      {lesson.start && ` · ${lesson.start}–${lesson.end}`}
                    </b>{" "}
                    · {lesson.course} · {lesson.class_groups.join(", ")}
                    {lesson.recorded && (
                      <span className="block text-ink-3">{t("timetable.worked.already")}</span>
                    )}
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          {kind === "replaced" && (
            <Field id="exception-replacement" label={t("timetable.worked.replacement")}>
              {(control) => (
                <Select
                  {...control}
                  value={replacement}
                  onChange={(event) => setReplacement(event.target.value)}
                >
                  <option value="" />
                  {sorted
                    .filter(([id]) => id !== teacher)
                    .map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
          )}
          {kind === "extra" && (
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_120px]">
              <Field id="exception-course" label={t("timetable.worked.extraCourse")}>
                {(control) => (
                  <Select
                    {...control}
                    value={course}
                    disabled={!teacher}
                    onChange={(event) => setCourse(event.target.value)}
                  >
                    <option value="" />
                    {own.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="exception-hours" label={t("timetable.worked.extraHours")}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    max={8}
                    value={hours}
                    onChange={(event) => setHours(event.target.value)}
                  />
                )}
              </Field>
            </div>
          )}
          <Field
            id="exception-reason"
            label={t("timetable.worked.reason")}
            help={t("timetable.worked.reasonHelp")}
          >
            {(control) => (
              <Input
                {...control}
                maxLength={200}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
