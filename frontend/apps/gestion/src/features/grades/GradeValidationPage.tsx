// Suivi des notes (8.2.2, NB.2, maquette `notes-validation`) : le tableau du directeur des études.
// Pour une période ou des examens, l'état de la fiche de cotes de chaque cours de chaque classe
// (pas commencée, en cours, envoyée, validée, renvoyée), le rappel des enseignants en retard (une
// notification par enseignant), le tableau synthétique, le palmarès et, classe complète, les
// bulletins quand le titulaire les dit prêts (NB.3) ; dates limites de saisie à côté. Droit `grades.validate` (double authentification).
import { api, call } from "@mwangaza/api";
import { firstErrorMessage, formatDate, formatTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  ConfirmDialog,
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
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { termLabels } from "../../lib/terms";
import { LoadError } from "../status/StatusPages";
import {
  type BoardClass,
  type BoardCourse,
  type BoardData,
  isLate,
  remindable,
  teacherCount,
  useValidation,
} from "./data";
import { gradableTerms } from "./GradesPage";

type Filter = "late" | "toValidate" | "complete" | "all";

const TONES = {
  not_started: "gray",
  in_progress: "warn",
  submitted: "info",
  validated: "ok",
  returned: "due",
} as const;
const COUNTED = ["submitted", "returned", "in_progress", "not_started"] as const;

const FILTERS: Record<Filter, (group: BoardClass) => boolean> = {
  late: (group) => group.courses.some(isLate),
  toValidate: (group) => group.courses.some((course) => course.status === "submitted"),
  complete: (group) => group.complete,
  all: () => true,
};

export function GradeValidationPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  // Notification « Bulletins prêts » (NB.3) : la période dans l'adresse.
  const [termId, setTermId] = useState(() => params.get("term") ?? "");
  const [filter, setFilter] = useState<Filter>("late");
  const [confirm, setConfirm] = useState<BoardCourse[] | null>(null);
  const validation = useValidation(termId);
  const canRemind = Boolean(me.school?.modules.includes("notifications"));

  const remind = useMutation({
    mutationFn: (input: { term: string; courses: BoardCourse[] }) =>
      call(
        api.POST("/api/grading/reminders/", {
          body: { term: input.term, courses: input.courses.map((course) => course.id) },
        }),
      ),
    onSuccess: () => {
      setConfirm(null);
      void queryClient.invalidateQueries({ queryKey: keys.gradeValidation });
    },
  });

  if (validation.isPending) return <Skeleton label={t("common.loading")} />;
  if (validation.isError) {
    return <LoadError error={validation.error} onRetry={() => void validation.refetch()} />;
  }
  const data = validation.data;
  const labels = termLabels(data.terms, t);
  const leaves = gradableTerms(data.terms, labels);
  const term = data.term ?? "";
  const termLabel = leaves.find((leaf) => leaf.id === term)?.label ?? "";
  const courses = data.classes.flatMap((group) => group.courses);
  const late = remindable(courses);
  const shown = data.classes.filter(FILTERS[filter]);
  const count = (status: BoardCourse["status"]) =>
    courses.filter((course) => course.status === status).length;
  const sendReminders = (list: BoardCourse[]) => remind.mutate({ term, courses: list });

  return (
    <>
      <PageHeader
        title={t("gradeValidation.title")}
        subtitle={t("gradeValidation.subtitle")}
        actions={
          leaves.length > 0 && (
            <div className="text-left!">
              <Field id="board-term" label={t("gradeValidation.term")}>
                {(control) => (
                  <Select
                    {...control}
                    value={term}
                    onChange={(event) => setTermId(event.target.value)}
                    className="min-w-52"
                  >
                    {leaves.map((leaf) => (
                      <option key={leaf.id} value={leaf.id}>
                        {leaf.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
          )
        }
      />
      {remind.isSuccess && (
        <div className="mb-4">
          <Banner tone={remind.data.notified ? "ok" : "info"}>
            {remind.data.notified
              ? t("gradeValidation.remind.done", { count: remind.data.notified })
              : t("gradeValidation.remind.nothing")}
          </Banner>
        </div>
      )}
      {remind.isError && (
        <div className="mb-4">
          <Banner tone="due">{firstErrorMessage(remind.error, t)}</Banner>
        </div>
      )}
      {!data.term ? (
        <Banner tone="info">{t("gradeValidation.noTerm")}</Banner>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 min-[1100px]:grid-cols-4">
            <Kpi
              label={t("gradeValidation.stats.complete")}
              value={`${data.classes.filter((group) => group.complete).length} / ${data.classes.length}`}
              sub={t("gradeValidation.stats.completeSub")}
              icon="check"
              chip="ok"
            />
            <Kpi
              label={t("gradeValidation.stats.toValidate")}
              value={count("submitted")}
              sub={t("gradeValidation.stats.toValidateSub")}
              icon="inbox"
            />
            <Kpi
              label={t("gradeValidation.stats.notSent")}
              value={count("not_started") + count("in_progress")}
              sub={t("gradeValidation.stats.notSentSub", { count: count("not_started") })}
              icon="clock"
              chip="warn"
            />
            <Kpi
              label={t("gradeValidation.stats.returned")}
              value={count("returned")}
              sub={t("gradeValidation.stats.returnedSub")}
              icon="undo"
              chip="due"
            />
          </div>
          <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
            <Card>
              <CardHeader className="flex-wrap gap-3">
                <CardTitle>{t("gradeValidation.classes")}</CardTitle>
                <Segmented
                  label={t("gradeValidation.classes")}
                  value={filter}
                  onValueChange={setFilter}
                  className="flex-wrap"
                  options={(Object.keys(FILTERS) as Filter[]).map((key) => ({
                    value: key,
                    label: t(`gradeValidation.filter.${key}`, {
                      count: data.classes.filter(FILTERS[key]).length,
                    }),
                  }))}
                />
              </CardHeader>
              {data.classes.length === 0 ? (
                <p className="px-5 py-6 text-sm text-ink-2">{t("gradeValidation.noCourse")}</p>
              ) : shown.length === 0 ? (
                <p className="px-5 py-6 text-sm text-ink-2">{t("gradeValidation.noneShown")}</p>
              ) : (
                shown.map((group, index) => (
                  <ClassBlock
                    key={group.id}
                    group={group}
                    term={term}
                    firstOpen={index === 0}
                    canRemind={canRemind}
                    pending={remind.isPending}
                    onRemind={sendReminders}
                  />
                ))
              )}
            </Card>
            <div className="flex flex-col gap-4">
              {canRemind && (
                <Card>
                  <CardHeader>
                    <CardTitle>{t("gradeValidation.remind.title")}</CardTitle>
                  </CardHeader>
                  <div className="flex flex-col gap-3 px-5 py-4 text-sm">
                    {late.length === 0 ? (
                      <p className="text-ink-2">{t("gradeValidation.remind.none")}</p>
                    ) : (
                      <>
                        <p>
                          {t("gradeValidation.remind.summary", {
                            count: late.length,
                            term: termLabel,
                          })}
                        </p>
                        <Button onClick={() => setConfirm(late)} disabled={remind.isPending}>
                          <Icon name="bell" size={16} />
                          {t("gradeValidation.remind.all", { count: teacherCount(late) })}
                        </Button>
                      </>
                    )}
                    <p className="text-ink-3">{t("gradeValidation.remind.help")}</p>
                  </div>
                </Card>
              )}
              <DeadlinesCard data={data} labels={leaves} />
            </div>
          </div>
        </>
      )}
      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={t("gradeValidation.remind.confirmTitle", {
          count: teacherCount(confirm ?? []),
        })}
        confirmLabel={t("gradeValidation.remind.confirm")}
        cancelLabel={t("common.cancel")}
        pending={remind.isPending}
        onConfirm={() => confirm && sendReminders(confirm)}
      >
        {t("gradeValidation.remind.confirmText", { term: termLabel })}
      </ConfirmDialog>
    </>
  );
}

function ClassBlock({
  group,
  term,
  firstOpen,
  canRemind,
  pending,
  onRemind,
}: {
  group: BoardClass;
  term: string;
  firstOpen: boolean;
  canRemind: boolean;
  pending: boolean;
  onRemind: (courses: BoardCourse[]) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = open ?? firstOpen;
  const validated = group.courses.filter((course) => course.status === "validated").length;
  const total = group.courses.length;
  const late = remindable(group.courses);
  const sheets = (kind: "class" | "ranking") =>
    `/grade-sheets?class=${group.id}&kind=${kind}&column=${term}`;

  return (
    <section className="border-t border-line-soft px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 flex-[1_1_220px]">
          <h3 className="font-bold">{group.name}</h3>
          <p className="text-sm text-ink-3">
            {group.homeroom_teacher
              ? t("gradeValidation.homeroom", { name: group.homeroom_teacher })
              : t("gradeValidation.noHomeroom")}
          </p>
        </div>
        <div className="flex-[1_1_200px]">
          <div className="flex justify-between text-sm">
            <span className="text-ink-3">{t("gradeValidation.validated")}</span>
            <b className="tabular-nums">
              {validated} / {total}
            </b>
          </div>
          <div
            className="mt-1.5 h-2 overflow-hidden rounded-full bg-gray-50"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={validated}
            aria-label={t("gradeValidation.validated")}
          >
            <i
              className={`block h-full rounded-full ${group.complete ? "bg-ok" : "bg-lake"}`}
              style={{ width: `${total ? Math.round((validated * 100) / total) : 0}%` }}
            />
          </div>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {COUNTED.map((status) => {
          const n = group.courses.filter((course) => course.status === status).length;
          return n ? (
            <StatusPill key={status} tone={TONES[status]}>
              {t(`gradeValidation.counts.${status}`, { count: n })}
            </StatusPill>
          ) : null;
        })}
        {group.ready_at ? (
          <StatusPill tone="ok">
            {t("gradeValidation.ready", {
              date: formatDate(group.ready_at, i18n.language, school.timezone),
            })}
          </StatusPill>
        ) : (
          group.complete &&
          group.homeroom_teacher && (
            <StatusPill tone="info">{t("gradeValidation.waitingHomeroom")}</StatusPill>
          )
        )}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {canRemind && late.length > 0 && (
          <Button size="sm" disabled={pending} onClick={() => onRemind(late)}>
            <Icon name="bell" size={14} />
            {t("gradeValidation.remind.class", {
              count: new Set(late.map((c) => c.teacher_id)).size,
            })}
          </Button>
        )}
        <Button asChild size="sm" variant="outline">
          <Link to={sheets("class")}>
            <Icon name="file" size={14} />
            {t("gradeValidation.table")}
          </Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link to={sheets("ranking")}>
            <Icon name="print" size={14} />
            {t("gradeValidation.ranking")}
          </Link>
        </Button>
        {/* Bulletins : quand le titulaire les dit prêts (NB.3) ; classe sans titulaire : complète. */}
        {(group.ready_at || (group.complete && !group.homeroom_teacher)) && (
          <Button asChild size="sm">
            <Link to={`/report-cards?class=${group.id}`}>
              <Icon name="print" size={14} />
              {t("gradeValidation.reportCards")}
            </Link>
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={expanded}
          onClick={() => setOpen(!expanded)}
        >
          <Icon name="chevdown" size={14} className={expanded ? "rotate-180" : undefined} />
          {expanded ? t("gradeValidation.hideCourses") : t("gradeValidation.showCourses")}
        </Button>
      </div>
      {expanded && (
        <div className="mt-3">
          <Table stacked freeze>
            <thead>
              <tr>
                <th>{t("gradeValidation.columns.course")}</th>
                <th>{t("gradeValidation.columns.teacher")}</th>
                <th>{t("gradeValidation.columns.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {group.courses.map((course) => (
                <tr key={course.id}>
                  <td data-label={t("gradeValidation.columns.course")}>
                    <b>{course.name}</b>
                  </td>
                  <td data-label={t("gradeValidation.columns.teacher")}>
                    {course.teacher || t("gradeValidation.noTeacher")}
                  </td>
                  <td data-label={t("gradeValidation.columns.status")}>
                    <StatusPill tone={TONES[course.status]}>
                      {t(`gradeValidation.status.${course.status}`)}
                    </StatusPill>
                  </td>
                  <td className="text-right">
                    {!isLate(course) ? (
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/grade-sheets/totals?course=${course.id}&term=${term}`}>
                          {t("gradeValidation.open")}
                        </Link>
                      </Button>
                    ) : !course.teacher_id ? (
                      <span className="text-sm text-ink-3">
                        {t("gradeValidation.withoutTeacher")}
                      </span>
                    ) : course.reminded_today && course.reminded_at ? (
                      <span className="text-sm text-ink-3">
                        {t("gradeValidation.remindedToday", {
                          time: formatTime(course.reminded_at, i18n.language, school.timezone),
                        })}
                      </span>
                    ) : canRemind ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={pending}
                        onClick={() => onRemind([course])}
                      >
                        <Icon name="bell" size={14} />
                        {t("gradeValidation.remind.one")}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </section>
  );
}

function DeadlinesCard({
  data,
  labels,
}: {
  data: BoardData;
  labels: { id: string; label: string }[];
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const due = new Map(data.deadlines.map((row) => [row.term, row.due_on]));

  const setDeadline = useMutation({
    mutationFn: (input: { term: string; due_on: string | null }) =>
      call(
        api.PUT("/api/terms/{term}/grades-deadline/", {
          params: { path: { term: input.term } },
          body: { due_on: input.due_on },
        }),
      ),
    onSuccess: (_result, input) => {
      setDrafts((all) =>
        Object.fromEntries(Object.entries(all).filter(([id]) => id !== input.term)),
      );
      void queryClient.invalidateQueries({ queryKey: keys.gradeValidation });
      void queryClient.invalidateQueries({ queryKey: keys.gradeSheet });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("gradeValidation.deadlines.title")}</CardTitle>
      </CardHeader>
      {setDeadline.isSuccess && (
        <div className="px-5 pt-3">
          <Banner tone="ok">{t("gradeValidation.deadlines.saved")}</Banner>
        </div>
      )}
      {setDeadline.isError && (
        <div className="px-5 pt-3">
          <Banner tone="due">{firstErrorMessage(setDeadline.error, t)}</Banner>
        </div>
      )}
      <p className="px-5 pt-3 text-sm text-ink-2">{t("gradeValidation.deadlines.help")}</p>
      <ul className="divide-y divide-line-soft">
        {labels.map((leaf) => {
          const current = due.get(leaf.id) ?? "";
          const value = drafts[leaf.id] ?? current;
          return (
            <li key={leaf.id} className="flex flex-wrap items-center gap-2 px-5 py-3">
              <span className="mr-auto text-sm font-medium">{leaf.label}</span>
              <Input
                type="date"
                aria-label={t("gradeValidation.deadlines.dateOf", { term: leaf.label })}
                value={value}
                onChange={(event) =>
                  setDrafts((all) => ({ ...all, [leaf.id]: event.target.value }))
                }
                className="w-auto"
              />
              <Button
                size="sm"
                variant="outline"
                disabled={value === current || setDeadline.isPending}
                onClick={() => setDeadline.mutate({ term: leaf.id, due_on: value || null })}
              >
                {t("common.save")}
              </Button>
              {current && (
                <span className="basis-full text-sm text-ink-3">
                  {t("gradeValidation.deadlines.until", {
                    date: formatDate(current, i18n.language, school.timezone),
                  })}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
