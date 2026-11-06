// « Horaire des épreuves » (EDT.5b, maquette `horaire-epreuves`) : le directeur des études fixe les
// interrogations et les examens d'une période, règle les conflits (rouge : classe, surveillant ou
// salle à deux épreuves en même temps, date hors période ; orange : surveillant absent, congé),
// publie : enseignants et familles sont prévenus. Droit `timetable.manage` (publier :
// `timetable.publish`). Publié, plus rien ne se modifie : « Rouvrir » le repasse en brouillon.
import { formatDateTime, formatDay, useTranslation } from "@mwangaza/i18n";
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
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { errorMessage, firstErrorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { useCurrentMe, useSchool } from "../../lib/queries";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { useRooms, useTimetableClasses, useTimetableCourses } from "./data";
import {
  type ExamSitting,
  examPrintUrl,
  examTerms,
  hhmm,
  useDeleteSitting,
  useExamSchedule,
  usePublishExams,
  useSaveSitting,
} from "./exams";

export function ExamSchedulePage() {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const timeZone = useSchool().data?.timezone ?? "Africa/Lubumbashi";
  const years = useYears();
  const [params, setParams] = useSearchParams();
  const year = years.data?.find((item) => item.is_current);
  const terms = examTerms(year, t);
  const today = new Date().toISOString().slice(0, 10);
  const fallback =
    terms.find(
      (item) => item.starts_on && item.ends_on && item.starts_on <= today && today <= item.ends_on,
    ) ?? terms[0];
  const term = terms.find((item) => item.id === params.get("term")) ?? fallback;
  const schedule = useExamSchedule(term?.id ?? "");
  const publish = usePublishExams(term?.id ?? "");
  const remove = useDeleteSitting(term?.id ?? "");
  const [editing, setEditing] = useState<ExamSitting | "new" | null>(null);
  const [removing, setRemoving] = useState<ExamSitting | null>(null);
  const [classFilter, setClassFilter] = useState("");
  const canPublish = can(me, ["timetable.publish"]);
  const courseRows = useTimetableCourses();
  const teachers = new Map<string, string>();
  for (const item of courseRows.data ?? []) {
    if (item.teacher) teachers.set(item.teacher, item.teacher_name);
  }

  if (years.isPending) return <Skeleton label={t("common.loading")} />;
  if (!term) {
    return (
      <>
        <PageHeader title={t("timetable.exams.title")} />
        <Banner tone="warn">{t("timetable.exams.noTerm")}</Banner>
      </>
    );
  }
  const data = schedule.data;
  const published = data?.status === "published";
  const sittings = (data?.sittings ?? []).filter(
    (item) => !classFilter || item.class_group === classFilter,
  );
  const names = new Map((data?.sittings ?? []).map((item) => [item.id, item]));
  const level = (id: string) => {
    const found = (data?.issues ?? []).filter((issue) => issue.sittings.includes(id));
    return found.some((issue) => issue.level === "error")
      ? "due"
      : found.length > 0
        ? "warn"
        : undefined;
  };
  const describe = (issue: NonNullable<typeof data>["issues"][number]) => {
    const list = issue.sittings
      .map((id) => names.get(id))
      .filter((item): item is ExamSitting => Boolean(item))
      .map((item) => `${item.course_name} (${item.class_name})`)
      .join(" · ");
    const date = issue.values.date ? formatDay(String(issue.values.date), i18n.language) : "";
    return t(`timetable.exams.issues.${issue.code}`, {
      defaultValue: issue.code,
      list,
      date,
    });
  };
  const days = [...new Set(sittings.map((item) => item.date))];
  const classes = [...new Map((data?.sittings ?? []).map((i) => [i.class_group, i.class_name]))];
  const errors = (data?.issues ?? []).filter((issue) => issue.level === "error");
  const warnings = (data?.issues ?? []).filter((issue) => issue.level === "warning");
  const range = [...new Set((data?.sittings ?? []).map((item) => item.date))].sort();

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("timetable.exams.title")}
        subtitle={t("timetable.exams.subtitle", { year: year?.name ?? "" })}
        actions={
          <>
            <Select
              aria-label={t("timetable.exams.term")}
              value={term.id}
              className="w-auto min-w-[160px]"
              onChange={(event) => setParams({ term: event.target.value })}
            >
              {terms.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Button asChild variant="outline" disabled={!data || data.sittings.length === 0}>
              <a href={examPrintUrl(term.id, "class")} target="_blank" rel="noopener">
                <Icon name="print" size={16} />
                {t("timetable.exams.print")}
              </a>
            </Button>
            {canPublish && !published && (
              <Button
                disabled={
                  !data || data.errors > 0 || data.sittings.length === 0 || publish.isPending
                }
                title={data && data.errors > 0 ? t("timetable.exams.fixFirst") : undefined}
                onClick={() => publish.mutate(true)}
              >
                {t("timetable.exams.publish")}
              </Button>
            )}
          </>
        }
      />
      {schedule.isPending && <Skeleton label={t("common.loading")} />}
      {schedule.isError && (
        <LoadError error={schedule.error} onRetry={() => void schedule.refetch()} />
      )}
      {publish.isError && <Banner tone="due">{errorMessage(publish.error, t)}</Banner>}
      {data && (
        <>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone={published ? "ok" : "warn"}>
              {t(published ? "timetable.exams.published" : "timetable.exams.draft")}
            </StatusPill>
            <StatusPill tone="gray">
              {t("timetable.exams.count", {
                count: data.sittings.length,
                classes: new Set(data.sittings.map((item) => item.class_group)).size,
              })}
            </StatusPill>
            {range.length > 0 && (
              <StatusPill tone="gray">
                {t("timetable.exams.range", {
                  from: formatDay(range[0]!, i18n.language),
                  to: formatDay(range[range.length - 1]!, i18n.language),
                })}
              </StatusPill>
            )}
          </div>
          {errors.length > 0 && (
            <Banner tone="due">
              <b>{t("timetable.exams.errors", { count: errors.length })}</b>
              <ul className="mt-1 flex list-none flex-col gap-0.5 p-0">
                {errors.map((issue, index) => (
                  <li key={index}>{describe(issue)}</li>
                ))}
              </ul>
            </Banner>
          )}
          {warnings.length > 0 && (
            <Banner tone="warn">
              <b>{t("timetable.exams.warnings", { count: warnings.length })}</b>
              <ul className="mt-1 flex list-none flex-col gap-0.5 p-0">
                {warnings.map((issue, index) => (
                  <li key={index}>{describe(issue)}</li>
                ))}
              </ul>
            </Banner>
          )}
          <Card>
            <CardHeader className="flex-wrap gap-2">
              <CardTitle>{t("timetable.exams.list", { count: data.sittings.length })}</CardTitle>
              <div className="flex flex-wrap gap-2">
                <Select
                  aria-label={t("timetable.exams.allClasses")}
                  value={classFilter}
                  className="w-auto min-w-[160px]"
                  onChange={(event) => setClassFilter(event.target.value)}
                >
                  <option value="">{t("timetable.exams.allClasses")}</option>
                  {classes.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </Select>
                <Button disabled={published} onClick={() => setEditing("new")}>
                  {t("timetable.exams.add")}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {sittings.length === 0 ? (
                <p className="px-6 py-8 text-center text-ink-3">{t("timetable.exams.empty")}</p>
              ) : (
                <Table stacked>
                  <thead>
                    <tr>
                      <th>{t("timetable.exams.course")}</th>
                      <th>{t("timetable.exams.hour")}</th>
                      <th>{t("timetable.exams.kind")}</th>
                      <th>{t("timetable.exams.room")}</th>
                      <th>{t("timetable.exams.invigilator")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {days.flatMap((day) => [
                      <tr key={day} className="[&_td]:bg-table-head">
                        <td colSpan={6}>
                          <b>{formatDay(day, i18n.language)}</b>
                        </td>
                      </tr>,
                      ...sittings
                        .filter((item) => item.date === day)
                        .map((item) => (
                          <tr key={item.id} data-tone={level(item.id)}>
                            <td data-label={t("timetable.exams.course")} data-wrap>
                              <b>{item.course_name}</b>
                              <span className="block text-sm text-ink-3">{item.class_name}</span>
                            </td>
                            <td className="tabular-nums" data-label={t("timetable.exams.hour")}>
                              {hhmm(item.start)}–{hhmm(item.end)}
                            </td>
                            <td data-label={t("timetable.exams.kind")}>
                              <StatusPill tone={item.kind === "exam" ? "info" : "gray"}>
                                {t(`timetable.exams.kinds.${item.kind}`)}
                              </StatusPill>
                            </td>
                            <td data-label={t("timetable.exams.room")}>{item.room_name || "—"}</td>
                            <td data-label={t("timetable.exams.invigilator")}>
                              {item.invigilator ? (teachers.get(item.invigilator) ?? "—") : "—"}
                            </td>
                            <td className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={published}
                                onClick={() => setEditing(item)}
                              >
                                {t("timetable.exams.edit")}
                              </Button>
                            </td>
                          </tr>
                        )),
                    ])}
                  </tbody>
                </Table>
              )}
            </CardContent>
          </Card>
          {published && (
            <Card>
              <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-5">
                <div>
                  <StatusPill tone="ok">{t("timetable.exams.published")}</StatusPill>{" "}
                  <b>
                    {data.published_at &&
                      t("timetable.exams.publishedAt", {
                        date: formatDateTime(new Date(data.published_at), i18n.language, timeZone),
                      })}
                  </b>
                  <p className="text-sm text-ink-3">{t("timetable.exams.publishedHelp")}</p>
                </div>
                <span className="flex gap-2">
                  <Button asChild variant="outline">
                    <a href={examPrintUrl(term.id, "general")} target="_blank" rel="noopener">
                      <Icon name="print" size={16} />
                      {t("timetable.exams.printGeneral")}
                    </a>
                  </Button>
                  {canPublish && (
                    <Button
                      variant="outline"
                      disabled={publish.isPending}
                      onClick={() => publish.mutate(false)}
                    >
                      {t("timetable.exams.reopen")}
                    </Button>
                  )}
                </span>
              </CardContent>
            </Card>
          )}
        </>
      )}
      {editing && (
        <SittingDialog
          term={term}
          teachers={teachers}
          sitting={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onRemove={(item) => {
            setEditing(null);
            setRemoving(item);
          }}
        />
      )}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={t("timetable.exams.removeTitle")}
        confirmLabel={t("timetable.exams.remove")}
        cancelLabel={t("common.cancel")}
        destructive
        pending={remove.isPending}
        onConfirm={() =>
          removing && remove.mutate(removing.id, { onSettled: () => setRemoving(null) })
        }
      >
        {removing && `${removing.course_name} · ${removing.class_name}`}
      </ConfirmDialog>
    </div>
  );
}

type DialogProps = {
  term: { id: string; name: string };
  teachers: Map<string, string>;
  sitting: ExamSitting | null;
  onClose: () => void;
  onRemove: (sitting: ExamSitting) => void;
};

function SittingDialog({ term, teachers, sitting, onClose, onRemove }: DialogProps) {
  const { t } = useTranslation();
  const classes = useTimetableClasses();
  const courses = useTimetableCourses();
  const rooms = useRooms();
  const save = useSaveSitting(term.id, sitting?.id);
  const [classGroup, setClassGroup] = useState(sitting?.class_group ?? "");
  const [course, setCourse] = useState(sitting?.course ?? "");
  const [kind, setKind] = useState<"quiz" | "exam">(sitting?.kind ?? "exam");
  const [date, setDate] = useState(sitting?.date ?? "");
  const [start, setStart] = useState(sitting ? hhmm(sitting.start) : "08:00");
  const [end, setEnd] = useState(sitting ? hhmm(sitting.end) : "10:00");
  const [room, setRoom] = useState(sitting?.room ?? "");
  const [invigilator, setInvigilator] = useState(sitting?.invigilator ?? "");

  const classCourses = (courses.data ?? []).filter((item) => item.class_group === classGroup);
  const valid = Boolean(course && date && start && end && start < end);

  const submit = () =>
    save.mutate(
      {
        course,
        kind,
        date,
        start,
        end,
        room: room || undefined,
        invigilator: invigilator || undefined,
      },
      { onSuccess: onClose },
    );

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t(sitting ? "timetable.exams.editTitle" : "timetable.exams.addTitle")}
        description={t("timetable.exams.dialogSubtitle", { term: term.name })}
        footer={
          <>
            {sitting && (
              <Button
                variant="destructive-outline"
                className="mr-auto"
                onClick={() => onRemove(sitting)}
              >
                {t("timetable.exams.remove")}
              </Button>
            )}
            <Button variant="outline" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button disabled={!valid || save.isPending} onClick={submit}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="exam-class" label={t("timetable.exams.class")}>
              {(control) => (
                <Select
                  {...control}
                  value={classGroup}
                  onChange={(event) => {
                    setClassGroup(event.target.value);
                    setCourse("");
                  }}
                >
                  <option value="" />
                  {(classes.data ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field id="exam-course" label={t("timetable.exams.course")}>
              {(control) => (
                <Select
                  {...control}
                  value={course}
                  disabled={!classGroup}
                  onChange={(event) => setCourse(event.target.value)}
                >
                  <option value="" />
                  {classCourses.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-bold text-ink-2">{t("timetable.exams.kind")}</span>
            <Segmented
              value={kind}
              onValueChange={setKind}
              label={t("timetable.exams.kind")}
              options={[
                { value: "quiz", label: t("timetable.exams.kinds.quiz") },
                { value: "exam", label: t("timetable.exams.kinds.exam") },
              ]}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="exam-date" label={t("timetable.exams.day")}>
              {(control) => (
                <Input
                  {...control}
                  type="date"
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                />
              )}
            </Field>
            <div className="flex items-end gap-2">
              <Field id="exam-start" label={t("timetable.exams.hour")} className="flex-1">
                {(control) => (
                  <Input
                    {...control}
                    type="time"
                    value={start}
                    onChange={(event) => setStart(event.target.value)}
                  />
                )}
              </Field>
              <span className="pb-2.5">{t("timetable.exams.to")}</span>
              <Field id="exam-end" label={t("timetable.exams.end")} className="flex-1">
                {(control) => (
                  <Input
                    {...control}
                    type="time"
                    value={end}
                    onChange={(event) => setEnd(event.target.value)}
                  />
                )}
              </Field>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="exam-room" label={t("timetable.exams.room")}>
              {(control) => (
                <Select {...control} value={room} onChange={(event) => setRoom(event.target.value)}>
                  <option value="" />
                  {(rooms.data ?? [])
                    .filter((item) => item.is_active)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
            <Field id="exam-invigilator" label={t("timetable.exams.invigilator")}>
              {(control) => (
                <Select
                  {...control}
                  value={invigilator}
                  onChange={(event) => setInvigilator(event.target.value)}
                >
                  <option value="" />
                  {[...teachers]
                    .sort((a, b) => a[1].localeCompare(b[1]))
                    .map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
          </div>
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
