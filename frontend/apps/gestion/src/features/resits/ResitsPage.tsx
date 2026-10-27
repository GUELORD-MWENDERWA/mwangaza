// Examens de repêchage (8.4.1, maquette `repechage`) : pour chaque élève de la classe, les cours
// échoués d'après les règles de l'école, la note de repêchage (saisie et signée par l'enseignant
// du cours) et l'issue proposée. La décision prise est celle de la délibération (8.4.2).
import { api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  Field,
  Icon,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { RuleCited } from "../deliberation/RuleCited";
import { useGrading } from "../grades/data";
import { LoadError } from "../status/StatusPages";
import { convocationsUrl, useClassResits, type ResitCourse, type StudentResits } from "./data";

const TONES: Record<string, "ok" | "warn" | "due" | "gray"> = {
  passed: "ok",
  resit: "warn",
  failed: "due",
  incomplete: "gray",
  unranked: "gray",
  orient: "warn",
  exclude: "due",
};

type Target = { enrollment: string; course: string };

export function ResitsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const grading = useGrading();
  const [params] = useSearchParams();
  const [classId, setClassId] = useState(params.get("class") ?? "");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [examDay, setExamDay] = useState<string | null>(null);

  const classes = grading.data?.classes ?? [];
  const groupId = classId || classes[0]?.id || "";
  const table = useClassResits(groupId);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.resits });
  const draftKey = ({ enrollment, course }: Target) => `${enrollment}:${course}`;

  const saveExamDay = useMutation({
    mutationFn: (examOn: string) =>
      call(
        api.PUT("/api/class-groups/{id}/resits/exam-date/", {
          params: { path: { id: groupId } },
          body: { exam_on: examOn },
        }),
      ),
    onSuccess: () => {
      setExamDay(null);
      refresh();
    },
  });
  const save = useMutation({
    mutationFn: (target: Target) =>
      call(
        api.PUT("/api/resits/enrollments/{id}/courses/{course_pk}/", {
          params: { path: { id: target.enrollment, course_pk: target.course } },
          body: { percent: (drafts[draftKey(target)] ?? "").replace(",", ".") },
        }),
      ),
    onSuccess: (_data, target) => {
      setDrafts((current) => {
        const rest = { ...current };
        delete rest[draftKey(target)];
        return rest;
      });
      refresh();
    },
  });
  const clear = useMutation({
    mutationFn: (target: Target) =>
      call(
        api.DELETE("/api/resits/enrollments/{id}/courses/{course_pk}/", {
          params: { path: { id: target.enrollment, course_pk: target.course } },
        }),
      ),
    onSuccess: refresh,
  });

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const courseLine = (student: StudentResits, course: ResitCourse) => {
    const target = { enrollment: student.enrollment, course: course.course };
    const key = draftKey(target);
    return (
      <li key={course.course} className="flex flex-wrap items-center gap-2">
        <span>
          <b>{course.course_name}</b>{" "}
          <span className="text-xs text-ink-3">
            {t("resits.percent", { value: course.percent })}
          </span>
        </span>
        <>
          {course.can_enter ? (
            <>
              <Input
                aria-label={t("resits.gradeFor", { course: course.course_name })}
                inputMode="decimal"
                className="w-20 text-right tabular-nums"
                value={drafts[key] ?? course.resit_percent ?? ""}
                onChange={(event) => setDrafts({ ...drafts, [key]: event.target.value })}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={save.isPending || (drafts[key] ?? "").trim() === ""}
                onClick={() => save.mutate(target)}
              >
                {t("resits.save")}
              </Button>
              {course.resit_percent !== null && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={clear.isPending}
                  onClick={() => clear.mutate(target)}
                >
                  {t("resits.clear")}
                </Button>
              )}
            </>
          ) : course.resit_percent !== null ? (
            <span className="whitespace-nowrap tabular-nums">
              {t("resits.percent", { value: course.resit_percent })}
            </span>
          ) : (
            <span className="text-xs text-ink-3">{t("resits.waiting")}</span>
          )}
          {course.signed_by && (
            <span className="text-xs text-ink-3">
              {t("resits.signedBy", { name: course.signed_by })}
            </span>
          )}
        </>
      </li>
    );
  };

  // Seconde session (NB.6) : élèves proclamés « repêchage », date de l'examen, convocations.
  const secondSession = (data: NonNullable<typeof table.data>) => {
    const session = data.second_session;
    const closed = session.status === "proclaimed";
    const day = examDay ?? session.exam_on ?? "";
    return (
      <Card>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-bold">{t("resits.secondTitle")}</h2>
            <StatusPill tone={closed ? "ok" : "warn"}>
              {t(`deliberation.status_${session.status}`)}
            </StatusPill>
          </div>
          <p className="text-sm">{t("resits.secondIntro", { count: session.students })}</p>
          {session.can_manage && !closed ? (
            <div className="flex flex-wrap items-end gap-3">
              <Field id="resits-exam-day" label={t("resits.examDay")}>
                {(control) => (
                  <Input
                    {...control}
                    type="date"
                    value={day}
                    onChange={(event) => setExamDay(event.target.value)}
                  />
                )}
              </Field>
              {examDay && examDay !== session.exam_on && (
                <Button
                  variant="outline"
                  disabled={saveExamDay.isPending}
                  onClick={() => saveExamDay.mutate(examDay)}
                >
                  {t("resits.saveExamDay")}
                </Button>
              )}
            </div>
          ) : (
            <p className="text-sm">
              {session.exam_on
                ? t("resits.examOn", { date: formatDay(session.exam_on, i18n.language) })
                : t("resits.noExamDay")}
            </p>
          )}
          {saveExamDay.isError && (
            <Banner tone="due">{firstErrorMessage(saveExamDay.error, t)}</Banner>
          )}
          {session.can_manage && (
            <div className="flex flex-wrap gap-2">
              {session.exam_on ? (
                <Button asChild>
                  <a href={convocationsUrl(groupId)} target="_blank" rel="noreferrer">
                    <Icon name="print" />
                    {t("resits.convocations")}
                  </a>
                </Button>
              ) : (
                <Button disabled>
                  <Icon name="print" />
                  {t("resits.convocations")}
                </Button>
              )}
              <Button asChild variant="outline">
                <Link to={`/deliberation?class=${groupId}&session=second`}>
                  {t("resits.openSecond")}
                </Link>
              </Button>
            </div>
          )}
          <p className="text-xs text-ink-3">
            {t(closed ? "resits.secondClosed" : "resits.secondHelp")}
          </p>
        </CardContent>
      </Card>
    );
  };

  return (
    <>
      <PageHeader title={t("resits.title")} subtitle={t("resits.subtitle")} />
      {classes.length === 0 ? (
        <Banner tone="info">{t("resits.noClass")}</Banner>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-4">
            <div className="max-w-xs">
              <Field id="resits-class" label={t("resits.class")}>
                {(control) => (
                  <Select
                    {...control}
                    value={groupId}
                    onChange={(event) => {
                      setClassId(event.target.value);
                      setExamDay(null);
                    }}
                  >
                    {classes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            {table.isPending ? (
              <Skeleton label={t("common.loading")} />
            ) : table.isError ? (
              <LoadError error={table.error} onRetry={() => void table.refetch()} />
            ) : table.data.students.length === 0 ? (
              <Banner tone="info">{t("resits.none")}</Banner>
            ) : (
              <>
                <Table stacked freeze>
                  <thead>
                    <tr>
                      <th>{t("resits.student")}</th>
                      <th>{t("resits.year")}</th>
                      <th>{t("resits.courses")}</th>
                      <th>{t("resits.outcome")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.data.students.map((student) => (
                      <tr key={student.enrollment}>
                        <td data-label={t("resits.student")} data-wrap>
                          {student.full_name}
                        </td>
                        <td
                          data-label={t("resits.year")}
                          className="whitespace-nowrap tabular-nums"
                        >
                          {student.percent === null
                            ? "—"
                            : t("resits.percent", { value: student.percent })}
                        </td>
                        <td data-label={t("resits.courses")} data-wrap>
                          <ul className="flex flex-col gap-2">
                            {student.courses
                              .filter((course) => course.eligible)
                              .map((course) => courseLine(student, course))}
                            {student.courses.some((course) => !course.eligible) && (
                              <li className="text-xs text-ink-3">
                                {t("resits.notOpenList", {
                                  list: student.courses
                                    .filter((course) => !course.eligible)
                                    .map((course) =>
                                      t("resits.courseAt", {
                                        course: course.course_name,
                                        value: course.percent,
                                      }),
                                    )
                                    .join(", "),
                                })}
                              </li>
                            )}
                          </ul>
                        </td>
                        <td data-label={t("resits.outcome")}>
                          <span className="flex flex-col items-end min-[600px]:items-start">
                            <StatusPill tone={TONES[student.outcome] ?? "gray"}>
                              {t(`resits.outcome_${student.outcome}`)}
                            </StatusPill>
                            <RuleCited rule={student.rule} params={student.rule_params} />
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                {(save.isError || clear.isError) && (
                  <Banner tone="due">{firstErrorMessage(save.error ?? clear.error, t)}</Banner>
                )}
                <p className="text-xs text-ink-3">
                  {t("resits.help", {
                    pass: table.data.rules.pass_percent,
                    course: table.data.rules.course_pass_percent,
                  })}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      )}
      {table.data && table.data.second_session.students > 0 && secondSession(table.data)}
    </>
  );
}
